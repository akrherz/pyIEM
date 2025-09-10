# -*- coding: utf-8 -*-
# pylint: disable=unbalanced-tuple-unpacking
"""Utility functions for pyIEM package

This module contains utility functions used by various parts of the codebase.
"""

import logging
import os
import random
import re
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from html import escape

# !important
# Lazy import everything possible here, since this module is imported by
# most everything.
import httpx
import numpy as np  # used too many places

# NB: careful with circular imports!
from pyiem import database
from pyiem.exceptions import IncompleteWebRequest, UnknownStationException
from pyiem.network import Table as NetworkTable

# API compat
get_dbconn = database.get_dbconn
get_dbconnc = database.get_dbconnc
get_dbconnstr = database.get_dbconnstr
get_sqlalchemy_conn = database.get_sqlalchemy_conn

SEQNUM = re.compile(r"^[0-9]{3}\s?$")
# Setup a default logging instance for this module
LOG = logging.getLogger("pyiem")
LOG.addHandler(logging.NullHandler())
WFO_FOURCHAR = ["AFG", "GUM", "AFG", "HFO", "AFC", "AJK"]


class CustomFormatter(logging.Formatter):
    """A custom log formatter class."""

    def format(self, record):
        """Return a string!"""
        return (
            f"[{time.strftime('%H:%M:%S', time.localtime(record.created))} "
            f"{(record.relativeCreated / 1000.0):6.3f} "
            f"{record.filename}:{record.lineno} {record.funcName}] "
            f"{record.getMessage()}"
        )


def _strptime(ins: str, fmt: str, rectify: bool = False) -> datetime:
    """Wrapper around strptime."""
    # Forgive an encoded space
    ins = ins.replace("+", " ")
    try:
        return datetime.strptime(ins, fmt)
    except ValueError as exp:
        if rectify:
            return handle_date_err(exp, ins, fmt)
        raise IncompleteWebRequest(
            f"String provided: `{ins}` does not match format: `{fmt}`"
        ) from exp


def ddhhmm2datetime(ddhhmm: str, utcnow: datetime) -> datetime:
    """Do the nasty WMO header timestamp conversion."""
    wmo_day = int(ddhhmm[:2])
    wmo_hour = int(ddhhmm[2:4])
    wmo_minute = int(ddhhmm[4:])

    wmo_valid = utcnow.replace(
        hour=wmo_hour, minute=wmo_minute, second=0, microsecond=0
    )
    if wmo_day != utcnow.day:
        if wmo_day - utcnow.day == 1:  # Tomorrow
            wmo_valid = wmo_valid.replace(day=wmo_day)
        elif wmo_day > 25 and utcnow.day < 15:  # Previous month!
            wmo_valid = wmo_valid + timedelta(days=-10)
            wmo_valid = wmo_valid.replace(day=wmo_day)
        elif wmo_day < 5 and utcnow.day >= 15:  # next month
            wmo_valid = wmo_valid + timedelta(days=10)
            wmo_valid = wmo_valid.replace(day=wmo_day)
        else:
            wmo_valid = wmo_valid.replace(day=wmo_day)

    return wmo_valid


def web2ldm(url, ldm_product_name, md5_from_name=False, pqinsert="pqinsert"):
    """Download a URL and insert into LDM.

    Implements a common IEM workflow whereby a web resource is downloaded,
    saved to a temporary file, and then inserted into LDM.

    Args:
      url (str): Web resource to download.
      ldm_product_name (str): LDM product ID to use when inserting.
      md5_from_name (bool): Should `pqinsert -i` be used, which causes LDM
       to compute the MD5 value from the product name instead of data bytes.
      pqinsert (str): pqinsert command.

    Returns:
      bool - success of this workflow.
    """
    resp = httpx.get(url, timeout=60)
    if resp.status_code != 200:
        return False
    with tempfile.NamedTemporaryFile(mode="wb", delete=False) as tmp:
        tmp.write(resp.content)
    args = [pqinsert, "-p", ldm_product_name, tmp.name]
    if md5_from_name:
        args.insert(1, "-i")
    try:
        with subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ) as proc:
            stderr = proc.stderr.read()
        res = True
        if stderr != b"":
            LOG.info("pqinsert stderr result %s", stderr)
            res = False
    except FileNotFoundError:
        LOG.info("Failed to find `pqinsert` in $PATH")
        res = False

    os.unlink(tmp.name)
    return res


def load_geodf(dataname: str, epsg: int = 4326):
    """Load a given bundled GeoDataFrame.

    Args:
      dataname (str): The name of the dataset name to load.

    Returns:
      GeoDataFrame
    """
    import geopandas as gpd

    preproj = (
        f"/opt/miniconda3/pyiem_data/parquet/{epsg}/geodf/{dataname}.parquet"
    )
    if os.path.isfile(preproj):
        fn = preproj
    else:
        fn = os.path.join(
            os.path.dirname(__file__), "data", "geodf", f"{dataname}.parquet"
        )
    if not os.path.isfile(fn):
        LOG.info("load_geodf(%s) failed, file is missing!", fn)
        return gpd.GeoDataFrame()
    return gpd.read_parquet(fn)


def convert_value(val, units_in, units_out):
    """DRY Helper to return magnitude of a metpy unit conversion.

    Args:
      val (mixed): something with values.
      units_in (str): What units those values have.
      units_out (str): What values we want with given magnitude.

    Returns:
      mixed: magnitude of val with unit conversion applied
    """
    from metpy.units import masked_array, units

    return masked_array(val, units(units_in)).to(units(units_out)).m


def c2f(val):
    """Helper to return magnitude of Celcius to Fahrenheit conversion.

    Args:
      val (mixed): something with values in C

    Returns:
      val: something with values in F
    """
    return convert_value(val, "degC", "degF")


def mm2inch(val):
    """Helper to return magnitude of milimeters to inch conversion.

    Args:
      val (mixed): something with values in mm

    Returns:
      val: something with values in inch
    """
    return convert_value(val, "mm", "inch")


def html_escape(val):
    """Wrapper around cgi.escape deprecation."""
    return escape(val)


def get_test_filepath(name: str) -> str:
    """Helper to get a testing filename, full path."""
    return f"{os.getcwd()}/data/product_examples/{name}"


def get_test_file(name):
    """Helper to get data for test usage."""
    with open(get_test_filepath(name), "rb") as fp:
        return fp.read().decode("utf-8")


def logger(name="pyiem", level=None):
    """Get pyiem's logger with a stream handler attached.

    Args:
      name (str): The name of the logger to get, default pyiem
      level (logging.LEVEL): The log level for this pyiem logget, default is
        WARNING for non interactive sessions, INFO otherwise

    Returns:
      logger instance
    """
    ch = logging.StreamHandler()
    ch.setFormatter(CustomFormatter())
    log = logging.getLogger(name)
    log.addHandler(ch)
    if level is None and sys.stdout.isatty():
        level = logging.INFO
    log.setLevel(level if level is not None else logging.WARNING)
    return log


def find_ij(lons, lats, lon, lat):
    """Compute the i,j closest cell."""
    dist = ((lons - lon) ** 2 + (lats - lat) ** 2) ** 0.5
    (xidx, yidx) = np.unravel_index(dist.argmin(), dist.shape)
    return xidx, yidx


def ssw(mixedobj):
    """python23 wrapper for sys.stdout.write

    Args:
      mixedobj (str or bytes): what content we want to send
    """
    stdout = getattr(sys.stdout, "buffer", sys.stdout)
    if isinstance(mixedobj, str):
        stdout.write(mixedobj.encode("utf-8"))
    else:
        stdout.write(mixedobj)


def ncopen(ncfn, mode="r", timeout=60, _sleep=5):
    """Safely open netcdf files

    The issue here is that we can only have the following situation for a
    given NetCDF file.
    1.  Only 1 or more readers
    2.  Only 1 appender

    The netcdf is being accessed over NFS and perhaps local disk, so writing
    lock files is problematic.

    Args:
      ncfn (str): The netCDF filename
      mode (str,optional): The netCDF4.Dataset open mode, default 'r'
      timeout (int): The total time in seconds to attempt a read, default 60

    Returns:
      `netCDF4.Dataset` or `None`
    """
    import netCDF4

    if mode != "w" and not os.path.isfile(ncfn):
        raise IOError(f"No such file {ncfn}")
    sts = datetime.now(timezone.utc)
    nc = None
    while (datetime.now(timezone.utc) - sts).total_seconds() < timeout:
        try:
            nc = netCDF4.Dataset(ncfn, mode)
            nc.set_auto_scale(True)
            break
        except (OSError, IOError) as exp:
            LOG.debug(exp)
        time.sleep(_sleep)
    return nc


def utc(year=None, month=1, day=1, hour=0, minute=0, second=0, microsecond=0):
    """Create a datetime instance with tzinfo=timezone.utc

    When no arguments are provided, returns `datetime.now(timezone.utc)`.

    Returns:
      datetime with tzinfo set
    """
    if year is None:
        return datetime.now(timezone.utc)
    return datetime(
        year, month, day, hour, minute, second, microsecond
    ).replace(tzinfo=timezone.utc)


def noaaport_text(text):
    """Make whatever text look like it is NOAAPort Pristine

    Args:
      text (string): the inbound text
    Returns:
      text that looks noaaportish
    """
    # Rectify the text to remove any stray stuff
    text = text.replace("\003", "").replace("\001", "").replace("\r", "")
    # trim any right hand space
    lines = [x.rstrip() for x in text.split("\n")]
    # remove any beginning empty lines
    for pos in [0, -1]:
        while lines and lines[pos].strip() == "":
            lines.pop(pos)

    # lime 0 should be start of product sequence
    lines.insert(0, "\001")
    # line 1 should be the LDM sequence number 4 chars
    if not SEQNUM.match(lines[1]):
        if len(lines[1]) > 5:
            lines.insert(1, "000 ")
    else:
        lines[1] = f"{lines[1][:3]} "
    # last line should be the control-c, by itself
    lines.append("\003")

    return "\r\r\n".join(lines)


def handle_date_err(exp, value, fmt):
    """Attempt to fix up a date string, when possible."""
    if str(exp).find("day is out of range") == -1:
        raise exp
    tokens = value.split(" ")
    datepart = tokens[0]
    (yyyy, mm, _dd) = datepart.split("-")
    # construct a new month date and then substract one day
    lastday = (date(int(yyyy), int(mm), 15) + timedelta(days=20)).replace(
        day=1
    ) - timedelta(days=1)
    # Reconstruct the date string
    res = lastday.strftime("%Y-%m-%d")
    if len(tokens) > 1:
        res += " " + tokens[1]
    # Careful here, we don't want a recursive loop
    return _strptime(res, fmt, rectify=False)


def get_autoplot_context(fdict, cfg, enforce_optional=False, **kwargs):
    """Get the variables out of a dict of strings

    This helper for IEM autoplot gets values out of a dictionary of strings,
    as provided by CGI.  It does some magic to get types right, defaults right
    and so on.  The typical way this is called

        ctx = iemutils.get_context(fdict, get_description())

    Args:
      fdict (dictionary): what was likely provided by `cgi.FieldStorage()`
      cfg (dictionary): autoplot value of get_description
      enforce_optional (bool,optional): Should the `optional` flag be enforced
      rectify_dates (bool,optional): Attempt to fix common date errors like
        June 31.  Default `false`.

    Returns:
      dictionary of variable names and values, with proper types!
    """
    import matplotlib

    from pyiem.reference import state_names

    def _float(val):
        """Convert string to float, if possible."""
        try:
            return float(val)
        except ValueError as exp:
            raise IncompleteWebRequest(f"Invalid float value: {val}") from exp

    ctx = {}
    # Check for DPI setting
    val = fdict.get("dpi")
    if val is not None:
        ctx["dpi"] = int(val)
    # Check for internal params
    for key in filter(lambda x: x.startswith("_"), fdict.keys()):
        ctx[key] = html_escape(fdict[key])
    # Check over autoplot provided arguments
    for opt in cfg.get("arguments", []):
        name = opt.get("name")
        default = opt.get("default")
        typ = opt.get("type")
        minval = opt.get("min")
        maxval = opt.get("max")
        optional = opt.get("optional", False)
        value = fdict.get(name)
        # vtec_ps is special since we have special logic to get its value
        if (
            optional
            and typ != "vtec_ps"
            and (
                value is None
                or (enforce_optional and fdict.get(f"_opt_{name}") != "on")
            )
        ):
            continue
        if typ == "text":
            pattern = opt.get("pattern")
            if pattern is not None and not re.match(pattern, value):
                value = default
        elif typ in ["station", "zstation", "sid", "networkselect"]:
            # A bit of hackery here if we have a name ending in a number
            _n = name[-1] if name[-1] in ["1", "2", "3", "4", "5"] else ""
            netname = f"network{_n}"
            # The network variable tags along and within a non-PHP context,
            # this variable is unset, so we do some more hackery here
            ctx[netname] = fdict.get(netname, opt.get("network"))
            # Convience we load up the network metadata
            ntname = f"_nt{_n}"

            ctx[ntname] = NetworkTable(ctx[netname], only_online=False)
            # stations starting with _ are virtual and should not error
            if value is None:
                value = default
            if not value.startswith("_") and value not in ctx[ntname].sts:
                # HACK for three/four char ugliness
                if ctx[netname] == "WFO" and value in WFO_FOURCHAR:
                    value = f"P{value}"
                elif ctx[netname] == "WFO" and value in ["JSJ", "SJU"]:
                    value = "TJSJ"
                else:
                    raise UnknownStationException("Unknown station provided.")
            # A helper to remove downstream boilerplate
            sname = ctx[ntname].sts.get(value, {"name": f"(({value}))"})[
                "name"
            ]
            ctx[f"_sname{_n}"] = f"[{value}] {sname}"
        elif typ == "cmap":
            # Ensure that our value is a valid colormap known to matplotlib
            if value not in matplotlib.colormaps:
                value = default
        elif typ in ["int", "month", "zhour", "hour", "day", "year"]:
            if value is not None:
                value = int(_float(value))
            if default is not None:
                default = int(_float(default))
        elif typ == "float":
            if value is not None:
                value = _float(value)
            if default is not None:
                default = _float(default)
        elif typ == "state":
            if value is not None:
                value = value.upper()
            if value not in state_names and default is not None:
                value = default
        elif typ == "select":
            options = opt.get("options", {})
            # in case of multi, value could be a list
            if value is None:
                value = default
            elif isinstance(value, str):
                if value not in options:
                    value = default
                if opt.get("multiple"):
                    value = [value]
            else:
                value = [subval for subval in value if subval in options]
        elif typ == "datetime":
            # tricky here, php has YYYY/mm/dd and CGI has YYYY-mm-dd
            if value is not None and value.strip() == "":
                value = default
            if default is not None:
                default = _strptime(default, "%Y/%m/%d %H%M")
            if minval is not None:
                minval = _strptime(minval, "%Y/%m/%d %H%M")
            if maxval is not None:
                maxval = _strptime(maxval, "%Y/%m/%d %H%M")
            if value is not None:
                # A common problem is for the space to be missing
                if value.find(" ") == -1:
                    if len(value) == 14:
                        value = f"{value[:10]} {value[10:]}"
                    else:
                        value += " 0000"
                value = _strptime(
                    value[:15].replace("/", "-"),
                    "%Y-%m-%d %H%M",
                    rectify=kwargs.get("rectify_dates", False),
                )

        elif typ == "sday":
            # supports legacy uris with yyyy-mm-dd, before migration to sday
            if default is not None:
                default = _strptime(f"2000{default}", "%Y%m%d").date()
            if minval is not None:
                minval = _strptime(f"2000{minval}", "%Y%m%d").date()
            if maxval is not None:
                maxval = _strptime(f"2000{maxval}", "%Y%m%d").date()
            if value is not None:
                if value.find("-") > -1:
                    value = _strptime(value, "%Y-%m-%d").date()
                else:
                    value = _strptime(f"2000{value}", "%Y%m%d").date()

        elif typ == "date":
            # tricky here, php has YYYY/mm/dd and CGI has YYYY-mm-dd
            if default is not None:
                default = _strptime(default, "%Y/%m/%d").date()
            if minval is not None:
                minval = _strptime(minval, "%Y/%m/%d").date()
            if maxval is not None:
                maxval = _strptime(maxval, "%Y/%m/%d").date()
            if value is not None:
                value = _strptime(
                    value,
                    "%Y-%m-%d",
                    rectify=kwargs.get("rectify_dates", False),
                ).date()
        elif typ == "vtec_ps":
            # VTEC phenomena and significance
            defaults = {}
            # Only set a default value when the field is not optional
            if default is not None and not optional:
                tokens = default.split(".")
                if (
                    len(tokens) == 2
                    and len(tokens[0]) == 2
                    and len(tokens[1]) == 1
                ):
                    defaults["phenomena"] = tokens[0]
                    defaults["significance"] = tokens[1]
            for label in ["phenomena", "significance"]:
                label2 = label + name
                ctx[label2] = fdict.get(label2, defaults.get(label))
                # Prevent empty strings from being set
                if ctx[label2] is not None and ctx[label2] == "":
                    ctx[label2] = defaults.get(label)
            continue
        elif typ == "dat":
            # Damage Assessment Toolkit
            ctx["datglobalid"] = fdict.get("datglobalid")
        # validation
        if minval is not None and value is not None and value < minval:
            value = default
        if maxval is not None and value is not None and value > maxval:
            value = default
        ctx[name] = value if value is not None else default
    # Ensure defaults are set, if they exist
    for key in cfg.get("defaults", {}):
        if key not in ctx:
            ctx[key] = cfg["defaults"][key]
    return ctx


def exponential_backoff(func, *args, **kwargs):
    """Exponentially backoff some function until it stops erroring

    Args:
      _ebfactor (int,optional): Optional scale factor, allowing for faster test
    """
    ebfactor = float(kwargs.pop("_ebfactor", 5))
    msgs = []
    for i in range(5):
        try:
            return func(*args, **kwargs)
        except Exception as exp:
            msgs.append(f"{i + 1}/5 {func.__name__} traceback: {exp}")
            time.sleep(ebfactor * (random.randint(0, 1000) / 1000))
    logging.error("%s failure", func.__name__)
    logging.error("\n".join(msgs))
    return None


def delete_property(name, cursor=None):
    """Delete a property from the database.

    Args:
      name (str): The name of the property to delete
      cursor (psycopg2.cursor): Optional database cursor to use
    """
    if cursor is None:
        pgconn, _cursor = get_dbconnc("mesosite")
    else:
        _cursor = cursor
    _cursor.execute("DELETE from properties WHERE propname = %s", (name,))
    if cursor is None:
        pgconn.commit()
        pgconn.close()


def get_properties(cursor=None):
    """Fetch the properties set

    Returns:
      dict: a dictionary of property names and values (both str)
    """
    if cursor is None:
        pgconn, _cursor = get_dbconnc("mesosite")
    else:
        _cursor = cursor
    _cursor.execute("SELECT propname, propvalue from properties")
    res = {}
    for row in _cursor:
        res[row["propname"]] = row["propvalue"]
    if cursor is None:
        pgconn.close()
    return res


def set_property(name, value, cursor=None):
    """
    Set a property value in the database.

    Args:
      name (str): The name of the property to set
      value (str,datetime): The value to set
      cursor (psycopg2.cursor): Optional database cursor to use
    """
    from pyiem.reference import ISO8601

    if cursor is None:
        pgconn, _cursor = get_dbconnc("mesosite")
    else:
        _cursor = cursor
    # auto convert datetime to ISO8601 string
    if isinstance(value, datetime):
        value = value.strftime(ISO8601)
    _cursor.execute(
        "UPDATE properties SET propvalue = %s WHERE propname = %s",
        (value, name),
    )
    if _cursor.rowcount == 0:
        _cursor.execute(
            "INSERT into properties (propname, propvalue) VALUES (%s, %s)",
            (name, value),
        )
    if cursor is None:
        pgconn.commit()
        pgconn.close()


def drct2text(drct):
    """Convert an degree value to text representation of direction.

    Args:
      drct (int or float): Value in degrees to convert to text

    Returns:
      str: String representation of the direction, could be `None`

    """
    if drct is None:
        return None
    # Convert the value into a float
    drct = float(drct)
    if drct > 360 or drct < 0:
        return None
    text = None
    if drct >= 350 or drct < 13:
        text = "N"
    elif drct < 35:
        text = "NNE"
    elif drct < 57:
        text = "NE"
    elif drct < 80:
        text = "ENE"
    elif drct < 102:
        text = "E"
    elif drct < 127:
        text = "ESE"
    elif drct < 143:
        text = "SE"
    elif drct < 166:
        text = "SSE"
    elif drct < 190:
        text = "S"
    elif drct < 215:
        text = "SSW"
    elif drct < 237:
        text = "SW"
    elif drct < 260:
        text = "WSW"
    elif drct < 281:
        text = "W"
    elif drct < 304:
        text = "WNW"
    elif drct < 324:
        text = "NW"
    else:
        text = "NNW"
    return text


def grid_bounds(lons, lats, bounds):
    """Figure out indices that we can truncate big grid

    Args:
      lons (np.array): grid lons
      lats (np.array): grid lats
      bounds (list): [x0, y0, x1, y1]

    Returns:
      [x0, y0, x1, y1]
    """
    if len(lons.shape) == 1:
        # Do 1-d work
        (x0, x1) = np.digitize([bounds[0], bounds[2]], lons)
        (y0, y1) = np.digitize([bounds[1], bounds[3]], lats)
        szx = len(lons)
        szy = len(lats)
    else:
        # Do 2-d work
        diff = ((lons - bounds[0]) ** 2 + (lats - bounds[1]) ** 2) ** 0.5
        (lly, llx) = np.unravel_index(np.argmin(diff), lons.shape)
        diff = ((lons - bounds[2]) ** 2 + (lats - bounds[3]) ** 2) ** 0.5
        (ury, urx) = np.unravel_index(np.argmin(diff), lons.shape)
        diff = ((lons - bounds[0]) ** 2 + (lats - bounds[3]) ** 2) ** 0.5
        (uly, ulx) = np.unravel_index(np.argmin(diff), lons.shape)
        diff = ((lons - bounds[2]) ** 2 + (lats - bounds[1]) ** 2) ** 0.5
        (lry, lrx) = np.unravel_index(np.argmin(diff), lons.shape)
        x0 = min([llx, ulx])
        x1 = max([lrx, urx])
        y0 = min([lry, lly])
        y1 = max([uly, ury])
        (szy, szx) = lons.shape

    return [
        int(i)
        for i in [max([0, x0]), max([0, y0]), min([szx, x1]), min([szy, y1])]
    ]


@contextmanager
def archive_fetch(
    partialpath: str,
    localdir: str = "/mesonet/ARCHIVE/data",
    method: str = "get",
):
    """
    Helper to fetch a file from the archive, by first looking at the filesystem
    and then going to the website.  This returns a filename.  If a temporary
    file is created, it is deleted after the context manager exits.

    Args:
        partialpath (str): Typically a path that starts with /YYYY/mm/dd
        method (str): HTTP method to use, default 'get', in the case of head,
          we only check the existence and return an empty string if found.

    Returns:
        str: filename of the file found and available for use
    """
    # Ensure partialpath does not start with a /
    if partialpath.startswith("/"):
        partialpath = partialpath[1:]
    localfn = os.path.join(localdir, partialpath)
    if os.path.isfile(localfn):
        yield localfn
        return

    url = f"http://mesonet.agron.iastate.edu/archive/data/{partialpath}"

    tmp = None
    suffix = "." + os.path.basename(partialpath).split(".")[-1]
    try:
        resp = httpx.request(method.upper(), url, timeout=30)
        resp.raise_for_status()
        if method.lower() == "head":
            yield ""
            return
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(resp.content)
        yield tmp.name
        return
    except Exception as exp:
        LOG.info("archive_fetch(%s) failed: %s", url, exp)
        yield None
    finally:
        if tmp is not None:
            os.unlink(tmp.name)
