"""Utilities for the Daily Erosion Project"""
import datetime

import pandas as pd

# The bounds of the climate files we store on disk and processing
SOUTH = 36.0
WEST = -104.0
NORTH = 49.0
EAST = -80.5


def read_cli(filename):
    """Read WEPP CLI File, Return DataFrame

    Args:
      filename (str): Filename to read

    Returns:
      pandas.DataFrame
    """
    rows = []
    dates = []
    lines = open(filename).readlines()
    linenum = 15
    while linenum < len(lines):
        (da, mo, year, breakpoints, tmax, tmin, rad, wvl, wdir,
         tdew) = lines[linenum].split()
        breakpoints = int(breakpoints)
        accum = 0
        times = []
        points = []
        for i in range(1, breakpoints + 1):
            (ts, accum) = lines[linenum + i].split()
            times.append(float(ts))
            points.append(float(accum))
        maxr = 0
        for i in range(1, len(times)):
            dt = times[i] - times[i-1]
            dr = points[i] - points[i-1]
            rate = (dr / dt)
            if rate > maxr:
                maxr = rate
        linenum += (breakpoints + 1)
        dates.append(datetime.date(int(year), int(mo), int(da)))
        rows.append({'tmax': float(tmax), 'tmin': float(tmin),
                     'rad': float(rad), 'wvl': float(wvl),
                     'wdir': float(wdir), 'tdew': float(tdew),
                     'maxr': maxr, 'bpcount': breakpoints,
                     'pcpn': float(accum)})

    return pd.DataFrame(rows, index=pd.DatetimeIndex(dates))


def read_env(filename, year0=2006):
    """Read WEPP .env file, return a dataframe

    Args:
      filename (str): Filename to read
      year0 (int,optional): The simulation start year minus 1

    Returns:
      pd.DataFrame
    """
    df = pd.read_table(filename,
                       skiprows=3, index_col=False, delim_whitespace=True,
                       header=None, na_values=['*******', '******'],
                       names=['day', 'month', 'year', 'precip', 'runoff',
                              'ir_det', 'av_det', 'mx_det', 'point',
                              'av_dep', 'max_dep', 'point2', 'sed_del',
                              'er'])
    if len(df.index) == 0:
        df['date'] = None
    else:
        # Faster than +=
        df['year'] = df['year'] + year0
        # Considerably faster than df.apply
        df['date'] = pd.to_datetime(dict(year=df['year'], month=df['month'],
                                         day=df['day']))
    return df


def read_wb(filename):
    """Read a *custom* WEPP .wb file into Pandas Data Table"""
    df = pd.read_table(filename, delim_whitespace=True,
                       na_values=['*******', '******'])
    if len(df.index) == 0:
        df['date'] = None
    else:
        # Considerably faster than df.apply
        df['date'] = pd.to_datetime(df['year'].astype(str) + ' ' +
                                    df['jday'].astype(str), format='%Y %j')
    return df
