"""A utility to load matplotlib and set the backend to AGG

Example:
   from pyiem.plot.use_agg import plt
"""
import os

from pandas.plotting import register_matplotlib_converters
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt  # noqa:  # pylint: disable

# Workaround a pandas dataframe to matplotlib issue
register_matplotlib_converters()

# work around warning coming from pooch
if 'TEST_DATA_DIR' not in os.environ:
    os.environ['TEST_DATA_DIR'] = '/tmp'
