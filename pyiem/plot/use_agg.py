"""A utility to load matplotlib and set the backend to AGG

Example:
   from pyiem.plot.use_agg import plt
"""
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
