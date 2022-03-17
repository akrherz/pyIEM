"""Test plots made by pyiem.plot.geoplot"""
import datetime
import tempfile
import os
import copy

import pytest
import matplotlib.colors as mpcolors
import numpy as np
from shapely.geometry import Polygon

# Local
from pyiem import plot
from pyiem.dep import RAMPS
from pyiem.plot import (
    MapPlot,
    centered_bins,
    dep_erosion,
    pretty_bins,
    load_bounds,
    mask_outside_geom,
)
from pyiem.reference import TWITTER_RESOLUTION_INCH
from pyiem.util import utc

PAIN = 1.3  # how much do we care, sigh.


def test_exercise_usdm():
    """Test the various checks in the usdm method."""
    mp = MapPlot()
    mp.draw_usdm()
    mp.draw_usdm(utc())
    with pytest.warns(UserWarning) as _:
        assert mp.draw_usdm("qqq") is None
    assert mp.draw_usdm(utc(1980, 1, 1)) is None


def test_close():
    """Test that the close method works."""
    mp = MapPlot()
    mp.close()


def test_invalid_file():
    """Test that we don't error out on an invalid filename."""
    assert load_bounds("this shall not work") is None


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_axes_position():
    """Test control of the main axes position."""
    mp = MapPlot(
        nocaption=True,
        title="Small Axes",
        axes_position=[0.3, 0.3, 0.3, 0.3],
    )
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_fill_ugcs_year_label():
    """Test that we can control the format of the label shown."""
    mp = MapPlot(
        nocaption=True,
        title="All Years",
        apctx={"_r": "t"},  # piggy back a change to figure size
    )
    assert mp.fig.get_size_inches()[0] == TWITTER_RESOLUTION_INCH[0]
    data = {"IAC001": 2021, "IAC003": 2021.5}
    mp.fill_ugcs(data, ilabel=True, lblformat="%.0f")
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_china():
    """Test that we can draw china and not overlay any cwas."""
    mp = MapPlot(
        twitter=True,
        nocaption=True,
        sector="custom",
        south=13,
        north=55,
        east=100,
        west=70,
        title="China",
        apctx={"_r": "bogus"},  # this should be a noop
    )
    assert mp.fig.get_size_inches()[0] == TWITTER_RESOLUTION_INCH[0]
    mp.fill_climdiv({"bah": 7})
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=2)  # unknown python3.7 diff
def test_nws_sector_twitter_res():
    """Test that Hawaii does not overlap Florida for Twitter Res."""
    mp = MapPlot(
        twitter=True,
        nocaption=True,
        sector="nws",
        title="Don't hide Flo Rida",
    )
    mp.draw_cwas()
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_nashville():
    """Test that Benton County, TNC005 does not show for OHX."""
    mp = MapPlot(
        nocaption=True,
        sector="cwa",
        cwa="OHX",
        title="Don't show Benton County TN!",
    )
    mp.fill_ugcs({"TNC005": 10}, plotmissing=True)
    mp.draw_cwas()
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_plotmissing():
    """Test that we can plotmissing."""
    mp = MapPlot(
        nocaption=True,
        sector="cwa",
        cwa="FSD",
        title="Testing plotmissing",
    )
    mp.fill_climdiv({"IAC001": 10}, plotmissing=False)
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_fill_by_str():
    """Test that we can fill by string or dict."""
    mp = MapPlot(
        nocaption=True,
        sector="state",
        state="CA",
        title="Testing color provision",
    )
    mp.fill_climdiv({"CAC001": 10}, color="b", plotmissing=False)
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_fill_by_dict():
    """Test that we can fill by string or dict."""
    mp = MapPlot(
        nocaption=True,
        sector="state",
        state="CA",
        title="Testing color provision",
    )
    mp.fill_climdiv({"CAC001": 10}, color={"CAC001": "r"}, plotmissing=False)
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_issue374_pah():
    """Test drawing fire weather zones for Paducah."""
    mp = MapPlot(
        nocaption=True,
        sector="cwa",
        cwa="PAH",
        title="Paducah Fire Weather Zones including MOZ098 Shannon",
    )
    mp.fill_ugcs({"MOZ098": 10}, is_firewx=True)
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_memphis_cwa():
    """Test that we can draw a map with Memphis CWA.."""
    mp = MapPlot(
        nocaption=True,
        sector="cwa",
        cwa="MEG",
        title="Memphis including Hardin, TN TNZ092",
    )
    mp.fill_ugcs({"TNZ092": 10})
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_overlay_roadcond():
    """Test being able to plot Iowa Road Conditions."""
    mp = MapPlot(
        nocaption=True,
        apctx={"csector": "IA"},
        title="A long and long title that has no purpose but to test things",
    )
    mp.overlay_roadcond(utc(2021, 2, 4, 17))
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_overlay_nexrad():
    """Test being able to plot NEXRAD."""
    mp = MapPlot(
        nocaption=True,
        sector="conus",
        title="A long and long title that has no purpose but to test things",
    )
    mp.overlay_nexrad(utc(2021, 2, 9, 17))
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_overlay_nexrad_hawaii():
    """Test that we can plot nexrad over Hawaii."""
    mp = MapPlot(
        nocaption=True,
        sector="iowa",  # this gets overridden
        apctx={"csector": "HI"},
        title="A long and long title that has no purpose but to test things",
    )
    caxpos = [0.05, 0.05, 0.35, 0.015]
    mp.overlay_nexrad(utc(2021, 2, 9, 17), caxpos=caxpos)
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_overlay_nexrad_alaska():
    """Test that we can plot nexrad over Alaska."""
    mp = MapPlot(
        nocaption=True,
        sector="cwa",
        cwa="AJK",
        title="A long and long title that has no purpose but to test things",
    )
    mp.overlay_nexrad(utc(2021, 2, 9, 17))
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_overlay_nexrad_puerto_rico():
    """Test that we can plot nexrad over Puerto Rico."""
    mp = MapPlot(
        nocaption=True,
        sector="cwa",
        cwa="SJU",
        title="A long and long title that has no purpose but to test things",
    )
    mp.overlay_nexrad(utc(2021, 2, 9, 17))
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_conus_contour():
    """Test that a conus sector plot can generate a contour correctly."""
    mp = MapPlot(nocaption=True, sector="conus", twitter=True)
    mp.contourf(
        list(np.arange(-120, -47, 3)),
        np.arange(25, 50),
        np.arange(25),
        np.arange(25),
        clip_on=False,
    )
    mp.draw_mask(sector="conus")
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_iowa_contour_with_polygon_mask():
    """Test that we can mask with a single Polygon."""
    mp = MapPlot(nocaption=True, sector="iowa", twitter=True)
    mp.contourf(
        np.arange(-120, -47, 3),
        np.arange(25, 50),
        np.arange(25),
        np.arange(25),
        clip_on=False,
    )
    poly = Polygon([(-95, 40), (-95, 45), (-90, 45), (-90, 40)])
    mask_outside_geom(mp.panels[0], poly)
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_issue365_cape_cod():
    """Test that we don't mask out Cape Cod."""
    mp = MapPlot(nocaption=True, sector="cwa", cwa="BOX")
    mp.contourf(
        np.arange(-75, -66),
        np.arange(36, 45),
        np.arange(9),
        np.arange(9),
        clevlabels=["a", "b", "c", "d", "e", "f", "g", "h", "i"],
        clip_on=False,
    )
    mp.draw_mask(sector="conus")
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_issue217():
    """See what happens with our logo on very scaled figure."""
    mp = MapPlot(nocaption=True, figsize=(6.00, 3.35))
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_twitter_resolution():
    """Test that we get good plot domain when we want a twitter resolution."""
    mp = MapPlot(sector="conus", nocaption=True, twitter=True)
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN + 1)  # lots of bars
def test_issue98_labelbar():
    """Sometimes our label bar sucks."""
    mp = MapPlot(
        title="Proportional Colorbar with some rotation",
        sector="iowa",
        nocaption=True,
    )
    cmap = copy.copy(plot.maue())
    cmap.set_under("white")
    cmap.set_over("black")
    clevs = np.arange(0, 1.0, 0.1)
    clevs[-1] = 3.987654
    norm = mpcolors.BoundaryNorm(clevs, cmap.N)
    colors = cmap(norm([0.5, 0.25, 1.0, 5.0]))
    colors = [mpcolors.to_hex(c) for c in colors]
    mp.plot_values(
        [-94, -92, -91, -92],
        [42, 41, 43, 42.4],
        ["0.5", "0.25", "1.0", "5.0"],
        color=colors,
        showmarker=True,
    )
    mp.draw_colorbar(clevs, cmap, norm, spacing="proportional")
    return mp.fig


def test_savefile():
    """Can we properly save a file."""
    mp = MapPlot()
    tmpfd = tempfile.NamedTemporaryFile(delete=False)
    mp.postprocess(filename=tmpfd.name)
    assert os.path.isfile(tmpfd.name)


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_illinois():
    """Produce a plot that doesn't suck"""
    mp = MapPlot(sector="state", state="IL", nocaption=True)
    mp.draw_cwas()
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_issue292_nws_fill_ugcs():
    """Test that fill_ugcs works for nws sector view."""
    mp = MapPlot(sector="nws", title="Four Counties", nocaption=True)
    data = {"IAC001": 10, "AKC013": 20, "HIC001": 30, "PRC001": 40}
    mp.fill_ugcs(data)
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_fill_ugcs_color():
    """Provide an explicit color to fill_ugcs"""
    mp = MapPlot(
        sector="cwa", cwa="DMX", title="Three Counties", nocaption=True
    )
    data = {"IAC001": 10, "IAC003": 20, "IAC135": 30}
    fc = {"IAC001": "#FF0000", "IAC003": "black"}
    ec = {}
    mp.fill_ugcs(data, fc=fc, ec=ec, draw_colorbar=False)
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_dep():
    """Produce a plot with the DEP logo on it."""
    mp = MapPlot(sector="state", state="IA", nocaption=True, logo="dep")
    cmap = dep_erosion()
    norm = mpcolors.BoundaryNorm(RAMPS["english"][1], cmap.N)
    mp.draw_colorbar(RAMPS["english"][1], dep_erosion(), norm)
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=0.7)
def test_usdm():
    """Can we plot the current USDM"""
    mp = MapPlot(sector="conus", nocaption=True)
    mp.draw_usdm(valid=datetime.date(2018, 5, 7), hatched=True, filled=False)
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_usdm_filled():
    """Can we plot the USDM filled."""
    mp = MapPlot(sector="southwest", nocaption=True)
    mp.draw_usdm(valid=datetime.date(2018, 5, 7), hatched=False, filled=True)
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_hexbin():
    """See if we can do hexbin OKish"""
    mp = MapPlot(
        sector="north_america", continentalcolor="white", nocaption=True
    )
    lons = np.arange(-100, -80, 0.25)
    lats = np.arange(40, 50, 0.25)
    vals = np.linspace(0, 1, lats.shape[0] * lons.shape[0]).reshape(
        [lats.shape[0], lons.shape[0]]
    )
    lons, lats = np.meshgrid(lons, lats)
    mp.hexbin(
        lons.flatten(),
        lats.flatten(),
        vals.flatten(),
        np.arange(0, 1, 0.1),
        cmap="jet",
    )
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=10)  # Lots of one pixel diffs
def test_pcolormesh():
    """See if we can do pcolormesh OKish"""
    mp = MapPlot(
        sector="custom",
        north=43,
        east=-80,
        west=-96,
        south=38,
        continentalcolor="white",
        nocaption=True,
    )
    lons = np.arange(-100, -80, 0.25)
    lats = np.arange(40, 50, 0.25)
    vals = np.linspace(0, 1, lats.shape[0] * lons.shape[0]).reshape(
        [lats.shape[0], lons.shape[0]]
    )
    lons, lats = np.meshgrid(lons, lats)
    mp.pcolormesh(lons, lats, vals, np.arange(0, 1, 0.1))
    return mp.fig


def test_pretty_bins():
    """Test that we get nice pretty bins!"""
    a = pretty_bins(-1, 10)
    assert abs(a[-1] - 10.5) < 0.01


def test_centered_bins():
    """See that we can compute some nice centered bins"""
    a = centered_bins(10)
    assert a[0] == -10
    a = centered_bins(55)
    assert a[0] == -56
    a = centered_bins(99)
    assert a[0] == -100
    a = centered_bins(99, bins=9)
    assert a[0] == -99
    a = centered_bins(100, on=100)
    assert a[0] == 0
    a = centered_bins(0.9)
    assert abs(a[-1] - 1.2) < 0.001
    a = centered_bins(1.2888)
    assert abs(a[-1] - 1.6) < 0.001


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_michigan():
    """See what we do with Michigan"""
    mp = MapPlot(sector="state", state="MI", nocaption=True)
    mp.contourf(
        np.arange(-84, -75),
        np.arange(36, 45),
        np.arange(9),
        np.arange(9),
        clevlabels=["a", "b", "c", "d", "e", "f", "g", "h", "i"],
    )
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_drawcities():
    """Draw Cities"""
    mp = MapPlot(
        title="Fill and Draw Cities",
        subtitle="This is my subtitle",
        continentalcolor="blue",
        sector="iowa",
        nocaption=True,
    )
    mp.drawcities()
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_drawrandomtext():
    """See if we can handle the fun that is drawing random text"""
    mp = MapPlot(
        sector="iowa",
        title="Fun Text, here and there",
        continentalcolor="white",
        debug=True,
        nocaption=True,
    )
    lons = [-94, -92, -91, -92]
    lats = [42, 41, 43, 42.4]
    vals = ["One", "Two\nTwo", "Three\nThree\nThree", "Four\nFour\nFour\nFour"]
    # Add some cruft to exercise culling
    lons.extend([lons[-1]] * 500)
    lats.extend([lats[-1]] * 500)
    vals.extend([vals[-1]] * 500)
    mp.plot_values(lons, lats, vals, showmarker=True)
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_drawiowawfo():
    """Iowa Contour Plot"""
    mp = MapPlot(sector="iowawfo", title="Iowa Contour plot", nocaption=True)
    mp.contourf(
        np.arange(-94, -85),
        np.arange(36, 45),
        np.arange(9),
        np.arange(9),
        clevlabels=["a", "b", "c", "d", "e", "f", "g", "h", "i"],
    )
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_contourf_grid():
    """Test that contourf can handle a 2d grid"""
    mp = MapPlot(title="Iowa Contour plot", nocaption=True)
    x = np.arange(-94, -85)
    y = np.arange(36, 45)
    xx, yy = np.meshgrid(x, y)
    vals = xx
    mp.contourf(
        xx,
        yy,
        vals,
        np.arange(-94, -85),
        clevlabels=["a", "b", "c", "d", "e", "f", "g", "h", "i"],
        ilabel=True,
        iline=True,
    )
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_fillstates():
    """Can we fill states"""
    data = {"AK": 10, "HI": 30, "IA": 40, "NY": 80}
    mp = MapPlot(
        sector="nws",
        title="Fill AK, HI, IA, NY States",
        subtitle="test_fillstates",
        nocaption=True,
    )
    mp.fill_states(data, lblformat="%.0f", ilabel=True)
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_drawcounties():
    """draw counties on the map"""
    mp = MapPlot(
        apctx={"csector": "midwest"}, title="Counties", nocaption=True
    )
    mp.drawcounties()
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_drawcounties_cornbelt():
    """draw counties on the map"""
    mp = MapPlot(sector="cornbelt", title="Counties", nocaption=True)
    mp.drawcounties()
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_drawcounties_iailin():
    """draw IA IL IN masked"""
    mp = MapPlot(sector="iailin", title="Counties", nocaption=True)
    mp.contourf(
        np.arange(-94, -85),
        np.arange(36, 45),
        np.arange(9),
        np.arange(9),
        clevlabels=["a", "b", "c", "d", "e", "f", "g", "h", "i"],
    )
    mp.drawcounties()
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=1.0)
def test_climdiv():
    """Run tests agains the fill_climdiv"""
    mp = MapPlot(sector="conus", title="Climate Divisions", nocaption=True)
    data = {"IAC001": 10, "MNC001": 20, "NMC001": 30}
    mp.fill_climdiv(data, ilabel=True, lblformat="%.0f")
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_colorbar():
    """Run tests against the colorbar algorithm"""
    mp = MapPlot(sector="iowa", nocaption=True)
    cmap = copy.copy(plot.maue())
    cmap.set_under("white")
    clevs = list(range(0, 101, 10))
    norm = mpcolors.BoundaryNorm(clevs, cmap.N)
    mp.drawcities()
    mp.draw_colorbar(clevs, cmap, norm)
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_colorbar2():
    """draw a colorbar"""
    mp = MapPlot(sector="iowa", nocaption=True)
    cmap = plot.maue()
    clevs = list(range(0, 101, 10))
    clevlabels = [
        "One",
        "Three",
        "Blahh",
        "Longest",
        "Five",
        "Six",
        "Ten",
        "Fourty",
        100000,
        "Hi\nHo",
        100,
    ]
    norm = mpcolors.BoundaryNorm(clevs, cmap.N)
    mp.draw_colorbar(
        clevs, cmap, norm, clevlabels=clevlabels, extend="neither"
    )
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_colorbar3():
    """draw another colorbar"""
    mp = MapPlot(sector="iowa", nocaption=True)
    cmap = copy.copy(plot.maue())
    cmap.set_over("black")
    clevs = [0, 100, 250, 500, 1000, 2000, 20000]
    norm = mpcolors.BoundaryNorm(clevs, cmap.N)
    mp.draw_colorbar(
        clevs,
        cmap,
        norm,
        title="Erosion $kg/m^2$",
        spacing="uniform",
        extend="max",
    )
    return mp.fig


# as of writing, python2.7 failure tolerance of 1.45
@pytest.mark.mpl_image_compare(tolerance=1.6)
def test_drawugcs():
    """test drawing of UGCS"""
    mp = MapPlot(
        sector="conus", title="Counties, 3 filled in Iowa", nocaption=True
    )
    mp.fill_ugcs({"IAC001": 10, "IAC003": 20, "IAC005": 30})
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=1.0)
def test_drawugcs2():
    """3 filled zones"""
    mp = MapPlot(
        sector="iowa",
        title="Zones, 3 filled in Iowa, label",
        subtitle="test_drawugcs2",
        nocaption=True,
    )
    mydict = {"IAZ001": 10, "IAZ003": 20, "IAZ005": 30}
    mp.fill_ugcs(mydict, ilabel=True, lblformat="%.0f")
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_lwx_cities():
    """Test that cities plot in a reasonable spot."""
    mp = MapPlot(
        sector="cwa",
        cwa="LWX",
        title="DC should be where DC is",
        nocaption=True,
    )
    mp.drawcities()
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_ugcs_lwx():
    """Ensure that we can plot some counties in LWX CWA."""
    mp = MapPlot(
        sector="cwa",
        cwa="LWX",
        title="Two Maryland Counties",
        subtitle="test_ugcs_lwx",
        nocaption=True,
    )
    labels = {"MDC003": "MDC003", "MDC033": "MDC033"}
    mp.fill_ugcs(
        {"MDC003": 1, "MDC033": 40},
        bins=list(range(0, 101, 10)),
        labels=labels,
        ilabel=True,
        extend="min",
    )
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_ugcs_lwx_zones():
    """Ensure that we can plot some zones in LWX CWA."""
    mp = MapPlot(
        sector="cwa",
        cwa="LWX",
        title="Two Maryland zones (MDZ001, MDZ008) xfered to LWX",
        subtitle="test_ugcs_lwx",
        nocaption=True,
    )
    labels = {"MDZ001": "MDZ001", "MDZ008": "MDZ008"}
    mp.fill_ugcs(
        {"MDZ001": 1, "MDZ008": 40},
        bins=list(range(0, 101, 10)),
        labels=labels,
        ilabel=True,
        extend="min",
    )
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN + 1)  # lots of bars on plot
def test_ugcs_withcustomlabels():
    """Fill ugcs with provided labels."""
    mp = MapPlot(
        sector="iowa",
        title="Zones, 3 filled in Iowa, custom label",
        subtitle="test_drawugcs2",
        nocaption=True,
    )
    labels = {"IAZ001": "IAZ001", "IAZ003": "IAZ003"}
    bins = list(range(24))
    clevlabels = [""] * 24
    clevlabels[0] = "mid"
    clevlabels[12] = "noon"
    mp.fill_ugcs(
        {"IAZ001": 1, "IAZ003": 4, "IAZ005": 12},
        bins=bins,
        labels=labels,
        ilabel=True,
        clevstride=12,
        clevlabels=clevlabels,
        lblformat="%.0f",
        extend="neither",
    )
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_states():
    """Exercise the state plotting routines"""
    mp = MapPlot(sector="state", state="CA", nocaption=True)
    assert mp.state == "CA"
    return mp.fig


# high tolerance due to python2.7 issue I don't wish to deal with now.
@pytest.mark.mpl_image_compare(tolerance=4.0)
def test_cwa_with_custom_masking():
    """Exercise the cwa plotting routines"""
    mp = MapPlot(sector="cwa", cwa="DLH", nocaption=True)
    mp.contourf(
        np.arange(-94, -89),
        np.arange(45, 50),
        np.arange(5),
        np.arange(5),
        clevlabels=["a", "b", "c", "d", "e"],
        clip_on=False,
    )
    mp.draw_cwas()
    mp.draw_mask(sector="conus")
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_cwa():
    """Exercise the cwa plotting routines"""
    mp = MapPlot(sector="cwa", cwa="MKX", nocaption=True)
    mp.contourf(
        np.arange(-94, -89),
        np.arange(40, 45),
        np.arange(5),
        np.arange(5),
        clevlabels=["a", "b", "c", "d", "e"],
    )
    mp.draw_cwas()
    mp.drawcounties()
    assert mp.cwa == "MKX"
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
    """Do some checking of our overlaps logic"""
    mp = MapPlot(sector="midwest", continentalcolor="white", nocaption=True)
    lons = list(np.linspace(-99, -90, 100))
    lats = list(np.linspace(38, 44, 100))
    vals = list(lats)
    labels = [f"{s:.2f}" for s in lats]
    mp.plot_values(lons, lats, vals, fmt="%.2f", labels=labels)
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_barbs():
    """Testing the plotting of wind barbs"""
    mp = MapPlot(continentalcolor="white", nocaption=True)
    data = [
        dict(
            lat=41.5,
            lon=-96,
            tmpf=50,
            dwpf=30,
            sknt=10,
            drct=100,
            coverage=50,
        ),
        dict(lat=42.0, lon=-95.5, tmpf=50, dwpf=30, sknt=20, drct=200),
        dict(lat=42.0, lon=-95.5, tmpf=50, dwpf=30, sknt=20, drct=200),
    ]
    mp.plot_station(data, fontsize=12)
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_stationplot():
    """Testing the plotting of wind barbs"""
    mp = MapPlot(continentalcolor="white", nocaption=True)
    data = [
        dict(lat=41.5, lon=-96, tmpf=50, dwpf=30, id="BOOI4"),
        dict(lat=42.0, lon=-95.5, tmpf=50, dwpf=30, id="CSAI4"),
    ]
    mp.plot_station(data, fontsize=12)
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_scatter():
    """Test scatter plots"""
    mp = MapPlot(
        sector="midwest",
        title="Should see 100 dots",
        subtitle="test_scatter",
        nocaption=True,
    )
    mp.scatter(
        np.linspace(-99, -94, 100),
        np.linspace(40, 45, 100),
        np.arange(100),
        np.arange(0, 101, 10),
    )
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=4)
def test_contourf():
    """Test the contourf plot with labels specified"""
    mp = MapPlot(sector="iowa", nocaption=True)
    mp.contourf(
        np.arange(-94, -89),
        np.arange(40, 45),
        np.arange(5),
        np.arange(5),
        clevlabels=["a", "b", "c", "d", "e"],
    )
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_textplot():
    """Can we plot text and place labels on them"""
    mp = MapPlot(sector="iowa", nocaption=True)
    mp.plot_values(np.arange(-99, -94), np.arange(40, 45), np.arange(5))
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_textplot2():
    """plot values on a map"""
    mp = MapPlot(sector="iowa", nocaption=True)
    mp.plot_values(
        np.arange(-99, -94),
        np.arange(40, 45),
        np.arange(5),
        labels=range(5, 10),
    )
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=1.0)
def test_plot():
    """Exercise the API"""
    mp = MapPlot(sector="midwest", nocaption=True)
    # test the translation of JSJ to SJU
    mp.fill_cwas({"DMX": 80, "MKX": 5, "JSJ": 30, "AJK": 40}, units="no units")
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=1.0)
def test_plot2():
    """Exercise NWS plot API"""
    mp = MapPlot(sector="nws", continentalcolor="white", nocaption=True)
    mp.fill_cwas(
        {"DMX": 80, "MKX": 5, "SJU": 30, "AJK": 40, "HFO": 50, "GUM": 67},
        units="NWS Something or Another",
        ilabel=True,
        lblformat="%.0f",
    )
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_plot22():
    """plot cwas that are filled"""
    mp = MapPlot(sector="iowa", continentalcolor="white", nocaption=True)
    mp.fill_cwas(
        {"DMX": 80, "MKX": 5, "SJU": 30, "AJK": 40, "HFO": 50},
        units="NWS Something or Another",
        lblformat="%.0f",
    )
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_plot3():
    """Exercise climdiv plot API"""
    mp = MapPlot(sector="iowa", nocaption=True)
    mp.fill_climdiv(
        {"IAC001": 80, "AKC003": 5, "HIC003": 30, "AJK": 40, "HFO": 50}
    )
    return mp.fig


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_alaska():
    """See that Alaska plots nicely."""
    mp = MapPlot(sector="state", state="AK", nocaption=True)
    return mp.fig
