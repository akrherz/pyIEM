"""Utility functions for iemwebfarm applications."""

import html
import inspect
import io
import os
import random
import re
import socket
import string
import sys
import traceback
import warnings
from collections.abc import Callable
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any, Iterator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from docutils.core import publish_string
from paste.request import parse_formvars
from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    IPvAnyAddress,
    ValidationError,
    WithJsonSchema,
    field_validator,
)
from pymemcache.client import Client
from typing_extensions import Annotated

from pyiem.database import get_sqlalchemy_conn, sql_helper
from pyiem.exceptions import (
    BadWebRequest,
    IncompleteWebRequest,
    NewDatabaseConnectionFailure,
    NoDataFound,
)
from pyiem.templates import get_site_template
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
# Match something that looks like a four digit year
YEAR_RE = re.compile(r"^\d{4}")


class TELEMETRY(BaseModel):
    timing: Annotated[
        float, Field(description="Request processing time in seconds")
    ]
    status_code: Annotated[int, Field(description="HTTP response code")]
    client_addr: Annotated[
        IPvAnyAddress | None,
        Field(
            description="Valid IPv4/IPv6 address",
        ),
    ] = None
    app: Annotated[
        str | None, Field(description="App generating this telemetry")
    ] = None
    request_uri: Annotated[str | None, Field(description="Request URI")] = None
    vhost: Annotated[str | None, Field(description="virtual host")] = None
    valid: Annotated[
        datetime,
        Field(
            description="Timestamp when this telemetry record was generated"
        ),
    ]

    @field_validator("app", "request_uri", mode="before")
    @classmethod
    def prevent_null_bytes(cls, v):
        """Prevent null bytes in these fields."""
        if isinstance(v, str) and "\x00" in v:
            raise ValueError("Null bytes are not allowed")
        return v


TELEMETRY_PREFIX = "Telemetry "
# A rsyslog socket established via akrherz/infra-ansible that is a side-door
# to send rsyslog messages without systemd intercepting them and filling
# journal logs
RSYSLOG_SIDEDOOR_SOCKET = "/run/rsyslog/iemweb.sock"
XSS_SENTINEL = "XSS"
MEMCACHED_HIT = "_mhit"


def _conv2list(mixed: str | list) -> list:
    """Ensure we have a list of strings without csv delimination."""
    if isinstance(mixed, list):
        # pydantic my come here with a string that is still delimited
        result = []
        for item in mixed:
            result.extend(x.strip() for x in item.split(","))
        return result
    return [x.strip() for x in mixed.split(",")]


def _ensure_all_strings(mixed) -> list:
    """Ensure we have all strings."""
    return [x for x in mixed if isinstance(x, str)]


ListOrCSVType = Annotated[
    list,
    BeforeValidator(_conv2list),
    AfterValidator(_ensure_all_strings),
    WithJsonSchema({"type": "string"}, mode="serialization"),
]


def _is_xss_payload(val: str) -> bool:
    """Return True if the provided string appears to contain XSS payloads.

    We first normalize entities with `html.unescape` and then inspect it. If
    the normalized text contains HTML tag-like patterns or javascript: URIs,
    treat it as naughty.
    """
    normalized = html.unescape(val)
    # Detect tag-like content (e.g. <script>, <img src=...>, etc.)
    if re.search(r"<\s*/?\s*[a-zA-Z]", normalized):
        return True
    # Detect javascript: URIs which may be used as payloads
    if re.search(r"javascript\s*:", normalized, re.I):
        return True
    return False


# https://github.com/tiangolo/fastapi/discussions/8143#discussioncomment-5147698
class CGIModel(BaseModel):
    """A Pydantic model that parses CGI arguments."""

    model_config = ConfigDict(
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )

    def __init__(self, **kwargs):
        try:
            super().__init__(**kwargs)
        except ValidationError as e:
            errors = e.errors()
            for error in errors:
                error["loc"] = ("query",) + error["loc"]
                if str(error.get("ctx", {}).get("error", "")) == XSS_SENTINEL:
                    raise BadWebRequest(
                        f"XSS Key: {error['loc']} Value: {error.get('input')}"
                    ) from e
            raise IncompleteWebRequest(errors) from e

    @field_validator("*", mode="before")
    @classmethod
    def xss_protect(cls, v):
        """Protect against XSS attacks."""
        # We want pydantic to *fail* validation when naughty HTML/JS is
        # provided, but avoid false-positives for benign strings that only
        # differ because of entity escaping (e.g. '&amp;').
        if isinstance(v, str):
            if _is_xss_payload(v):
                raise ValueError(XSS_SENTINEL)
            return v
        if isinstance(v, list):
            for x in v:
                if isinstance(x, str) and _is_xss_payload(x):
                    raise ValueError(XSS_SENTINEL)
            return v
        # Another field_validator may have run at this point and we have
        # a non-str datatype
        return v


def emit_to_sidedoor(payload: bytes) -> None:
    """Send the given payload to the rsyslog sidedoor."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.setblocking(False)
            sock.sendto(payload, RSYSLOG_SIDEDOOR_SOCKET)
    except OSError:
        LOG.exception("Failed to send telemetry payload")


def error_log(environ: dict, msg: str) -> None:
    """Properly send an error log message.

    Args:
      environ (dict): The mod_wsgi environment
      msg (str): The message to log
    """
    # For whatever reason, when this error message is logged, Apache does not
    # have the headers to include with the message, so we need to include them
    # ourselves.
    client_addr = environ.get(
        "HTTP_X_FORWARDED_FOR", environ.get("REMOTE_ADDR")
    )
    host = environ.get("HTTP_HOST", "unknown")
    # 141 is local1.notice
    payload = (f"<141>iemwebErrorLog {client_addr} [{host}] {msg}").encode()
    emit_to_sidedoor(payload)


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
        desc = str(prop.get("description", "")).strip()
        if desc:
            desc = "\n       ".join(
                [line.strip() for line in desc.splitlines() if line.strip()]
            )
        rst.append(f"   * - {key}\n     - {typetext}{required}\n     - {desc}")
    return "\n".join(rst)


def write_telemetry(data: TELEMETRY) -> bool:
    """Best-effort telemetry write."""
    # 141 is local1.notice and is critical to make this work.
    # The TELEMETRY_PREFIX becomes the syslog tag
    payload = (
        "<141>" + TELEMETRY_PREFIX + data.model_dump_json(indent=None)
    ).encode("utf-8")
    # We need to avoid syslog as systemd/journal will intercept this and
    # fill logs quickly.
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.setblocking(False)
            sock.sendto(payload, RSYSLOG_SIDEDOOR_SOCKET)
    except OSError:
        return False
    return True


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


def log_request(environ: dict, multiplier: int = 1):
    """Log the request to database for future processing."""
    with get_sqlalchemy_conn("mesosite") as conn:
        for _ in range(multiplier):
            conn.execute(
                sql_helper(
                    """
        INSERT into weblog
        (client_addr, uri, referer, http_status, x_forwarded_for, domain)
        VALUES (:client_addr, :uri, :referer, :http_status, :x_forwarded_for,
        :domain)
                """
                ),
                {
                    "client_addr": environ.get("REMOTE_ADDR"),
                    "uri": environ.get("REQUEST_URI"),
                    "referer": environ.get("HTTP_REFERER"),
                    "http_status": 404,
                    "x_forwarded_for": environ.get("HTTP_X_FORWARDED_FOR"),
                    "domain": environ.get("HTTP_HOST"),
                },
            )
        conn.commit()


def compute_ts_from_string(
    form: dict, key: str, default_tz: str | None
) -> datetime:
    """Convert a string to a timestamp."""
    tz = ZoneInfo(form.get("tz", default_tz or "America/Chicago"))
    val = datetime.fromisoformat(form[key])
    if val.tzinfo is None:
        val = val.replace(tzinfo=tz)
    return val


def compute_ts(form: dict, suffix: str, default_tz: str | None) -> datetime:
    """Figure out the timestamp."""
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

    return datetime(
        int(yearval),
        month,
        day,
        int(form.get(f"hour{suffix}", 0)),
        int(form.get(f"minute{suffix}", 0)),
        tzinfo=ZoneInfo(form.get("tz", default_tz or "America/Chicago")),
    )


def condition_form_for_datetimes(
    schema: BaseModel, form: dict, default_tz: str | None
):
    """Modify the form to account for ambiguous things in the schema."""
    tzfield = schema.model_fields.get("tz")
    # Logic short-circuit here requiring either default_tz or schema.tz
    # to be set
    if default_tz is None and tzfield is None:
        return
    if tzfield and str(tzfield.annotation) == "str | None":
        raise NotImplementedError("CGIModel tz field cannot be optional")
    tzinfo = form.get("tz") or default_tz or tzfield.default
    tz_to_use = ZoneInfo(tzinfo)
    # Iterate over the field
    for field_name, field in schema.model_fields.items():
        if "datetime" in str(field.annotation) and field_name not in form:
            default = field.default
            if field.default_factory:
                default = field.default_factory()
            if isinstance(default, datetime) and default.tzinfo is None:
                default = default.replace(tzinfo=tz_to_use)
            if default:
                form[field_name] = default.isoformat()
            continue
        if "datetime" in str(field.annotation) and field_name in form:
            user_value = form[field_name]
            if isinstance(user_value, str):
                # This should have some timezone information in the string
                # This exercises pydantic's value import logic ahead of time
                try:
                    val = datetime.fromisoformat(user_value)
                    if val.tzinfo is None:
                        val = val.replace(tzinfo=tz_to_use)
                        form[field_name] = val.isoformat()
                except ValueError:
                    # Do nothing and allow it to fail later...
                    pass


def condition_form_for_tz(form: dict, kwargs: dict):
    """Ensure that tz is well formed and free of known typos."""
    if form["tz"] == "":
        form["tz"] = kwargs.get("default_tz", "America/Chicago")
    # Correct any known typos in the tz value before further processing
    form["tz"] = TZ_TYPOS.get(form["tz"], form["tz"])

    # Pre-flight check for a valid timezone
    try:
        ZoneInfo(form["tz"])
    except (IsADirectoryError, ValueError, ZoneInfoNotFoundError) as exp:
        raise IncompleteWebRequest("Invalid tz specified") from exp


def add_to_environ(environ: dict, form: dict, **kwargs):
    """Build out some things auto-parsed from the request."""
    kwargs_default_tz = kwargs.get("default_tz")
    # Typically apps without schema definition, so this removes some
    # downstream boilerplate to prevent unwanted lists
    allowed = kwargs.get("allowed_as_list", [])
    if allowed:
        for key in form:
            if not isinstance(form[key], list):
                continue
            if key not in allowed:
                raise BadWebRequest(f"Key {key} is a list, but not allowed")

    # tz has important implications, so we need to preflight check this
    if "tz" in form:
        condition_form_for_tz(form, kwargs)

    schema = None
    if "schema" in kwargs:
        # Account for misery associated with pydantic model defining a
        # datetime type that is then ambiguous about if a tzinfo should
        # be included
        condition_form_for_datetimes(kwargs["schema"], form, kwargs_default_tz)
        # Remove any form keys that are not contained in the
        # schema, but first we debracket keys with []
        form = {
            k: v
            for k, v in _debracket(form).items()
            if k in kwargs["schema"].model_fields and v != ""
        }
        raw_form = form
        schema = kwargs["schema"](**raw_form)
        # Retain a reference to the Schema instance as it may have
        # private / computed attributes that are needed
        environ["_cgimodel_schema"] = schema
        form = schema.model_dump()

    for key, val in form.items():
        if key not in environ:
            # check for XSS and other naughty things
            # We should only have either lists or strings
            if isinstance(val, list):
                for va in val:
                    if isinstance(va, str) and _is_xss_payload(va):
                        raise BadWebRequest(f"XSS Key: {key} Value: {va}")
            elif isinstance(val, str):
                if _is_xss_payload(val):
                    raise BadWebRequest(f"XSS Key: {key} Value: {val}")
            environ[key] = form[key]
        else:
            warnings.warn(
                f"Refusing to over-write environ key {key}",
                UserWarning,
                stacklevel=1,
            )
    if kwargs.get("parse_times", True):
        sts = None
        ets = None
        try:
            # Le Sigh, darly used sts for stations in the past, so ensure
            # that sts starts with something that looks like a year
            if isinstance(form.get("sts"), str) and YEAR_RE.match(form["sts"]):
                sts = compute_ts_from_string(form, "sts", kwargs_default_tz)
            if isinstance(form.get("ets"), str) and YEAR_RE.match(form["ets"]):
                ets = compute_ts_from_string(form, "ets", kwargs_default_tz)
            # NB: The usage of a schema may have already parsed a sts or ets,
            # but it will be None if it was not provided
            if form.get("day1") is not None and form.get("sts") is None:
                sts = compute_ts(form, "1", kwargs_default_tz)
            if form.get("day2") is not None and form.get("ets") is None:
                ets = compute_ts(form, "2", kwargs_default_tz)
            # Assign back into environ and schema (with validation)
            if sts:
                environ["sts"] = sts
                if schema is not None and "sts" in type(schema).model_fields:
                    # Send back as str to get downstream schema validation
                    schema.sts = sts.isoformat()
            if ets:
                environ["ets"] = ets
                if schema is not None and "ets" in type(schema).model_fields:
                    # Send back as str to get downstream schema validation
                    schema.ets = ets.isoformat()
        except (TypeError, ValueError) as exp:
            msg = "" if not isinstance(exp, ValidationError) else f" {exp}"
            raise IncompleteWebRequest(
                f"Invalid timestamp specified{msg}"
            ) from exp


def _handle_help(httphost: str, **kwargs):
    """Handle the help request.

    Args:
        start_response: the WSGI start_response function
        httphost: the HTTP_HOST header value for this request
        kwargs: the keyword arguments passed to the decorator

    Returns The HTML response
    """
    # return the module docstring for the func

    sdoc = kwargs.get("help", "Help not available")
    if "schema" in kwargs:
        sdoc = f"{sdoc}\n\n{model_to_rst(kwargs['schema'])}"
    warning_stream = io.StringIO()
    rendered = publish_string(
        source=sdoc,
        writer_name="html",
        settings_overrides={
            # Keep docutils CSS external so we can style ourselves.
            "embed_stylesheet": False,
            # Never raise, but capture/report warnings for visibility.
            "warning_stream": warning_stream,
        },
    ).decode("utf-8")

    warning_text = warning_stream.getvalue().strip()
    if warning_text:
        LOG.warning("Docutils warnings while rendering help: %s", warning_text)

    # Load external CSS file for styling docutils-generated content
    css_path = os.path.join(
        os.path.dirname(__file__), "data", "docutils-help.css"
    )
    with open(css_path, "r", encoding="utf-8") as fh:
        css_content = fh.read()

    # Get just the rendered HTML body and wrap with responsive container.
    body_content = rendered.split("<body>")[1].split("</body>")[0]
    styled_content = (
        f"<style>\n{css_content}\n</style>"
        f'<div class="container-fluid">{body_content}</div>'
    )

    res = {"content": styled_content}
    # avert your eyes
    mapper = {
        "mesonet-dep.agron.iastate.edu": "dep",
        "depbackend.local": "dep",
    }
    hostkey = httphost.split(":", 1)[0].lower()
    template = get_site_template(mapper.get(hostkey, "iem"), "full.j2")
    return template.render(res).encode("utf-8")


def _debracket(form):
    """Remove brackets from form keys."""
    res = {}
    for key in form:
        if key.endswith("[]"):
            res[key[:-2]] = form[key]
        else:
            res[key] = form[key]
    return res


def _mcall(
    func: Callable,
    environ: dict,
    start_response: Callable,
    memcachekey: str | Callable | None,
    expire: int | Callable,
    content_type: str | Callable,
):
    """Call the function with memcachekey handling."""
    if memcachekey is None:
        return func(environ, start_response)
    key = memcachekey if isinstance(memcachekey, str) else memcachekey(environ)
    # Ensure that the key is not too long for memcache
    if key is None or len(key) > 249 or inspect.isgeneratorfunction(func):
        # An appside short circuit when we programatically do not want cache
        # or we are dealing with a generator
        return func(environ, start_response)
    mc = Client("iem-memcached:11211")
    res = mc.get(key)
    if not res:
        res = func(environ, start_response)
        # IEM memcache instances run with a 10MB limit `-I 10m`, so check first
        if len(res) < 10e6:
            mc.set(
                key,
                res,
                expire if isinstance(expire, int) else expire(environ),
            )
    else:
        # since our function never got called, we need to start_response
        ct = (
            content_type
            if isinstance(content_type, str)
            else content_type(environ)
        )
        start_response("200 OK", [("Content-type", ct)])
        environ[MEMCACHED_HIT] = True
    cb = environ.get("callback")
    if cb is not None:
        if isinstance(res, str):
            res = f"{cb}({res})"
        elif isinstance(res, bytes):
            res = f"{cb}({res.decode('utf-8')})"
    mc.close()
    return res


def ip_is_throttled(environ: dict, throttle_secs: float | Callable) -> bool:
    """Return True if the REMOTE_ADDR is throttled."""
    client_ip = environ.get("REMOTE_ADDR")
    if not client_ip or client_ip.startswith(("127.", "129.186.", "10.")):
        return False
    if isinstance(throttle_secs, Callable):
        throttle_secs = throttle_secs(environ)
    if throttle_secs > 0:
        # No connection happens until it is used, so this should not fail
        mc = Client(("iem-memcached", 11211))
        key = f"throttle:{client_ip}"
        expire = int(throttle_secs) + 1
        try:
            # Important to set noreply=False to ensure add returns reality
            return not mc.add(key, "1", expire=expire, noreply=False)
        except Exception:
            LOG.warning(
                "ip_is_throttled backend exception for ip=%s key=%s "
                "ttl=%s pid=%s uri=%s",
                client_ip,
                key,
                expire,
                os.getpid(),
                environ.get("REQUEST_URI", "?"),
                exc_info=True,
            )
        finally:
            mc.close()
    return False


def _iemapp_error_response(
    environ: dict,
    start_response: Callable,
    errormsg: str,
    routine: bool = False,
    code: int = 500,
) -> bytes:
    """Build an iemapp text/plain error response payload."""
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
        sys.stderr.write(f"={uid} URL: {environ.get('REQUEST_URI')}\n")
        sys.stderr.write(errormsg)
    else:
        msg = errormsg
    start_response(
        f"{code} {HTTPStatus(code).phrase}",
        [("Content-type", "text/plain")],
    )
    return msg.encode("ascii", errors="replace")


def _iemapp_preflight(
    environ: dict,
    start_response: Callable,
    kwargs: dict[str, Any],
    ip_throttle_secs: float | Callable,
) -> tuple[bool, bytes | None]:
    """Run request preflight checks and return early payload when needed."""
    # Handle OPTIONS requests
    if environ.get("REQUEST_METHOD", "") == "OPTIONS":
        start_response(
            "204 No Content",
            [("Content-type", "text/plain"), ("Allow", "GET, OPTIONS")],
        )
        return True, b""

    # mixed converts this to a regular dict
    form = parse_formvars(environ).mixed()
    form = clean_form(form)
    if "help" in form:
        hostname = environ.get("HTTP_HOST", "unknown")
        payload = _handle_help(hostname, **kwargs)
        start_response("200 OK", [("Content-type", "text/html")])
        return True, payload
    add_to_environ(environ, form, **kwargs)
    if ip_is_throttled(environ, ip_throttle_secs):
        start_response(
            "429 Too Many Requests",
            [("Content-type", "text/plain")],
        )
        return True, b"Too many requests from your IP address, slow down."
    return False, None


def _normalize_iemapp_response(res: Any) -> Iterator[bytes]:
    """Yield response chunks in a uniform iterable form."""
    # Need to be careful here and ensure we are returning a list of bytes.
    if isinstance(res, str):
        yield res.encode("utf-8")
        return
    if isinstance(res, bytes):
        yield res
        return
    if isinstance(res, (tuple, list)):
        for chunk in res:
            yield chunk
        return
    yield from res


def _iemapp_emit_telemetry(
    environ: dict,
    start_time: datetime,
    status_code: int,
) -> None:
    """Emit telemetry for an iemapp request."""
    end_time = datetime.now(timezone.utc)
    try:
        write_telemetry(
            TELEMETRY(
                timing=(end_time - start_time).total_seconds(),
                status_code=status_code,
                client_addr=environ.get("REMOTE_ADDR"),
                app=environ.get("SCRIPT_NAME"),
                request_uri=environ.get("REQUEST_URI"),
                vhost=environ.get("HTTP_HOST"),
                valid=end_time,
            )
        )
    except ValidationError:
        LOG.exception("Failed to write telemetry for request")


def _parse_status_code(status: str) -> int | None:
    """Parse integer HTTP status code from a WSGI status line."""
    # This could raise, but this should not be accounted for.
    return int(status.split()[0])


def _cache_control_header(
    environ: dict, cache_control: int | Callable | None
) -> tuple[str, str] | None:
    """Build a Cache-Control header, or None when caching is not wanted."""
    secs = cache_control(environ) if callable(cache_control) else cache_control
    if secs is None or secs <= 0:
        return None
    return ("Cache-Control", f"public, max-age={int(secs)}")


def _capture_start_response(start_response: Callable) -> tuple[Callable, dict]:
    """Wrap start_response and capture if it was called and status code.

    When ``state["cache_control"]`` holds a header tuple, it is added to a
    ``200`` response that does not already set Cache-Control.
    """
    state = {
        "started": False,
        "status_code": None,
        "cache_control": None,
    }

    def _wrapped_start_response(status, headers, exc_info=None):
        state["started"] = True
        state["status_code"] = _parse_status_code(status)
        header = state["cache_control"]
        if (
            header is not None
            and state["status_code"] == 200
            and not any(k.lower() == "cache-control" for k, _ in headers)
        ):
            headers = [*headers, header]
        if exc_info is None:
            return start_response(status, headers)
        return start_response(status, headers, exc_info)

    return _wrapped_start_response, state


def _iemapp_handle_exception(
    environ: dict,
    start_response: Callable,
    exp: Exception,
) -> tuple[int, bytes]:
    """Map exceptions to status code and user-facing payload."""
    if isinstance(exp, (IncompleteWebRequest, NoDataFound)):
        status_code = 422
        return status_code, _iemapp_error_response(
            environ,
            start_response,
            str(exp),
            routine=True,
            code=status_code,
        )
    if isinstance(exp, BadWebRequest):
        status_code = 422
        log_request(environ, multiplier=2)
        return status_code, _iemapp_error_response(
            environ,
            start_response,
            str(exp),
            code=status_code,
        )
    if isinstance(exp, NewDatabaseConnectionFailure):
        status_code = 503
        return status_code, _iemapp_error_response(
            environ,
            start_response,
            f"get_dbconn() failed with `{exp}`",
            code=status_code,
        )
    return 500, _iemapp_error_response(
        environ,
        start_response,
        traceback.format_exc(),
    )


def iemapp(**kwargs):
    """Opinionated processing of CGI GET variables for mod_wsgi apps.

    - A schema field name of `tz` is assumed to be destined to ZoneInfo usage.

    kwargs:
        - default_tz: The default timezone to use for timestamps, the default
          is ``America/Chicago``.
        - enable_telemetry: Enable telemetry logging, default ``True``.
        - help: Default help text, default ``Help not available``.
        - parse_times: Parse the form for timestamps, default ``True``.
        - schema (BaseModel): A Pydantic model to parse the form with. This has
          some requirements about how datetime fields and `tz` field name has
          special logic. See discussion below.
        - memcachekey (str or callable): A memcache key to use for caching
          the response. If the callable returns `None`, no caching is done.
        - memcacheexpire (int or callable): The number of seconds to cache
          the response, defaults to 3600.
        - content_type (str or callable): The content type to use for the
          response.
        - allowed_as_list (list): CGI parameters that are permitted to be
          lists.
        - ip_throttle_secs (float or callable): Number of seconds between
          requests from the same REMOTE_ADDR, 0 to disable,
          which is the default.
        - cache_control (int or callable): Seconds that clients and proxies
          may cache a ``200`` response, sent as
          ``Cache-Control: public, max-age=N``.  A callable gets the
          ``environ`` after schema parsing and may return ``None`` or ``0``
          to send no header for that request.  A ``Cache-Control`` header
          set by the application wins.  The default ``None`` sends nothing.

    What all this does:
        1) Attempts to catch database connection errors and handle nicely
        2) Updates `environ` with some auto-parsed values + form content.
        3) If the wrapped function returns a str or bytes, it will be encoded
           and made into a list for the WSGI response.

    Schema DateTime Handling
    ------------------------

    Best practice is to use `pydantic.AwareDatetime` and not be ambiguous. If
    you have a `tz` `CGIModel` field, it must have a default and so not be
    optional.  If you use a `datetime` and either have a `tz` defined or
    provided a kwargs `default_tz`, then magic will happen to assign in this
    timezone.

    Exception Raising
    -----------------

    The following Exception types raised within the mod_wsgi wrapped code will
    trigger the following HTTP status codes sent to the client.

        - `NoDataFound` or `IncompleteWebRequest` -> 422 Unprocessable Entity
        - `BadWebRequest` -> 422 Unprocessable Entity (also db logged...)
        - `NewDatabaseConnectionFailure` -> 503 Service Unavailable
        - Any other Exception -> 500 Internal Server Error
    """
    enable_telemetry = kwargs.get("enable_telemetry", True)
    ip_throttle_secs = kwargs.get("ip_throttle_secs", 0)
    memcachekey = kwargs.get("memcachekey")
    memcacheexpire = kwargs.get("memcacheexpire", 3600)
    content_type = kwargs.get("content_type", "application/json")
    cache_control = kwargs.get("cache_control")

    def _decorator(func):
        """Decorate a function to catch exceptions and do nice things."""

        def _wrapped(environ, start_response):
            """Decorate function."""

            start_time = datetime.now(timezone.utc)
            status_code = 500
            wrapped_start_response, response_state = _capture_start_response(
                start_response
            )
            try:
                short_circuit, payload = _iemapp_preflight(
                    environ,
                    wrapped_start_response,
                    kwargs,
                    ip_throttle_secs,
                )
                if short_circuit:
                    yield payload
                    return
                # Decided after preflight, so help and 429 replies get none
                response_state["cache_control"] = _cache_control_header(
                    environ, cache_control
                )
                res = _mcall(
                    func,
                    environ,
                    wrapped_start_response,
                    memcachekey,
                    memcacheexpire,
                    content_type,
                )
                # you know what assumptions do
                status_code = 200
                # Keep generator iteration in the try block so downstream
                # iteration exceptions are mapped by our exception handler.
                if inspect.isgenerator(res):
                    yield from _normalize_iemapp_response(res)
                    if enable_telemetry and not environ.get(
                        MEMCACHED_HIT, False
                    ):
                        _iemapp_emit_telemetry(
                            environ, start_time, status_code
                        )
                    return
            except NotImplementedError as exp:
                # This is a programming error that should not be handled here
                raise exp
            except Exception as exp:
                if response_state["started"]:
                    # Once streaming has started, we cannot safely restart
                    # the response with a new status/body.
                    LOG.exception(
                        "iemapp: exception raised after start_response. %s",
                        exp,
                    )
                    res = []
                    status_code = response_state["status_code"] or status_code
                else:
                    status_code, res = _iemapp_handle_exception(
                        environ,
                        wrapped_start_response,
                        exp,
                    )
            if enable_telemetry and not environ.get(MEMCACHED_HIT, False):
                _iemapp_emit_telemetry(
                    environ,
                    start_time,
                    response_state["status_code"] or status_code,
                )
            yield from _normalize_iemapp_response(res)

        return _wrapped

    return _decorator
