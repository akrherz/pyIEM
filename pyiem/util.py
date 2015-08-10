# -*- coding: utf-8 -*-
"""Utility functions for pyIEM package

This module contains utility functions used by various parts of the codebase.
"""
import psycopg2


def get_properties():
    """Fetch the properties set

    Returns:
      dict: a dictionary of property names and values (both str)
    """
    pgconn = psycopg2.connect(database='mesosite', host='iemdb')
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
