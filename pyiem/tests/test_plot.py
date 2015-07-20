import unittest
import numpy as np
from pyiem import plot
import datetime


class TestPlot(unittest.TestCase):

    def test_windrose(self):
        """Exercise the windrose code"""
        plot.windrose('AMW')
        self.assertEquals(1, 1)

    def test_colorramps(self):
        """make sure our colorramps are happy"""
        c = plot.james()
        self.assertEquals(c.N, 12)
        c = plot.james2()
        self.assertEquals(c.N, 12)
        c = plot.whitebluegreenyellowred()
        self.assertEquals(c.N, 236)

    def test_calendar(self):
        """See if we can make a calendar plot!"""
        import matplotlib.pyplot as plt
        sts = datetime.date(2015, 5, 1)
        ets = datetime.date(2015, 7, 1)
        data = dict()
        fig = plot.calendar_plot(sts, ets, data)
        self.assertTrue(isinstance(fig, plt.Figure))

    def test_overlap(self):
        """ Do some checking of our overlaps logic """
        m = plot.MapPlot(sector='midwest', axisbg='white')
        lons = np.linspace(-99, -90, 100)
        lats = np.linspace(38, 44, 100)
        vals = lats
        labels = ['%.2f' % (s,) for s in lats]
        m.plot_values(lons, lats, vals, fmt='%.2f', labels=labels)
        m.postprocess(filename='/tmp/test_plot_overlap.png')
        m.close()

    def test_barbs(self):
        """Testing the plotting of wind barbs"""
        m = plot.MapPlot(axisbg='white')
        data = [dict(lat=41.5, lon=-96, tmpf=50, dwpf=30, sknt=10, drct=100),
                dict(lat=42.0, lon=-95.5, tmpf=50, dwpf=30, sknt=20, drct=200),
                ]
        m.plot_station(data)
        m.postprocess(filename='/tmp/test_plot_barbs.png')
        m.close()

    def test_scatter(self):
        """ Test scatter plots """
        m = plot.MapPlot(sector='midwest')
        m.scatter(np.linspace(-99, -94, 100),
                  np.linspace(40, 45, 100), range(100), np.arange(0, 101, 10))
        m.postprocess(filename='/tmp/test_plot_scatter.png')
        m.close()

    def test_contourf(self):
        ''' Test the contourf plot with labels specified '''
        m = plot.MapPlot(sector='iowa')
        m.contourf(range(-94, -89), range(40, 45), range(5), range(5),
                   clevlabels=['a', 'b', 'c', 'd', 'e'])
        m.postprocess(filename='/tmp/test_plot_contourf.png')
        m.close()

    def test_textplot(self):
        ''' Can we plot text and place labels on them '''
        m = plot.MapPlot(sector='iowa')
        m.plot_values(range(-99, -94), range(40, 45), range(5))
        m.postprocess(filename='/tmp/test_plot_1.png')

        m = plot.MapPlot(sector='iowa')
        m.plot_values(range(-99, -94), range(40, 45), range(5),
                      labels=range(5, 11))
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
        m = plot.MapPlot(sector='nws', axisbg='white')
        m.fill_cwas({'DMX': 80, 'MKX': 5, 'SJU': 30, 'AJK': 40, 'HFO': 50},
                    units='NWS Something or Another')
        m.postprocess(filename='/tmp/us_plot_example.png')
        m.close()

    def test_plot3(self):
        """ Exercise climdiv plot API """
        m = plot.MapPlot(sector='iowa')
        m.fill_climdiv({'IAC001': 80, 'AKC003': 5, 'HIC003': 30,
                        'AJK': 40, 'HFO': 50})
        m.postprocess(filename='/tmp/iowa_climdiv_example.png')
        m.close()
