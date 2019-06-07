"""Test plots made by pyiem.plot.geoplot"""
import datetime

import pytest
import matplotlib.colors as mpcolors
import numpy as np
from pyiem import reference
from pyiem import plot
from pyiem.plot import MapPlot, centered_bins


@pytest.mark.mpl_image_compare(tolerance=0.1)
def test_issue98_labelbar():
    """Sometimes our label bar sucks."""
    mp = MapPlot(
        title='Proportional Colorbar with some rotation',
        sector='iowa', nocaption=True)
    cmap = plot.maue()
    cmap.set_under('white')
    cmap.set_over('black')
    clevs = np.arange(0, 1., 0.1)
    clevs[-1] = 3.987654
    norm = mpcolors.BoundaryNorm(clevs, cmap.N)
    mp.plot_values(
        [-94, -92, -91, -92], [42, 41, 43, 42.4],
        ['0.5', '0.25', '1.0', '5.0'], color=cmap(norm([0.5, 0.25, 1.0, 5.0])),
        showmarker=True
    )
    mp.draw_colorbar(clevs, cmap, norm, spacing='proportional')
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=0.1)
def test_illinois():
    """Produce a plot that doesn't suck"""
    mp = MapPlot(sector='state', state='IL', nocaption=True)
    mp.draw_cwas()
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=0.7)
def test_usdm():
    """Can we plot the current USDM"""
    mp = MapPlot(sector='conus', nocaption=True)
    mp.draw_usdm(valid=datetime.date(2018, 5, 7), hatched=True, filled=False)
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=0.1)
def test_hexbin():
    """See if we can do hexbin OKish"""
    mp = MapPlot(sector='north_america', continentalcolor='white',
                 nocaption=True)
    lons = np.arange(-100, -80, 0.25)
    lats = np.arange(40, 50, 0.25)
    vals = np.linspace(0, 1, lats.shape[0] * lons.shape[0]
                       ).reshape([lats.shape[0], lons.shape[0]])
    lons, lats = np.meshgrid(lons, lats)
    mp.hexbin(lons.flatten(), lats.flatten(), vals.flatten(),
              np.arange(0, 1, 0.1), cmap='jet')
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=0.2)
def test_pcolormesh():
    """See if we can do pcolormesh OKish"""
    mp = MapPlot(sector='custom', north=43, east=-80, west=-96,
                 south=38, projection=reference.EPSG[2163],
                 continentalcolor='white', nocaption=True)
    lons = np.arange(-100, -80, 0.25)
    lats = np.arange(40, 50, 0.25)
    vals = np.linspace(0, 1, lats.shape[0] * lons.shape[0]
                       ).reshape([lats.shape[0], lons.shape[0]])
    lons, lats = np.meshgrid(lons, lats)
    mp.pcolormesh(lons, lats, vals, np.arange(0, 1, 0.1))
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=0.3)
def test_conus():
    """See if we can plot albers"""
    mp = MapPlot(sector='custom',
                        title='EPSG: 5070 Albers',
                        north=reference.CONUS_NORTH + 1,
                        east=reference.CONUS_EAST - 12,
                        west=reference.CONUS_WEST + 14,
                        south=reference.CONUS_SOUTH,
                        projection=reference.EPSG[5070],
                        continentalcolor='white', nocaption=True)
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=0.3)
def test_conus2():
    """Map the conus in LEA"""
    mp = MapPlot(sector='custom',
                 title='EPSG: 2163 Lambert Azimuthal Equal Area',
                 north=reference.CONUS_NORTH + 1,
                 east=reference.CONUS_EAST - 12,
                 west=reference.CONUS_WEST + 14,
                 south=reference.CONUS_SOUTH,
                 projection=reference.EPSG[2163],
                 continentalcolor='white', nocaption=True)
    return mp.fig


def test_centered_bins():
    """See that we can compute some nice centered bins"""
    a = centered_bins(10, bins=9)
    assert a[0] == -12
    a = centered_bins(55, bins=9)
    assert a[0] == -56
    a = centered_bins(99, bins=9)
    assert a[0] == -100
    a = centered_bins(0.9, bins=9)
    assert a[0] == -0.9


@pytest.mark.mpl_image_compare(tolerance=0.1)
def test_michigan():
    """See what we do with Michigan"""
    mp = MapPlot(sector='state', state='MI', nocaption=True)
    mp.contourf(np.arange(-84, -75), np.arange(36, 45), np.arange(9),
                np.arange(9),
                clevlabels=['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i'])
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=0.1)
def test_drawcities():
    """Draw Cities"""
    mp = MapPlot(title='Fill and Draw Cities',
                 subtitle="This is my subtitle",
                 continentalcolor='blue',
                 sector='iowa', nocaption=True)
    mp.drawcities()
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=0.1)
def test_drawrandomtext():
    """See if we can handle the fun that is drawing random text"""
    mp = MapPlot(sector='iowa', title='Fun Text, here and there',
                 continentalcolor='white', debug=True, nocaption=True)
    mp.plot_values([-94, -92, -91, -92],
                   [42, 41, 43, 42.4],
                   ['One', 'Two\nTwo', 'Three\nThree\nThree',
                   'Four\nFour\nFour\nFour'], showmarker=True)
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=0.2)
def test_drawiowawfo():
    """Iowa Contour Plot"""
    mp = MapPlot(sector='iowawfo', title='Iowa Contour plot', nocaption=True)
    mp.contourf(np.arange(-94, -85), np.arange(36, 45), np.arange(9),
                np.arange(9),
                clevlabels=['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i'])
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=0.3)
def test_fillstates():
    """Can we fill states"""
    data = {'AK': 10, 'HI': 30, 'IA': 40, 'NY': 80}
    mp = MapPlot(sector='nws', title='Fill AK, HI, IA, NY States',
                 subtitle='test_fillstates', nocaption=True)
    mp.fill_states(data, ilabel=True)
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=0.25)
def test_drawcounties():
    """draw counties on the map"""
    mp = MapPlot(sector='midwest', title='Counties', nocaption=True)
    mp.drawcounties()
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=0.25)
def test_drawcounties_cornbelt():
    """draw counties on the map"""
    mp = MapPlot(sector='cornbelt', title='Counties', nocaption=True)
    mp.drawcounties()
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=0.25)
def test_drawcounties_iailin():
    """draw IA IL IN masked"""
    mp = MapPlot(sector='iailin', title='Counties', nocaption=True)
    mp.contourf(
        np.arange(-94, -85), np.arange(36, 45), np.arange(9),
        np.arange(9),
        clevlabels=['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i']
    )
    mp.drawcounties()
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=1.)
def test_climdiv():
    """Run tests agains the fill_climdiv"""
    mp = MapPlot(sector='conus', title="Climate Divisions", nocaption=True)
    data = {'IAC001':  10, 'MNC001': 20, 'NMC001': 30}
    mp.fill_climdiv(data, ilabel=True)
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=0.1)
def test_colorbar():
    """Run tests against the colorbar algorithm"""
    mp = MapPlot(sector='iowa', nocaption=True)
    cmap = plot.maue()
    cmap.set_under('white')
    clevs = list(range(0, 101, 10))
    norm = mpcolors.BoundaryNorm(clevs, cmap.N)
    mp.drawcities()
    mp.draw_colorbar(clevs, cmap, norm)
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=0.1)
def test_colorbar2():
    """draw a colorbar"""
    mp = MapPlot(sector='iowa', nocaption=True)
    cmap = plot.maue()
    clevs = list(range(0, 101, 10))
    clevlabels = ["One", "Three", "Blahh", "Longest", "Five",
                  "Six", "Ten", "Fourty", 100000, "Hi\nHo", 100]
    norm = mpcolors.BoundaryNorm(clevs, cmap.N)
    mp.draw_colorbar(
        clevs, cmap, norm, clevlabels=clevlabels
    )
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=0.1)
def test_colorbar3():
    """draw another colorbar"""
    mp = MapPlot(sector='iowa', nocaption=True)
    cmap = plot.maue()
    cmap.set_over('black')
    clevs = [0, 100, 250, 500, 1000, 2000, 20000]
    norm = mpcolors.BoundaryNorm(clevs, cmap.N)
    mp.draw_colorbar(
        clevs, cmap, norm, title="Erosion $kg/m^2$", spacing='uniform'
    )
    return mp.fig


# as of writing, python2.7 failure tolerance of 1.45
@pytest.mark.mpl_image_compare(tolerance=1.6)
def test_drawugcs():
    """test drawing of UGCS"""
    mp = MapPlot(sector='conus', title='Counties, 3 filled in Iowa',
                 nocaption=True)
    mp.fill_ugcs({"IAC001": 10, "IAC003": 20, "IAC005": 30})
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=1.0)
def test_drawugcs2():
    """3 filled zones"""
    mp = MapPlot(sector='iowa', title='Zones, 3 filled in Iowa, label',
                 subtitle='test_drawugcs2',
                 nocaption=True)
    mp.fill_ugcs({"IAZ001": 10, "IAZ003": 20, "IAZ005": 30}, ilabel=True)
    return mp.fig


def test_filter_functions():
    """Make sure our filter functions are doing what we want!"""
    mp = MapPlot(sector='iowa')
    assert plot.state_filter(mp, b'IAC001', dict())
    assert not plot.state_filter(mp, b'MNC001', dict())
    mp = MapPlot(cwa='DMX')
    assert plot.state_filter(mp, b'IAC001', dict())


@pytest.mark.mpl_image_compare(tolerance=0.15)
def test_states():
    """Exercise the state plotting routines"""
    mp = MapPlot(sector='state', state='CA', nocaption=True)
    assert mp.state == 'CA'
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=0.1)
def test_cwa():
    """Exercise the cwa plotting routines"""
    mp = MapPlot(sector='cwa', cwa='MKX', nocaption=True)
    mp.contourf(np.arange(-94, -89), np.arange(40, 45),
                np.arange(5), np.arange(5),
                clevlabels=['a', 'b', 'c', 'd', 'e'])
    mp.draw_cwas()
    assert mp.cwa == 'MKX'
    return mp.fig


def test_colorramps():
    """make sure our colorramps are happy"""
    c = plot.james()
    assert c.N == 12
    c = plot.james2()
    assert c.N == 12
    c = plot.whitebluegreenyellowred()
    assert c.N == 236
    c = plot.nwssnow()
    assert c.N == 11


@pytest.mark.mpl_image_compare(tolerance=0.2)
def test_overlap():
    """ Do some checking of our overlaps logic """
    mp = MapPlot(sector='midwest', continentalcolor='white', nocaption=True)
    lons = np.linspace(-99, -90, 100)
    lats = np.linspace(38, 44, 100)
    vals = lats
    labels = ['%.2f' % (s,) for s in lats]
    mp.plot_values(lons, lats, vals, fmt='%.2f', labels=labels)
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=0.1)
def test_barbs():
    """Testing the plotting of wind barbs"""
    mp = MapPlot(continentalcolor='white', nocaption=True)
    data = [
        dict(lat=41.5, lon=-96, tmpf=50, dwpf=30, sknt=10, drct=100),
        dict(lat=42.0, lon=-95.5, tmpf=50, dwpf=30, sknt=20, drct=200),
    ]
    mp.plot_station(data, fontsize=12)
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=0.1)
def test_stationplot():
    """Testing the plotting of wind barbs"""
    mp = MapPlot(continentalcolor='white', nocaption=True)
    data = [
        dict(lat=41.5, lon=-96, tmpf=50, dwpf=30, id='BOOI4'),
        dict(lat=42.0, lon=-95.5, tmpf=50, dwpf=30, id='CSAI4'),
    ]
    mp.plot_station(data, fontsize=12)
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=0.2)
def test_scatter():
    """ Test scatter plots """
    mp = MapPlot(sector='midwest', title='Should see 100 dots',
                 subtitle='test_scatter', nocaption=True)
    mp.scatter(np.linspace(-99, -94, 100),
               np.linspace(40, 45, 100), np.arange(100),
               np.arange(0, 101, 10))
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=4)
def test_contourf():
    ''' Test the contourf plot with labels specified '''
    mp = MapPlot(sector='iowa', nocaption=True)
    mp.contourf(np.arange(-94, -89), np.arange(40, 45),
                np.arange(5), np.arange(5),
                clevlabels=['a', 'b', 'c', 'd', 'e'])
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=0.1)
def test_textplot():
    ''' Can we plot text and place labels on them '''
    mp = MapPlot(sector='iowa', nocaption=True)
    mp.plot_values(np.arange(-99, -94), np.arange(40, 45), np.arange(5))
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=0.1)
def test_textplot2():
    """plot values on a map"""
    mp = MapPlot(sector='iowa', nocaption=True)
    mp.plot_values(np.arange(-99, -94), np.arange(40, 45), np.arange(5),
                   labels=range(5, 11))
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=1.0)
def test_plot():
    """ Exercise the API """
    mp = MapPlot(sector='midwest', nocaption=True)
    mp.fill_cwas({'DMX': 80, 'MKX': 5, 'SJU': 30, 'AJK': 40},
                 units='no units')
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=1.0)
def test_plot2():
    """ Exercise NWS plot API """
    mp = MapPlot(sector='nws', continentalcolor='white', nocaption=True)
    mp.fill_cwas({'DMX': 80, 'MKX': 5, 'SJU': 30, 'AJK': 40, 'HFO': 50},
                 units='NWS Something or Another', ilabel=True)
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=0.63)
def test_plot22():
    """plot cwas that are filled"""
    mp = MapPlot(sector='iowa', continentalcolor='white', nocaption=True)
    mp.fill_cwas({'DMX': 80, 'MKX': 5, 'SJU': 30, 'AJK': 40, 'HFO': 50},
                 units='NWS Something or Another')
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=0.2)
def test_plot3():
    """ Exercise climdiv plot API """
    mp = MapPlot(sector='iowa', nocaption=True)
    mp.fill_climdiv({'IAC001': 80, 'AKC003': 5, 'HIC003': 30,
                     'AJK': 40, 'HFO': 50})
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=0.1)
def test_alaska():
    """See that Alaska plots nicely."""
    mp = MapPlot(sector='state', state='AK', nocaption=True)
    return mp.fig
