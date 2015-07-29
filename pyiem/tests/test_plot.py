import unittest
import numpy as np
from pyiem import plot
import datetime
import matplotlib.colors as mpcolors


class TestPlot(unittest.TestCase):

    def test_colorbar(self):
        """Run tests against the colorbar algorithm"""
        m = plot.MapPlot(sector='iowa')
        cmap = plot.maue()
        clevs = range(0, 101, 10)
        norm = mpcolors.BoundaryNorm(clevs, cmap.N)
        m.draw_colorbar(clevs, cmap, norm)
        m.postprocess(filename='/tmp/test_plot_colorbar1.png')
        m.close()

        m = plot.MapPlot(sector='iowa')
        cmap = plot.maue()
        clevs = range(0, 101, 1)
        norm = mpcolors.BoundaryNorm(clevs, cmap.N)
        m.draw_colorbar(clevs, cmap, norm, clevstride=10)
        m.postprocess(filename='/tmp/test_plot_colorbar2.png')
        m.close()

    def test_drawugcs(self):
        """test drawing of UGCS"""
        m = plot.MapPlot(sector='conus', title='Counties, 3 filled in Iowa')
        m.fill_ugcs({"IAC001": 10, "IAC003": 20, "IAC005": 30})
        m.postprocess(filename='/tmp/test_plot_ugcs_counties.png')
        m.close()
        m = plot.MapPlot(sector='iowa', title='Zones, 3 filled in Iowa')
        m.fill_ugcs({"IAZ001": 10, "IAZ003": 20, "IAZ005": 30})
        m.postprocess(filename='/tmp/test_plot_ugcs_zones.png')
        m.close()
        self.assertTrue(True)

    def test_filter_functions(self):
        """Make sure our filter functions are doing what we want!"""
        m = plot.MapPlot(sector='iowa')
        self.assertTrue(plot.state_filter(m, 'IAC001', dict()))
        self.assertTrue(not plot.state_filter(m, 'MNC001', dict()))
        m = plot.MapPlot(cwa='DMX')
        self.assertTrue(plot.state_filter(m, 'IAC001', dict()))

    def test_states(self):
        """Exercise the state plotting routines"""
        m = plot.MapPlot(sector='state', state='CA')
        m.postprocess(filename='/tmp/test_plot_CA.png')
        m.close()
        self.assertEquals(m.state, 'CA')

    def test_cwa(self):
        """Exercise the cwa plotting routines"""
        m = plot.MapPlot(sector='cwa', cwa='MKX')
        m.postprocess(filename='/tmp/test_plot_MKX.png')
        m.close()
        self.assertEquals(m.cwa, 'MKX')

    def test_windrose(self):
        """Exercise the windrose code"""
        plot.windrose('AMW22')
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
