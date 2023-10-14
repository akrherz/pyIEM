"""Utility functions for iemwebfarm applications."""
import datetime
import random
import string
import sys
import traceback
import warnings
from zoneinfo import ZoneInfo

import nh3
from paste.request import parse_formvars

from pyiem.exceptions import (
    BadWebRequest,
    NewDatabaseConnectionFailure,
    NoDataFound,
)
from pyiem.util import get_dbconnc


def log_request(environ):
    """Log the request to database for future processing."""
    pgconn, cursor = get_dbconnc("mesosite")
    cursor.execute(
        "INSERT into weblog(client_addr, uri, referer, http_status) "
        "VALUES (%s, %s, %s, %s)",
        (
            environ.get("REMOTE_ADDR"),
            environ.get("REQUEST_URI"),
            environ.get("HTTP_REFERER"),
            404,
        ),
    )
    cursor.close()
    pgconn.commit()
    pgconn.close()


def compute_ts_from_string(form, key):
    """Convert a string to a timestamp."""
    # Support various ISO9660 formats
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
    return datetime.datetime(
        int(form.get(f"year{suffix}", form.get("year"))),
        int(form.get(f"month{suffix}", form.get("month"))),
        int(form.get(f"day{suffix}", form.get("day"))),
        int(form.get(f"hour{suffix}", 0)),
        int(form.get(f"day{suffix}", 0)),
        tzinfo=ZoneInfo(form.get("tz", "America/Chicago")),
    )


def add_to_environ(environ, form):
    """Build out some things auto-parsed from the request."""
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
    if "sts" in form:
        environ["sts"] = compute_ts_from_string(form, "sts")
    if "ets" in form:
        environ["ets"] = compute_ts_from_string(form, "ets")
    if "day1" in form and "sts" not in form:
        environ["sts"] = compute_ts(form, "1")
    if "day2" in form and "ets" not in form:
        environ["ets"] = compute_ts(form, "2")


def iemapp(**kwargs):
    """
    Attempts to do all kinds of nice things for the user and the developer.

    kwargs:
        - default_tz: The default timezone to use for timestamps

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

            def _handle_exp(errormsg, routine=False):
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
                    "500 Internal Server Error",
                    [("Content-type", "text/plain")],
                )
                return [msg.encode("ascii")]

            try:
                # mixed convers this to a regular dict
                form = parse_formvars(environ).mixed()
                if "tz" not in form:
                    form["tz"] = kwargs.get("default_tz", "America/Chicago")
                add_to_environ(environ, form)
                res = func(environ, start_response)
            except BadWebRequest as exp:
                log_request(environ)
                res = _handle_exp(str(exp))
            except NoDataFound as exp:
                res = _handle_exp(str(exp), routine=True)
            except NewDatabaseConnectionFailure as exp:
                res = _handle_exp(f"get_dbconn() failed with `{exp}`")
            except Exception:
                res = _handle_exp(traceback.format_exc())
            return res

        return _wrapped

    return _decorator
