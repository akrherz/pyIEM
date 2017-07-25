"""Do tests please!"""
import unittest
import datetime

import numpy as np
from pyiem import plot
import matplotlib.colors as mpcolors
import cartopy.crs as ccrs


class TestPlot(unittest.TestCase):

    def test_illinois(self):
        """Produce a plot that doesn't suck"""
        mp = plot.MapPlot(sector='state', state='IL')
        mp.postprocess(filename="/tmp/test_plot_illinois.png")
        mp.close()

    def test_usdm(self):
        """Can we plot the current USDM"""
        mp = plot.MapPlot(sector='conus')
        mp.draw_usdm(hatched=True, filled=False)
        mp.postprocess(filename='/tmp/test_plot_usdm.png')
        mp.close()

    def test_pcolormesh(self):
        """See if we can do pcolormesh OKish"""
        m = plot.MapPlot(sector='custom', north=43, east=-80, west=-96,
                         south=38, projection=ccrs.AlbersEqualArea(),
                         continentalcolor='white')
        lons = np.arange(-100, -80, 0.25)
        lats = np.arange(40, 50, 0.25)
        vals = np.random.rand(lats.shape[0], lons.shape[0])
        lons, lats = np.meshgrid(lons, lats)
        m.pcolormesh(lons, lats, vals, np.arange(0, 1, 0.1))
        m.postprocess(filename='/tmp/test_plot_pcolormesh.png')
        m.close()

    def test_albers(self):
        """See if we can plot albers"""
        m = plot.MapPlot(sector='custom', north=43, east=-80, west=-96,
                         south=38, projection=ccrs.AlbersEqualArea(),
                         continentalcolor='white')
        m.postprocess(filename='/tmp/test_plot_albers.png')
        m.close()

    def test_centered_bins(self):
        """See that we can compute some nice centered bins"""
        a = plot.centered_bins(10, bins=9)
        self.assertEquals(a[0], -12)
        a = plot.centered_bins(55, bins=9)
        self.assertEquals(a[0], -56)
        a = plot.centered_bins(99, bins=9)
        self.assertEquals(a[0], -100)
        a = plot.centered_bins(0.9, bins=9)
        self.assertEquals(a[0], -0.9)

    def test_michigan(self):
        """See what we do with Michigan"""
        m = plot.MapPlot(sector='state', state='MI')
        m.contourf(range(-84, -75), range(36, 45), range(9), range(9),
                   clevlabels=['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i'])
        m.postprocess(filename='/tmp/test_plot_michigan.png')
        m.close()
        # self.assertTrue(1 == 2)

    def test_drawcities(self):
        """Fill the Iowa WFOs"""
        m = plot.MapPlot(title='Fill and Draw Cities', continentalcolor='blue',
                         sector='iowa')
        m.drawcities()
        m.postprocess(filename='/tmp/test_plot_drawcities.png')
        m.close()
        # self.assertTrue(1 == 2)

    def test_drawrandomtext(self):
        """See if we can handle the fun that is drawing random text"""
        m = plot.MapPlot(sector='iowa', title='Fun Text, here and there',
                         continentalcolor='white', debug=True)
        m.plot_values([-94, -92, -91, -92],
                      [42, 41, 43, 42.4],
                      ['One', 'Two\nTwo', 'Three\nThree\nThree',
                       'Four\nFour\nFour\nFour'], showmarker=True)
        m.postprocess(filename='/tmp/test_plot_drawrandom.png')
        m.close()
        # self.assertTrue(1 == 2)

    def test_drawiowawfo(self):
        """Fill the Iowa WFOs"""
        m = plot.MapPlot(sector='iowawfo', title='Fill Iowa WFOs')
        m.contourf(range(-94, -85), range(36, 45), range(9), range(9),
                   clevlabels=['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i'])
        m.postprocess(filename='/tmp/test_plot_iowawfo.png')
        m.close()

    def test_fillstates(self):
        """Can we fill states"""
        data = {'AK': 10, 'HI': 30, 'IA': 40, 'NY': 80}
        m = plot.MapPlot(sector='nws', title='Fill States')
        m.fill_states(data, ilabel=True)
        m.postprocess(filename='/tmp/test_plot_states.png')
        m.close()

    def test_drawcounties(self):
        """draw counties on the map"""
        m = plot.MapPlot(sector='midwest', title='Counties')
        m.drawcounties()
        m.postprocess(filename='/tmp/test_plot_counties.png')
        m.close()

    def test_climdiv(self):
        """Run tests agains the fill_climdiv"""
        m = plot.MapPlot(sector='conus', title="Climate Divisions")
        data = {'IAC001':  10, 'MNC001': 20, 'NMC001': 30}
        m.fill_climdiv(data, ilabel=True)
        m.postprocess(filename='/tmp/test_plot_climdiv.png')
        m.close()

    def test_colorbar(self):
        """Run tests against the colorbar algorithm"""
        mp = plot.MapPlot(sector='iowa', debug=True)
        cmap = plot.maue()
        clevs = range(0, 101, 10)
        norm = mpcolors.BoundaryNorm(clevs, cmap.N)
        mp.drawcities()
        mp.draw_colorbar(clevs, cmap, norm)
        mp.postprocess(filename='/tmp/test_plot_colorbar1.png')
        mp.close()

        mp = plot.MapPlot(sector='iowa')
        cmap = plot.maue()
        clevs = range(0, 101, 10)
        clevlabels = ["One", "Three", "Blahh", "Longest", "Five",
                      "Six", "Ten", "Fourty", 100000, "Hi\nHo", 100]
        norm = mpcolors.BoundaryNorm(clevs, cmap.N)
        mp.draw_colorbar(clevs, cmap, norm, clevlabels=clevlabels)
        mp.postprocess(filename='/tmp/test_plot_colorbar2.png')
        mp.close()

        mp = plot.MapPlot(sector='iowa')
        cmap = plot.maue()
        clevs = range(0, 101, 1)
        norm = mpcolors.BoundaryNorm(clevs, cmap.N)
        mp.draw_colorbar(clevs, cmap, norm, clevstride=10,
                         title="Erosion $kg/m^2$")
        mp.postprocess(filename='/tmp/test_plot_colorbar3.png')
        mp.close()

    def test_drawugcs(self):
        """test drawing of UGCS"""
        m = plot.MapPlot(sector='conus', title='Counties, 3 filled in Iowa')
        m.fill_ugcs({"IAC001": 10, "IAC003": 20, "IAC005": 30})
        m.postprocess(filename='/tmp/test_plot_ugcs_counties.png')
        m.close()
        m = plot.MapPlot(sector='iowa', title='Zones, 3 filled in Iowa, label')
        m.fill_ugcs({"IAZ001": 10, "IAZ003": 20, "IAZ005": 30}, ilabel=True)
        m.postprocess(filename='/tmp/test_plot_ugcs_zones.png')
        m.close()

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

    def test_colorramps(self):
        """make sure our colorramps are happy"""
        c = plot.james()
        self.assertEquals(c.N, 12)
        c = plot.james2()
        self.assertEquals(c.N, 12)
        c = plot.whitebluegreenyellowred()
        self.assertEquals(c.N, 236)
        c = plot.nwssnow()
        self.assertEquals(c.N, 11)

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
        m = plot.MapPlot(sector='midwest', continentalcolor='white')
        lons = np.linspace(-99, -90, 100)
        lats = np.linspace(38, 44, 100)
        vals = lats
        labels = ['%.2f' % (s,) for s in lats]
        m.plot_values(lons, lats, vals, fmt='%.2f', labels=labels)
        m.postprocess(filename='/tmp/test_plot_overlap.png')
        m.close()

    def test_barbs(self):
        """Testing the plotting of wind barbs"""
        m = plot.MapPlot(continentalcolor='white')
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
                    units='no units')
        m.postprocess(filename='/tmp/test_plot_midwest.png')
        m.close()

    def test_plot2(self):
        """ Exercise NWS plot API """
        m = plot.MapPlot(sector='nws', continentalcolor='white')
        m.fill_cwas({'DMX': 80, 'MKX': 5, 'SJU': 30, 'AJK': 40, 'HFO': 50},
                    units='NWS Something or Another', ilabel=True)
        m.postprocess(filename='/tmp/test_plot_us.png')
        m.close()

        m = plot.MapPlot(sector='iowa', continentalcolor='white')
        m.fill_cwas({'DMX': 80, 'MKX': 5, 'SJU': 30, 'AJK': 40, 'HFO': 50},
                    units='NWS Something or Another')
        m.postprocess(filename='/tmp/test_plot_iowa.png')
        m.close()

    def test_plot3(self):
        """ Exercise climdiv plot API """
        m = plot.MapPlot(sector='iowa')
        m.fill_climdiv({'IAC001': 80, 'AKC003': 5, 'HIC003': 30,
                        'AJK': 40, 'HFO': 50})
        m.postprocess(filename='/tmp/test_plot_iowa_climdiv.png')
        m.close()
