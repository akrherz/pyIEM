"""A utility to load matplotlib and set the backend to AGG

Example:
   from pyiem.plot.use_agg import plt
"""
import os

from pandas.plotting import register_matplotlib_converters
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt

# Workaround a pandas dataframe to matplotlib issue
register_matplotlib_converters()

# work around warning coming from pooch
if 'TEST_DATA_DIR' not in os.environ:
    os.environ['TEST_DATA_DIR'] = '/tmp'


def fontscale(ratio, fig=None):
    """Return a font size suitable for this NDC ratio.

    Args:
      ratio (float): value between 0 and 1
      fig (matplotlib.Figure,optional): The Figure of interest

    Returns:
      float: font size
    """
    if fig is None:
        fig = plt.gcf()
    bbox = fig.get_window_extent().transformed(
        fig.dpi_scale_trans.inverted()
    )
    return bbox.height * fig.dpi * ratio
