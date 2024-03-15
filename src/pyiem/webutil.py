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
from sqlalchemy import text

from pyiem.database import get_dbconnc, get_sqlalchemy_conn
from pyiem.exceptions import (
    BadWebRequest,
    IncompleteWebRequest,
    NewDatabaseConnectionFailure,
    NoDataFound,
)
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
    ["timing", "status_code", "client_addr", "app", "request_uri"],
)


def write_telemetry(data: TELEMETRY) -> bool:
    """Writes telemetry to the database."""
    # Yes, this blocks, but if this database is not working, we are in trouble
    try:
        with get_sqlalchemy_conn("mesosite") as conn:
            conn.execute(
                text(
                    """
                insert into website_telemetry(timing, status_code,
                client_addr, app, request_uri)
                values (:timing, :status_code, :client_addr,
                :app, :request_uri)
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
    # Forgive specification of two years
    yearval = form.get(f"year{suffix}", form.get("year"))
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
    for key in form:
        if key not in environ:
            # check for XSS and other naughty things
            val = form[key]
            # We should only have either lists or strings
            if isinstance(val, list):
                for va in val:
                    if nh3.clean(va) != va:
                        raise BadWebRequest(f"XSS Key: {key} Value: {va}")
            else:
                if nh3.clean(val) != val:
                    raise BadWebRequest(f"XSS Key: {key} Value: {val}")
            environ[key] = form[key]
        else:
            warnings.warn(
                f"Refusing to over-write environ key {key}",
                UserWarning,
            )
    if kwargs.get("parse_times", True):
        try:
            # Le Sigh, darly used sts for stations in the past, so ensure
            # that sts starts with something that looks like a year
            if isinstance(form.get("sts"), str) and YEAR_RE.match(form["sts"]):
                environ["sts"] = compute_ts_from_string(form, "sts")
            if isinstance(form.get("ets"), str) and YEAR_RE.match(form["ets"]):
                environ["ets"] = compute_ts_from_string(form, "ets")
            if "day1" in form and "sts" not in form:
                environ["sts"] = compute_ts(form, "1")
            if "day2" in form and "ets" not in form:
                environ["ets"] = compute_ts(form, "2")
        except (TypeError, ValueError):
            raise IncompleteWebRequest("Invalid timestamp specified")
        except (IsADirectoryError, ZoneInfoNotFoundError):
            raise IncompleteWebRequest("Invalid timezone specified")


def iemapp(**kwargs):
    """
    Attempts to do all kinds of nice things for the user and the developer.

    kwargs:
        - default_tz: The default timezone to use for timestamps
        - enable_telemetry: Enable telemetry logging, default ``True``.
        - help: Default help text, default ``Help not available``.
        - parse_times: Parse the form for timestamps, default ``True``.
        - iemdb: (str or list) The database(s) to connect to, these will be
          bundled into the environ with keys of `iemdb.<name>.conn` and
          `iemdb.<name>.cursor`.  No commit is performed. You can specify a
          single cursor name with `iemdb_cursorname=<name>`.

    Example usage:
        @iemapp()
        def application(environ, start_response):
            return [b"Content-type: text/plain\n\nHello World!"]

    What all this does:
      1) Attempts to catch database connection errors and handle nicely
      2) Updates `environ` with some auto-parsed values + form content.

    Notes:
      - raise `NoDataFound` to have a nice error message generated
    """

    def _decorator(func):
        """Decorate a function to catch exceptions and do nice things."""

        def _wrapped(environ, start_response):
            """Decorated function."""

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
                    start_response("200 OK", [("Content-type", "text/html")])
                    # return the module docstring for the func
                    from docutils.core import publish_string

                    return [
                        publish_string(
                            source=kwargs.get("help", "Help not available"),
                            writer_name="html",
                        )
                    ]
                if "tz" not in form:
                    form["tz"] = kwargs.get("default_tz", "America/Chicago")
                form["tz"] = TZ_TYPOS.get(form["tz"], form["tz"])
                add_to_environ(environ, form, **kwargs)
                res = func(environ, start_response)
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
                    )
                )
            # Ensure we close any database connections
            for key in environ:
                if DBKEY_RE.match(key):
                    if not environ[key.replace(".conn", ".cursor")].closed:
                        environ[key.replace(".conn", ".cursor")].close()
                    environ[key].close()
            return res

        return _wrapped

    return _decorator
