import unittest

from pyiem import plot

class TestObservation(unittest.TestCase):
    
    def test_contourf(self):
        ''' Test the contourf plot with labels specified '''
        m = plot.MapPlot(sector='iowa')
        m.contourf(range(-99,-94), range(40,45), range(5), range(5),
                   clevlabels=['a','b', 'c', 'd', 'e'])
        m.postprocess(filename='/tmp/test_plot_contourf.png')
        m.close()
    
    def test_textplot(self):
        ''' Can we plot text and place labels on them '''
        m = plot.MapPlot(sector='iowa')
        m.plot_values(range(-99,-94), range(40,45), range(5))
        m.postprocess(filename='/tmp/test_plot_1.png')

        m = plot.MapPlot(sector='iowa')
        m.plot_values(range(-99,-94), range(40,45), range(5), 
                      labels=range(5,11))
        m.postprocess(filename='/tmp/test_plot_2.png')
        m.close()

    
    def test_plot(self):
        """ Exercise the API """
        m = plot.MapPlot(sector='midwest')
        m.fill_cwas({'DMX': 80, 'MKX': 5, 'SJU': 30, 'AJK': 40},
                    units='midwest')
        m.postprocess(filename='/tmp/midwest_plot_example.png')
        m.close()
        
    def test_plot2(self):
        """ Exercise NWS plot API """
        m = plot.MapPlot(sector='nws')
        m.fill_cwas({'DMX': 80, 'MKX': 5, 'SJU': 30, 'AJK': 40, 'HFO':50},
                    units='NWS Something or Another')
        m.postprocess(filename='/tmp/us_plot_example.png')
        m.close()

    def test_plot3(self):
        """ Exercise climdiv plot API """
        m = plot.MapPlot(sector='iowa')
        m.fill_climdiv({'IAC001': 80, 'AKC003': 5, 'HIC003': 30, 
                     'AJK': 40, 'HFO':50})
        m.postprocess(filename='/tmp/iowa_climdiv_example.png')
        m.close()
