"""Utilities for the Daily Erosion Project"""
import pandas as pd
import datetime

# The bounds of the climate files we store on disk and processing
SOUTH = 36.0
WEST = -104.0
NORTH = 49.0
EAST = -80.5


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
        df['year'] += year0
        # This fails on an emoty dataframe
        df['date'] = df[['year', 'month', 'day']].apply(
            lambda sx: datetime.date(*[int(s) for s in sx]), axis=1)
    return df
