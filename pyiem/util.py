# -*- coding: utf-8 -*-
"""Utility functions for pyIEM package

This module contains utility functions used by various parts of the codebase.
"""
import time
import random
import logging
import datetime
import re
import warnings
import getpass
from socket import error as socket_error

import pytz
import psycopg2
import numpy as np
# NB We shall not be importing other parts of pyIEM here as we then get
# circular references.

SEQNUM = re.compile(r"\001?[0-9]{3}\s?")


def utc(year, month=1, day=1, hour=0, minute=0, second=0, microsecond=0):
    """Create a datetime instance with tzinfo=pytz.utc

    Returns:
      datetime with tzinfo set
    """
    return datetime.datetime(year, month, day, hour, minute, second,
                             microsecond).replace(tzinfo=pytz.utc)


def get_dbconn(dbname, user=None, host=None, port=5432):
    """Helper function with business logic to get a database connection

    Note that this helper could return a read-only database connection if the
    connection to the primary server fails.

    Args:
      dbname (str): the database name to connect to
      user (str,optional): hard coded user to connect as, default: current user
      host (str,optional): hard coded hostname to connect as, default: iemdb
      port (int,optional): the TCP port that PostgreSQL is listening
        defaults to 5432

    Returns:
      psycopg2 database connection
    """
    if user is None:
        user = getpass.getuser()
        # We hard code the apache user back to nobody, www-data is travis-ci
        if user in ['apache', 'www-data']:
            user = 'nobody'
    if host is None:
        host = "iemdb"
        if dbname == 'hads':
            host = "iemdb-hads"

    try:
        pgconn = psycopg2.connect(database=dbname, host=host, user=user,
                                  port=port, connect_timeout=15)
    except psycopg2.OperationalError as exp:
        warnings.warn("database connection failure: %s" % (exp, ))
        # as a stop-gap, lets try connecting to iemdb2
        pgconn = psycopg2.connect(database=dbname, host='iemdb2', user=user,
                                  port=port, connect_timeout=15)
    return pgconn


def noaaport_text(text):
    """Make whatever text look like it is NOAAPort Pristine

    Args:
      text (string): the inbound text
    Returns:
      text that looks noaaportish
    """
    # Convert to LFLFCR
    text = text.replace("\n", "\r\r\n").replace("\r\r\r\r", "\r\r")
    lines = text.split("\r\r\n")
    # remove any beginning empty lines
    while lines and lines[0] == '':
        lines.pop(0)

    # lime 0 should be start of product sequence
    if lines[0] != "\001":
        lines.insert(0, "\001")
    # line 1 should be the LDM sequence number 4 chars
    if not SEQNUM.match(lines[1]):
        if len(lines[1]) > 5:
            lines.insert(1, "000 ")
    # last line should be the control-c, by itself
    if lines[-1] != "\003":
        lines.append("\003")
    # Second line should not be blank
    if lines[1].strip() == 0:
        lines = [lines[0], ] + lines[2:]

    return "\r\r\n".join(lines)


def get_autoplot_context(fdict, cfg):
    """Get the variables out of a dict of strings

    This helper for IEM autoplot gets values out of a dictionary of strings,
    as provided by CGI.  It does some magic to get types right, defaults right
    and so on.  The typical way this is called

        ctx = iemutils.get_context(fdict, get_description())

    Args:
      fdict (dictionary): what was likely provided by `cgi.FieldStorage()`
      cfg (dictionary): autoplot value of get_description
    Returns:
      dictionary of variable names and values, with proper types!
    """
    ctx = {}
    for opt in cfg.get('arguments', []):
        name = opt.get('name')
        default = opt.get('default')
        typ = opt.get('type')
        minval = opt.get('min')
        maxval = opt.get('max')
        optional = opt.get('optional', False)
        value = fdict.get(name)
        if optional and value is None and typ not in ['vtec_ps']:
            continue
        if typ in ['station', 'zstation', 'sid', 'networkselect']:
            # A bit of hackery here if we have a name ending in a number
            netname = "network%s" % (name[-1] if name[-1] != 'n' else '',)
            ctx[netname] = fdict.get(netname)
            # The network variable tags along and within a non-PHP context,
            # this variable is unset, so we do some more hackery here
            if ctx[netname] is None:
                ctx[netname] = opt.get('network')
        elif typ in ['int', 'month', 'zhour', 'hour', 'day', 'year']:
            if value is not None:
                value = int(value)
            if default is not None:
                default = int(default)
        elif typ == 'float':
            if value is not None:
                value = float(value)
            if default is not None:
                default = float(default)
        elif typ == 'select':
            options = opt.get('options', dict())
            if value not in options:
                value = default
        elif typ == 'datetime':
            # tricky here, php has YYYY/mm/dd and CGI has YYYY-mm-dd
            if default is not None:
                default = datetime.datetime.strptime(default,
                                                     '%Y/%m/%d %H%M')
            if minval is not None:
                minval = datetime.datetime.strptime(minval,
                                                    '%Y/%m/%d %H%M')
            if maxval is not None:
                maxval = datetime.datetime.strptime(maxval,
                                                    '%Y/%m/%d %H%M')
            if value is not None:
                if value.find(" ") == -1:
                    value += " 0000"
                value = datetime.datetime.strptime(value, '%Y-%m-%d %H%M')
        elif typ == 'date':
            # tricky here, php has YYYY/mm/dd and CGI has YYYY-mm-dd
            if default is not None:
                default = datetime.datetime.strptime(default,
                                                     '%Y/%m/%d').date()
            if minval is not None:
                minval = datetime.datetime.strptime(minval,
                                                    '%Y/%m/%d').date()
            if maxval is not None:
                maxval = datetime.datetime.strptime(maxval,
                                                    '%Y/%m/%d').date()
            if value is not None:
                value = datetime.datetime.strptime(value, '%Y-%m-%d').date()
        elif typ == 'vtec_ps':
            # VTEC phenomena and significance
            for label in ['phenomena', 'significance']:
                label = label + name
                ctx[label] = fdict.get(label)
            continue
        # validation
        if minval is not None and value is not None and value < minval:
            value = default
        if maxval is not None and value is not None and value > maxval:
            value = default
        ctx[name] = value if value is not None else default
    return ctx


def exponential_backoff(func, *args, **kwargs):
    """ Exponentially backoff some function until it stops erroring

    Args:
      _ebfactor (int,optional): Optional scale factor, allowing for faster test
    """
    ebfactor = float(kwargs.pop('_ebfactor', 2))
    msgs = []
    for i in range(5):
        try:
            return func(*args, **kwargs)
        except socket_error as serr:
            msgs.append("%s/5 %s traceback: %s" % (i+1, func.__name__, serr))
            time.sleep((ebfactor ** i) + (random.randint(0, 1000) / 1000))
        except Exception as exp:
            msgs.append("%s/5 %s traceback: %s" % (i+1, func.__name__, exp))
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
        pgconn = get_dbconn('mesosite', user='nobody')
        cursor = pgconn.cursor()
    cursor.execute("""SELECT propname, propvalue from properties""")
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
    if drct > 360:
        return None
    text = None
    if drct >= 350 or drct < 13:
        text = "N"
    elif drct >= 13 and drct < 35:
        text = "NNE"
    elif drct >= 35 and drct < 57:
        text = "NE"
    elif drct >= 57 and drct < 80:
        text = "ENE"
    elif drct >= 80 and drct < 102:
        text = "E"
    elif drct >= 102 and drct < 127:
        text = "ESE"
    elif drct >= 127 and drct < 143:
        text = "SE"
    elif drct >= 143 and drct < 166:
        text = "SSE"
    elif drct >= 166 and drct < 190:
        text = "S"
    elif drct >= 190 and drct < 215:
        text = "SSW"
    elif drct >= 215 and drct < 237:
        text = "SW"
    elif drct >= 237 and drct < 260:
        text = "WSW"
    elif drct >= 260 and drct < 281:
        text = "W"
    elif drct >= 281 and drct < 304:
        text = "WNW"
    elif drct >= 304 and drct < 324:
        text = "NW"
    elif drct >= 324 and drct < 350:
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
    x0 = 0
    x1 = -1
    y0 = 0
    y1 = -1
    if len(lons.shape) == 1:
        # Do 1-d work
        (x0, x1) = np.digitize([bounds[0], bounds[2]], lons)
        (y0, y1) = np.digitize([bounds[1], bounds[3]], lats)
        szx = len(lons)
        szy = len(lats)
    else:
        # Do 2-d work
        diff = ((lons - bounds[0])**2 + (lats - bounds[1])**2)**0.5
        (lly, llx) = np.unravel_index(np.argmin(diff), lons.shape)
        diff = ((lons - bounds[2])**2 + (lats - bounds[3])**2)**0.5
        (ury, urx) = np.unravel_index(np.argmin(diff), lons.shape)
        diff = ((lons - bounds[0])**2 + (lats - bounds[3])**2)**0.5
        (uly, ulx) = np.unravel_index(np.argmin(diff), lons.shape)
        diff = ((lons - bounds[2])**2 + (lats - bounds[1])**2)**0.5
        (lry, lrx) = np.unravel_index(np.argmin(diff), lons.shape)
        x0 = min([llx, ulx])
        x1 = max([lrx, urx])
        y0 = min([lry, lly])
        y1 = max([uly, ury])
        (szy, szx) = lons.shape

    return [int(i) for i in [max([0, x0]), max([0, y0]), min([szx, x1]),
                             min([szy, y1])]]
