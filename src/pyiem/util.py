# -*- coding: utf-8 -*-
# pylint: disable=import-outside-toplevel,unbalanced-tuple-unpacking
"""Utility functions for pyIEM package

This module contains utility functions used by various parts of the codebase.
"""
from contextlib import contextmanager
import os
import sys
import time
import random
import logging
from datetime import timezone, datetime, date, timedelta
import re
import warnings
import getpass
from socket import error as socket_error
import subprocess
import tempfile

# third party
import psycopg2
from psycopg2.extensions import register_adapter, AsIs
import numpy as np
from metpy.units import units, masked_array
import requests
from sqlalchemy import create_engine

# NB: some third party stuff is expensive to import, so let us be lazy

# NB: We shall not be importing other parts of pyIEM here as we then get
# circular references.

SEQNUM = re.compile(r"^[0-9]{3}\s?$")
# Setup a default logging instance for this module
LOG = logging.getLogger("pyiem")
LOG.addHandler(logging.NullHandler())


def _addapt_num(val):
    """Take the value verbatim."""
    if not np.isnan(val):
        return AsIs(val)
    return AsIs("NULL")


register_adapter(np.float64, _addapt_num)
register_adapter(np.int64, _addapt_num)
register_adapter(float, _addapt_num)


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
    req = requests.get(url, timeout=60)
    if req.status_code != 200:
        return False
    tmp = tempfile.NamedTemporaryFile(mode="wb", delete=False)
    tmp.write(req.content)
    tmp.close()
    args = [pqinsert, "-p", ldm_product_name, tmp.name]
    if md5_from_name:
        args.insert(1, "-i")
    try:
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
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


def load_geodf(dataname):
    """Load a given bundled GeoDataFrame.

    Args:
      dataname (str): The name of the dataset name to load.

    Returns:
      GeoDataFrame
    """
    import geopandas as gpd

    datadir = os.sep.join([os.path.dirname(__file__), "data"])
    fn = f"{datadir}/geodf/{dataname}.parquet"
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
    fval = masked_array(val, units(units_in)).to(units(units_out)).m
    return fval


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
    from html import escape

    return escape(val)


def get_test_file(name, fponly=False, fnonly=False):
    """Helper to get data for test usage."""
    basedir = os.path.dirname(__file__)
    fn = f"{basedir}/../../data/product_examples/{name}"
    if fnonly:
        return fn
    fp = open(fn, "rb")
    if fponly:
        return fp
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


def get_twitter(screen_name):
    """Provide an authorized Twitter API Client

    Args:
      screen_name (str): The twitter user we are fetching creds for
    """
    import twython

    dbconn = get_dbconn("mesosite")
    cursor = dbconn.cursor()
    props = get_properties(cursor)
    # fetch the oauth saved creds
    cursor.execute(
        "select access_token, access_token_secret from iembot_twitter_oauth "
        "WHERE screen_name = %s",
        (screen_name,),
    )
    row = cursor.fetchone()
    dbconn.close()
    return twython.Twython(
        props["bot.twitter.consumerkey"],
        props["bot.twitter.consumersecret"],
        row[0],
        row[1],
    )


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


def ncopen(ncfn, mode="r", timeout=60):
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
    sts = datetime.utcnow()
    nc = None
    while (datetime.utcnow() - sts).total_seconds() < timeout:
        try:
            nc = netCDF4.Dataset(ncfn, mode)
            nc.set_auto_scale(True)
            break
        except (OSError, IOError):
            pass
        time.sleep(5)
    return nc


def utc(year=None, month=1, day=1, hour=0, minute=0, second=0, microsecond=0):
    """Create a datetime instance with tzinfo=timezone.utc

    When no arguments are provided, returns `datetime.utcnow()`.

    Returns:
      datetime with tzinfo set
    """
    if year is None:
        return datetime.utcnow().replace(tzinfo=timezone.utc)
    return datetime(
        year, month, day, hour, minute, second, microsecond
    ).replace(tzinfo=timezone.utc)


def get_dbconnstr(name, **kwargs) -> str:
    """Create a database connection string/URI.

    Args:
      name (str): the database name to connect to.
      **kwargs: any additional arguments to pass to psycopg2.connect
        user (str): the database user to connect as
        host (str): the database host to connect to
        port (int): the database port to connect to
    Returns:
      str
    """
    user = kwargs.get("user")
    if user is None:
        user = getpass.getuser()
        # We hard code the apache user back to nobody, www-data is travis-ci
        if user in ["apache", "www-data"]:
            user = "nobody"
        elif user == "akrherz":  # HACK for daryl's development, sigh
            user = "mesonet"
        elif user == "meteor_ldm":  # Another HACK
            user = "ldm"
    host = kwargs.get("host")
    if host is None:
        host = f"iemdb-{name}.local"
    port = kwargs.get("port")
    if port is None:
        port = 5432

    return (
        f"postgresql://{user}@{host}:{port}/{name}?"
        f"connect_timeout={kwargs.get('connect_timeout', 15)}&"
        f"gssencmode={kwargs.get('gssencmode', 'disable')}&"
    )


def get_dbconn(database="mesosite", user=None, host=None, port=5432, **kwargs):
    """Helper function with business logic to get a database connection

    Note that this helper could return a read-only database connection if the
    connection to the primary server fails.

    Args:
      database (str,optional): the database name to connect to.
        default: mesosite
      user (str,optional): hard coded user to connect as, default: current user
      host (str,optional): hard coded hostname to connect as,
        default: iemdb.local
      port (int,optional): the TCP port that PostgreSQL is listening
        defaults to 5432
      password (str,optional): the password to use.

    Returns:
      psycopg2 database connection
    """
    dsn = get_dbconnstr(database, user=user, host=host, port=port, **kwargs)
    attempt = 0
    while attempt < 3:
        attempt += 1
        try:
            return psycopg2.connect(dsn)
        except psycopg2.ProgrammingError as exp:
            warnings.warn(f"database connection failure: {exp}", stacklevel=2)
            if attempt == 3:
                raise exp
        except psycopg2.OperationalError as exp:
            if attempt == 3:
                raise exp
            warnings.warn(
                f"database connection failure: {exp}, trying again",
                stacklevel=2,
            )


@contextmanager
def get_sqlalchemy_conn(text, **kwargs):
    """An auto-disposing sqlalchemy context-manager helper.

    This is used for when we really do not want to manage having pools of
    database connections open.  So this isn't something that is fast!

    Args:
        text (str): the database to connect to, passed to get_dbconnstr
        **kwargs: any additional arguments to pass to get_dbconnstr
    """
    engine = create_engine(get_dbconnstr(text, **kwargs))
    try:
        # Unsure if this is trouble or not.
        with engine.connect() as conn:
            yield conn
    finally:
        engine.dispose()


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
    return datetime.strptime(res, fmt)


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
    ctx = {}
    # This quasi sucks
    for arg in ["dpi", "_r"]:
        val = fdict.get(arg)
        if val is not None:
            ctx[arg] = val if arg != "dpi" else int(val)
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
        if typ in ["station", "zstation", "sid", "networkselect"]:
            # A bit of hackery here if we have a name ending in a number
            _n = name[-1] if name[-1] in ["1", "2", "3", "4", "5"] else ""
            netname = f"network{_n}"
            # The network variable tags along and within a non-PHP context,
            # this variable is unset, so we do some more hackery here
            ctx[netname] = fdict.get(netname, opt.get("network"))
            # Convience we load up the network metadata
            ntname = f"_nt{_n}"
            from pyiem.network import Table as NetworkTable
            from pyiem.exceptions import NoDataFound

            ctx[ntname] = NetworkTable(ctx[netname], only_online=False)
            # stations starting with _ are virtual and should not error
            if value is None:
                value = default
            if not value.startswith("_") and value not in ctx[ntname].sts:
                raise NoDataFound("Station metadata unavailable.")
            # A helper to remove downstream boilerplate
            sname = ctx[ntname].sts.get(value, {"name": f"(({value}))"})[
                "name"
            ]
            ctx[f"_sname{_n}"] = f"[{value}] {sname}"

        elif typ in ["int", "month", "zhour", "hour", "day", "year"]:
            if value is not None:
                value = int(value)
            if default is not None:
                default = int(default)
        elif typ == "float":
            if value is not None:
                value = float(value)
            if default is not None:
                default = float(default)
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
                res = []
                for subval in value:
                    if subval in options:
                        res.append(subval)
                value = res
        elif typ == "datetime":
            # tricky here, php has YYYY/mm/dd and CGI has YYYY-mm-dd
            if default is not None:
                default = datetime.strptime(default, "%Y/%m/%d %H%M")
            if minval is not None:
                minval = datetime.strptime(minval, "%Y/%m/%d %H%M")
            if maxval is not None:
                maxval = datetime.strptime(maxval, "%Y/%m/%d %H%M")
            if value is not None:
                if value.find(" ") == -1:
                    value += " 0000"
                _dtfmt = "%Y-%m-%d %H%M"
                try:
                    value = datetime.strptime(value, "%Y-%m-%d %H%M")
                except ValueError as exp:
                    if kwargs.get("rectify_dates", False):
                        value = handle_date_err(exp, value, _dtfmt)
                    else:
                        # If we are not rectifying dates, we just raise the
                        # exception
                        raise

        elif typ == "date":
            # tricky here, php has YYYY/mm/dd and CGI has YYYY-mm-dd
            if default is not None:
                default = datetime.strptime(default, "%Y/%m/%d").date()
            if minval is not None:
                minval = datetime.strptime(minval, "%Y/%m/%d").date()
            if maxval is not None:
                maxval = datetime.strptime(maxval, "%Y/%m/%d").date()
            if value is not None:
                try:
                    value = datetime.strptime(value, "%Y-%m-%d").date()
                except ValueError as exp:
                    if kwargs.get("rectify_dates", False):
                        value = handle_date_err(exp, value, "%Y-%m-%d").date()
                    else:
                        # If we are not rectifying dates, we just raise the
                        # exception
                        raise
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
            continue
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
    ebfactor = float(kwargs.pop("_ebfactor", 2))
    msgs = []
    for i in range(5):
        try:
            return func(*args, **kwargs)
        except socket_error as serr:
            msgs.append(f"{i+1}/5 {func.__name__} traceback: {serr}")
            time.sleep((ebfactor ** i) + (random.randint(0, 1000) / 1000))
        except Exception as exp:
            msgs.append(f"{i+1}/5 {func.__name__} traceback: {exp}")
            time.sleep((ebfactor ** i) + (random.randint(0, 1000) / 1000))
    logging.error("%s failure", func.__name__)
    logging.error("\n".join(msgs))
    return None


def get_properties(cursor=None):
    """Fetch the properties set

    Returns:
      dict: a dictionary of property names and values (both str)
    """
    if cursor is None:
        pgconn = get_dbconn("mesosite", user="nobody")
        cursor = pgconn.cursor()
    cursor.execute("SELECT propname, propvalue from properties")
    res = {}
    for row in cursor:
        res[row[0]] = row[1]
    return res


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
