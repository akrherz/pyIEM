import unittest

from pyiem import plot

class TestObservation(unittest.TestCase):
    
    def test_plot(self):
        """ Exercise the API """
        m = plot.MapPlot(sector='midwest')
        m.fill_cwas({'DMX': 80, 'MKX': 5, 'SJU': 30, 'AJK': 40})
        m.postprocess(filename='/tmp/midwest_plot_example.png')
        
    def test_plot2(self):
        """ Exercise NWS plot API """
        m = plot.MapPlot(sector='nws')
        m.fill_cwas({'DMX': 80, 'MKX': 5, 'SJU': 30, 'AJK': 40, 'HFO':50})
        m.postprocess(filename='/tmp/us_plot_example.png')