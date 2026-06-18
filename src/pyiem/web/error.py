"""Handle various errors coming from the IEM webfarm hosts."""

import re
from datetime import datetime, timezone

from sqlalchemy.engine import Connection

from pyiem.database import get_sqlalchemy_conn, sql_helper
from pyiem.templates.iem import TEMPLATE
from pyiem.util import utc
from pyiem.webutil import error_log

IEM_VHOSTS = [
    "mesonet.agron.iastate.edu",
    "iem.local",
    "www.mesonet.agron.iastate.edu",
    "mesonet1.agron.iastate.edu",
    "mesonet2.agron.iastate.edu",
    "mesonet3.agron.iastate.edu",
    "mesonet4.agron.iastate.edu",
]
COWIMG = "https://mesonet.agron.iastate.edu/images/cow404.jpg"
ARCHIVE_BASE_RE = re.compile(r"^/archive/data/(\d{4})/(\d{2})/(\d{2})/")
ARCHIVE_RE = re.compile(
    r"^/archive/data/(\d{4})/(\d{2})/(\d{2})/(.*)_(\d{8})_?(\d{2,4})"
)


def log_request(
    conn: Connection,
    uri: str,
    environ: dict,
    redirect_status: int,
):
    """Do some logging work."""
    snipped = f"{uri[:100]}...snipped" if len(uri) > 100 else uri
    # See mod_wsgi discussion on this
    remoteip = environ.get("REMOTE_ADDR")
    if redirect_status == 404:
        error_log(
            environ, f"404 {snipped} referer: {environ.get('HTTP_REFERER')}"
        )
    conn.execute(
        sql_helper(
            "INSERT into weblog(client_addr, uri, referer, http_status, "
            "x_forwarded_for, domain) VALUES (:addr, :url, :ref, :status, "
            ":xf, :domain)"
        ),
        {
            "addr": remoteip,
            "url": uri,
            "ref": environ.get("HTTP_REFERER"),
            "status": redirect_status,
            "xf": environ.get("HTTP_X_FORWARDED_FOR"),
            "domain": environ.get("HTTP_HOST"),
        },
    )
    conn.commit()


def application(environ: dict, start_response: callable) -> list[bytes]:
    """mod-wsgi handler."""
    redirect_status = int(environ.get("REDIRECT_STATUS", 404))
    http_host = environ.get("HTTP_HOST", "")
    is_iem = http_host in IEM_VHOSTS
    uri = environ.get("REQUEST_URI", "")

    # Some Web Map Service request landed here, so we attempt to help the
    # user out.
    if "=WMS" in uri:
        payload = (
            "This URL appears to be a Web Map Service request, which errored "
            "out.  Please review the documentation at "
            "https://mesonet.agron.iastate.edu/ogc/"
        )
        start_response("400 Bad Request", [("Content-type", "text/plain")])
        return [payload.encode()]

    # A specialized check for archive requests and attempt to help the
    # user out when they request files from the future.
    base_match = ARCHIVE_BASE_RE.match(uri)
    if base_match:
        m = ARCHIVE_RE.match(uri)
        if m:
            tstr = m.group(5) + m.group(6)
            fmt = "%Y%m%d%H%M" if len(tstr) == 12 else "%Y%m%d%H"
            ts = None
            try:
                ts = datetime.strptime(tstr, fmt).replace(tzinfo=timezone.utc)
            except Exception as exp:
                error_log(environ, f"Error parsing timestamp: {tstr} {exp}")
            if ts is not None and ts > utc():
                start_response(
                    "422 Unprocessable entity",
                    [("Content-type", "text/plain")],
                )
                return [
                    b"Please adjust your script to not request files "
                    b"from the future."
                ]
    else:
        try:
            with get_sqlalchemy_conn("mesosite", rw=True) as conn:
                log_request(conn, uri, environ, redirect_status)
        except Exception as exp:
            error_log(environ, f"log_request failed: {exp}")

    # 405s are naughty requests, which we punt them away
    if redirect_status == 405:
        start_response(
            "301 Moved Permanently",
            [
                (
                    "Location",
                    "https://iowamesonet.github.io/sorry/?mode=blocked",
                )
            ],
        )
        return [b"Moved Permanently"]

    # We should re-assert the HTTP status code that brought us here :/
    content = (
        "<h3>Requested file was not found</h3>"
        f'<img src="{COWIMG}" class="img img-responsive" alt="404 Cow" />'
    )
    ctx = {"title": "File Not Found (404)", "content": content}

    if is_iem:
        payload = TEMPLATE.render(ctx).encode("utf-8")
    else:
        payload = content.encode("utf-8")
    start_response("404 Not Found", [("Content-type", "text/html")])
    return [payload]
