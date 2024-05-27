"""Utility functions for iemwebfarm applications."""

import datetime
import random
import re
import string
import sys
import traceback
import warnings
from collections import namedtuple
from http import HTTPStatus
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import nh3
from paste.request import parse_formvars
from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    ValidationError,
    WithJsonSchema,
    field_validator,
)
from pymemcache.client import Client
from sqlalchemy import text
from typing_extensions import Annotated

from pyiem.database import get_dbconnc, get_sqlalchemy_conn
from pyiem.exceptions import (
    BadWebRequest,
    IncompleteWebRequest,
    NewDatabaseConnectionFailure,
    NoDataFound,
)
from pyiem.templates.iem import TEMPLATE
from pyiem.util import LOG

# Forgive some typos
TZ_TYPOS = {
    "central": "America/Chicago",
    "CST": "America/Chicago",
    "CDT": "America/Chicago",
    "MST": "America/Denver",
    "MDT": "America/Denver",
    "PST": "America/Los_Angeles",
    "PDT": "America/Los_Angeles",
    "AKST": "America/Anchorage",
    "AKDT": "America/Anchorage",
    "HST": "Pacific/Honolulu",
    "HDT": "Pacific/Honolulu",
    "GMT": "UTC",
    "UT": "UTC",
    "etc/utc": "UTC",
    "utc": "UTC",
}
# Key matching iemdb.<name>.conn
DBKEY_RE = re.compile(r"^iemdb\.(.*)\.conn$")
# Match something that looks like a four digit year
YEAR_RE = re.compile(r"^\d{4}")
TELEMETRY = namedtuple(
    "TELEMETRY",
    ["timing", "status_code", "client_addr", "app", "request_uri", "vhost"],
)


def _conv2list(mixed) -> list:
    """Convert to a list."""
    if isinstance(mixed, list):
        return mixed
    return mixed.split(",")


def _ensure_all_strings(mixed) -> list:
    """Ensure we have all strings."""
    return [x for x in mixed if isinstance(x, str)]


ListOrCSVType = Annotated[
    list,
    BeforeValidator(_conv2list),
    AfterValidator(_ensure_all_strings),
    WithJsonSchema({"type": "string"}, mode="serialization"),
]


# https://github.com/tiangolo/fastapi/discussions/8143#discussioncomment-5147698
class CGIModel(BaseModel):
    """A Pydantic model that parses CGI arguments."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(self, **kwargs):
        try:
            super().__init__(**kwargs)
        except ValidationError as e:
            errors = e.errors()
            for error in errors:
                error["loc"] = ("query",) + error["loc"]
            raise IncompleteWebRequest(errors) from e

    @field_validator("*", mode="before")
    def xss_protect(cls, v):
        """Protect against XSS attacks."""
        if isinstance(v, str) and nh3.clean(v) != v:
            raise ValueError("XSS detected")
        return v


def model_to_rst(model: BaseModel) -> str:
    """Convert a Pydantic model to a reStructuredText table.

    Args:
        model: The Pydantic model to convert

    Returns: A reStructuredText table
    """
    rst = [
        "CGI Arguments",
        "-------------",
        "",
        """
The following table lists the CGI arguments that are accepted by this service.
A HTTP ``GET`` request is required. Fields of type
**Multi-Params or CSV value** can accept either a comma separated list or
multiple parameter and value combinations.  For example, ``?foo=1&foo=2`` is
equivalent to ``?foo=1,2``.
        """,
        "",
        ".. list-table::",
        "   :header-rows: 1",
        "   :widths: 15 15 70",
        "",
        "   * - Field",
        "     - Type",
        "     - Description",
    ]
    schema = model.model_json_schema()
    for key, prop in schema["properties"].items():
        required = " (required)" if key in schema.get("required", []) else ""
        if "anyOf" in prop:
            typetext = " or ".join([x["type"] for x in prop["anyOf"]])
        else:
            typetext = prop["type"]
            if typetext == "array":
                typetext = "Multi-Params or CSV value"
        rst.append(
            f"   * - {key}\n"
            f"     - {typetext}{required}\n"
            f"     - {prop.get('description', '')}"
        )
    return "\n".join(rst)


def write_telemetry(data: TELEMETRY) -> bool:
    """Write telemetry to the database."""
    # Yes, this blocks, but if this database is not working, we are in trouble
    try:
        with get_sqlalchemy_conn("mesosite") as conn:
            conn.execute(
                text(
                    """
                insert into website_telemetry(timing, status_code,
                client_addr, app, request_uri, vhost)
                values (:timing, :status_code, :client_addr,
                :app, :request_uri, :vhost)
                """
                ),
                data._asdict(),
            )
            conn.commit()
        return True
    except Exception as exp:
        LOG.exception(exp)
    return False


def ensure_list(environ, key, parse_commas=True) -> list:
    """Ensure that we get something that is at least an empty list.

    Args:
        environ: the WSGI environ
        key: the key to look for
        parse_commas: split each found value based on commas, default True.
    """
    if key not in environ:
        return []
    if isinstance(environ[key], list):
        res = environ[key]
    else:
        res = [environ[key]]
    if parse_commas:
        res = [x.strip() for y in res for x in y.split(",")]
    return res


def clean_form(form):
    """Opinionated cleaning of form data."""
    if "tz" in form and isinstance(form["tz"], list):
        if len(set(form["tz"])) == 1:
            form["tz"] = form["tz"][0]
        else:
            raise NoDataFound("GET variable tz specified twice, please fix.")
    return form


def log_request(environ):
    """Log the request to database for future processing."""
    with get_sqlalchemy_conn("mesosite") as conn:
        conn.execute(
            text(
                """
            INSERT into weblog(client_addr, uri, referer, http_status)
            VALUES (:client_addr, :uri, :referer, :http_status)
            """
            ),
            dict(
                client_addr=environ.get("REMOTE_ADDR"),
                uri=environ.get("REQUEST_URI"),
                referer=environ.get("HTTP_REFERER"),
                http_status=404,
            ),
        )
        conn.commit()


def compute_ts_from_string(form, key):
    """Convert a string to a timestamp."""
    # Support various ISO8601 formats
    tstr = form[key].replace("T", " ")
    tz = ZoneInfo(form.get("tz", "America/Chicago"))
    if tstr.endswith("Z"):
        tz = ZoneInfo("UTC")
        tstr = tstr[:-1]
    fmt = "%Y-%m-%d %H:%M:%S"
    if "." in tstr:
        fmt += ".%f"
    if len(tstr.split(":")) == 2:
        fmt = "%Y-%m-%d %H:%M"
    return datetime.datetime.strptime(tstr, fmt).replace(tzinfo=tz)


def compute_ts(form, suffix):
    """Figure out the timestamp."""
    # NB: form["tz"] should always be set by this point, but alas
    month = int(form.get(f"month{suffix}", form.get("month")))
    day = min(int(form.get(f"day{suffix}", form.get("day"))), 31)
    # Forgive bad day of the month combinations
    if month in [4, 6, 9, 11] and day == 31:
        day = 30
    # Forgive specification of two years, with pydantic, this could be NOne
    yearval = form.get(f"year{suffix}") or form.get("year")
    if isinstance(yearval, list) and len(set(yearval)) == 1:
        yearval = yearval[0]
    # Forgive February 29ths on non-leap years
    if month == 2 and day > 28:
        # Check for leap year, close enough
        if int(yearval) % 4 == 0 and yearval not in [1800, 1900]:
            day = min(day, 29)
        else:
            day = 28

    return datetime.datetime(
        int(yearval),
        month,
        day,
        int(form.get(f"hour{suffix}", 0)),
        int(form.get(f"minute{suffix}", 0)),
        tzinfo=ZoneInfo(form.get("tz", "America/Chicago")),
    )


def add_to_environ(environ, form, **kwargs):
    """Build out some things auto-parsed from the request."""
    # Process database connection requests
    for dbname in ensure_list(kwargs, "iemdb"):
        cursor_name = kwargs.get("iemdb_cursorname")
        pgconn, cursor = get_dbconnc(dbname, cursor_name=cursor_name)
        environ[f"iemdb.{dbname}.conn"] = pgconn
        environ[f"iemdb.{dbname}.cursor"] = cursor
    for key, val in form.items():
        if key not in environ:
            # check for XSS and other naughty things
            # We should only have either lists or strings
            if isinstance(val, list):
                for va in val:
                    if nh3.clean(va) != va:
                        raise BadWebRequest(f"XSS Key: {key} Value: {va}")
            elif isinstance(val, str):
                if nh3.clean(val) != val:
                    raise BadWebRequest(f"XSS Key: {key} Value: {val}")
            environ[key] = form[key]
        else:
            warnings.warn(
                f"Refusing to over-write environ key {key}",
                UserWarning,
                stacklevel=1,
            )
    if kwargs.get("parse_times", True):
        try:
            # Le Sigh, darly used sts for stations in the past, so ensure
            # that sts starts with something that looks like a year
            if isinstance(form.get("sts"), str) and YEAR_RE.match(form["sts"]):
                environ["sts"] = compute_ts_from_string(form, "sts")
            if isinstance(form.get("ets"), str) and YEAR_RE.match(form["ets"]):
                environ["ets"] = compute_ts_from_string(form, "ets")
            # NB: The usage of a schema may have already parsed a sts or ets,
            # but it will be None if it was not provided
            if form.get("day1") is not None and form.get("sts") is None:
                environ["sts"] = compute_ts(form, "1")
            if form.get("day2") is not None and form.get("ets") is None:
                environ["ets"] = compute_ts(form, "2")
        except (TypeError, ValueError) as exp:
            raise IncompleteWebRequest("Invalid timestamp specified") from exp
        except (IsADirectoryError, ZoneInfoNotFoundError) as exp:
            raise IncompleteWebRequest("Invalid timezone specified") from exp


def _handle_help(start_response, **kwargs):
    """Handle the help request.

    Args:
        start_response: the WSGI start_response function
        kwargs: the keyword arguments passed to the decorator

    Returns The HTML response
    """
    start_response("200 OK", [("Content-type", "text/html")])
    # return the module docstring for the func
    from docutils.core import publish_string

    sdoc = kwargs.get("help", "Help not available") + (
        "" if "schema" not in kwargs else model_to_rst(kwargs["schema"])
    )
    html = publish_string(source=sdoc, writer_name="html").decode("utf-8")
    # Get the content between the body tags
    res = {"content": html.split("<body>")[1].split("</body>")[0]}
    return [TEMPLATE.render(res).encode("utf-8")]


def _debracket(form):
    """Remove brackets from form keys."""
    res = {}
    for key in form:
        if key.endswith("[]"):
            res[key[:-2]] = form[key]
        else:
            res[key] = form[key]
    return res


def _mcall(func, environ, start_response, memcachekey, expire, content_type):
    """Call the function with memcachekey handling."""
    if memcachekey is None:
        return func(environ, start_response)
    key = memcachekey if isinstance(memcachekey, str) else memcachekey(environ)
    mc = Client("iem-memcached:11211")
    res = mc.get(key)
    if not res:
        res = func(environ, start_response)
        mc.set(key, res, expire)
    else:
        # since our function never got called, we need to start_response
        ct = (
            content_type
            if isinstance(content_type, str)
            else content_type(environ)
        )
        start_response("200 OK", [("Content-type", ct)])
    cb = environ.get("callback")
    if cb is not None:
        if isinstance(res, str):
            res = f"{cb}({res})"
        elif isinstance(res, bytes):
            res = f"{cb}({res.decode('utf-8')})"
    mc.close()
    return res


def iemapp(**kwargs):
    """Attempt to do all kinds of nice things for the user and the developer.

    kwargs:
        - default_tz: The default timezone to use for timestamps, the default
          is ``America/Chicago``.
        - enable_telemetry: Enable telemetry logging, default ``True``.
        - help: Default help text, default ``Help not available``.
        - parse_times: Parse the form for timestamps, default ``True``.
        - iemdb: (str or list) The database(s) to connect to, these will be
          bundled into the environ with keys of `iemdb.<name>.conn` and
          `iemdb.<name>.cursor`.  No commit is performed. You can specify a
          single cursor name with `iemdb_cursorname=<name>`.
        - schema (BaseModel): A Pydantic model to parse the form with.
        - memcachekey (str or callable): A memcache key to use for caching
          the response.
        - memcacheexpire (int): The number of seconds to cache the response.
        - content_type (str or callable): The content type to use for the
          response.

    What all this does:
        1) Attempts to catch database connection errors and handle nicely
        2) Updates `environ` with some auto-parsed values + form content.
        3) If the wrapped function returns a str or bytes, it will be encoded
           and made into a list for the WSGI response.

    Notes
    -----
        - raise `NoDataFound` to have a nice error message generated
    """

    def _decorator(func):
        """Decorate a function to catch exceptions and do nice things."""

        def _wrapped(environ, start_response):
            """Decorate function."""

            def _handle_exp(errormsg, routine=False, code=500):
                # generate a random string so we can track this request
                uid = "".join(
                    random.choice(string.ascii_uppercase + string.digits)
                    for _ in range(12)
                )
                msg = (
                    "Oopsy, something failed on our end, but fear not.\n"
                    "Please contact akrherz@iastate.edu and reference "
                    f"this unique identifier: {uid}\n"
                    "Or wait a day for daryl to review the web logs and fix "
                    "the bugs he wrote.  What a life."
                )
                if not routine:
                    # Nicely log things about this actual request
                    sys.stderr.write(
                        f"={uid} URL: {environ.get('REQUEST_URI')}\n"
                    )
                    sys.stderr.write(errormsg)
                else:
                    msg = errormsg
                start_response(
                    f"{code} {HTTPStatus(code).phrase}",
                    [("Content-type", "text/plain")],
                )
                return [msg.encode("ascii")]

            start_time = datetime.datetime.utcnow()
            status_code = 500
            try:
                # mixed convers this to a regular dict
                form = clean_form(parse_formvars(environ).mixed())
                if "help" in form:
                    return _handle_help(start_response, **kwargs)
                if "schema" in kwargs:
                    form = kwargs["schema"](**_debracket(form)).model_dump()
                if "tz" not in form:
                    form["tz"] = kwargs.get("default_tz", "America/Chicago")
                # Important this is set before calling add_to_environ
                form["tz"] = TZ_TYPOS.get(form["tz"], form["tz"])
                add_to_environ(environ, form, **kwargs)
                res = _mcall(
                    func,
                    environ,
                    start_response,
                    kwargs.get("memcachekey"),
                    kwargs.get("memcacheexpire", 3600),
                    kwargs.get("content_type", "application/json"),
                )
                # you know what assumptions do
                status_code = 200
            except IncompleteWebRequest as exp:
                status_code = 422
                res = _handle_exp(str(exp), routine=True, code=status_code)
            except BadWebRequest as exp:
                status_code = 422
                log_request(environ)
                res = _handle_exp(str(exp), code=status_code)
            except NoDataFound as exp:
                status_code = 200
                res = _handle_exp(str(exp), routine=True, code=status_code)
            except NewDatabaseConnectionFailure as exp:
                status_code = 503
                res = _handle_exp(
                    f"get_dbconn() failed with `{exp}`",
                    code=status_code,
                )
            except Exception:
                res = _handle_exp(traceback.format_exc())
            end_time = datetime.datetime.utcnow()
            if kwargs.get("enable_telemetry", True):
                write_telemetry(
                    TELEMETRY(
                        (end_time - start_time).total_seconds(),
                        status_code,
                        environ.get("REMOTE_ADDR"),
                        environ.get("SCRIPT_NAME"),
                        environ.get("REQUEST_URI"),
                        environ.get("HTTP_HOST"),
                    )
                )
            # Ensure we close any database connections
            for key in environ:
                if DBKEY_RE.match(key):
                    if not environ[key.replace(".conn", ".cursor")].closed:
                        environ[key.replace(".conn", ".cursor")].close()
                    environ[key].close()
            # Need to be careful here and ensure we are returning a list
            # of bytes
            if isinstance(res, str):
                return [res.encode("utf-8")]
            if isinstance(res, bytes):
                return [res]
            return res

        return _wrapped

    return _decorator
