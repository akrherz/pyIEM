"""Utilities for the Daily Erosion Project"""
import pandas as pd
import datetime

# The bounds of the climate files we store on disk and processing
SOUTH = 36.0
WEST = -104.0
NORTH = 49.0
EAST = -80.5


def read_cli(fn):
    """Read WEPP CLI File, Return DataFrame

    Args:
      fn (str): Filename to read

    Returns:
      pandas.DataFrame
    """
    rows = []
    dates = []
    lines = open(fn).readlines()
    linenum = 15
    while linenum < len(lines):
        (da, mo, year, breakpoints, tmax, tmin, rad, wvl, wdir,
         tdew) = lines[linenum].split()
        breakpoints = int(breakpoints)
        accum = 0
        t = []
        r = []
        for i in range(1, breakpoints + 1):
            (ts, accum) = lines[linenum + i].split()
            t.append(float(ts))
            r.append(float(accum))
        maxr = 0
        for i in range(1, len(t)):
            dt = t[i] - t[i-1]
            dr = r[i] - r[i-1]
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


def read_env(fn, year0=2006):
    """Read a WEPP .env file into Pandas Data Table"""
    df = pd.read_table(fn,
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
        df['date'] = pd.to_datetime(dict(year=df.year, month=df.month,
                                         day=df.day))
    return df
