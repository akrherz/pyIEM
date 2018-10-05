"""A utility to load matplotlib and set the backend to AGG

Example:
   from pyiem.plot.use_agg import plt
"""
import os

import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt

# work around warning coming from pooch
if 'TEST_DATA_DIR' not in os.environ:
    os.environ['TEST_DATA_DIR'] = '/tmp'
