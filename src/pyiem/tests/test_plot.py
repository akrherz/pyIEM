import unittest

from pyiem import plot

class TestObservation(unittest.TestCase):
    
    def test_plot(self):
        """ Exercise the API """
        m = plot.MapPlot(sector='midwest')
        m.fill_cwas({'DMX': 80, 'MKX': 5})
        m.postprocess(filename='/tmp/blah.png')