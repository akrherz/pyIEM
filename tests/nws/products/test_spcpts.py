"""Unit Tests"""

import pytest

from pyiem.nws.products import parser
from pyiem.nws.products._outlook_util import debug_draw
from pyiem.nws.products.spcpts import (
    SPCPTS,
    THRESHOLD_ORDER,
    imgsrc_from_row,
    load_conus_data,
    str2multipolygon,
)
from pyiem.util import get_test_file, utc


def test_gh1156_cig():
    """Test the newly minted CIG thresholds."""
    prod = parser(
        get_test_file("SPCPTS/PTSDY1_gh1156.txt"),
        utcnow=utc(2025, 3, 15, 15),
    )
    outlook = prod.get_outlook("TORNADO", "CIG1", 1)
    assert outlook.geometry_layers.area > outlook.geometry.area
    outlook = prod.get_outlook("TORNADO", "CIG2", 1)
    assert outlook.geometry_layers.area > outlook.geometry.area
    outlook = prod.get_outlook("TORNADO", "CIG3", 1)
    assert outlook.geometry_layers.area == outlook.geometry.area


def test_d48_crosses_month():
    """Test that the right month is assigned to this."""
    prod = parser(
        get_test_file("SPCPTS/PTSD48_crosses.txt"),
        utcnow=utc(2015, 3, 30, 10),
    )
    for day in range(4, 9):
        outlookcollect = prod.get_outlookcollection(day)
        assert outlookcollect.issue.month == 4


def test_gh936_day3_20z():
    """Test that this gets a 20z cycle."""
    prod = parser(
        get_test_file("SPCPTS/PTSDY3_20z.txt"),
        utcnow=utc(2024, 8, 21),
    )
    assert prod.cycle == 20
    jmsgs = prod.get_jabbers("", "")
    assert jmsgs[-1][0].find("day3otlk_20240820_1930") > -1


def test_imgsrc():
    """Test the various combos, I guess."""
    row = {"product_issue": utc(), "cycle": -1}
    assert imgsrc_from_row(row) is None
    for cycle in [6, 7]:
        row["cycle"] = cycle
        for category in ["TORNADO", "CATEGORICAL"]:
            row["category"] = category
            for day in range(1, 9):
                row["day"] = day
                assert imgsrc_from_row(row) is not None


def test_220404_threshold_order():
    """Test that two terms are not missing from the lookup :("""
    assert "ENH" in THRESHOLD_ORDER
    assert "MDT" in THRESHOLD_ORDER


def test_invalid_awipsid():
    """Test that exception is raised when passed invalid AWIPS ID."""
    data = get_test_file("SPCPTS/PTSDY1_closed.txt")
    with pytest.raises(ValueError):
        SPCPTS(data.replace("PTSDY1", "XXXYYY"))


def test_get_invalid_outlook_day():
    """Test that we can accurately close off an unclosed polygon."""
    prod = parser(get_test_file("SPCPTS/PTSDY1_closed.txt"))
    assert prod.get_outlook("", "", -1) is None


def test_100606_closed():
    """Test that we can accurately close off an unclosed polygon."""
    prod = parser(get_test_file("SPCPTS/PTSDY1_closed.txt"))
    outlook = prod.get_outlook("CATEGORICAL", "TSTM", 1)
    assert abs(outlook.geometry_layers.area - 572.878) < 0.01


def test_130607_larger_than_conus():
    """Test that we do not yield a multipolygon larger than the CONUS."""
    # /products/outlook/archive/2013/day1otlk_20130607_1630.html
    prod = parser(get_test_file("SPCPTS/PTSDY1_conus.txt"))
    outlook = prod.get_outlook("CATEGORICAL", "TSTM", 1)
    assert abs(outlook.geometry_layers.area - 4.719) < 0.01


def test_issue246():
    """Test a segment that slightly leaks outside the CONUS."""
    prod = parser(get_test_file("SPCPTS/PTSDY2_greatlakes.txt"))
    outlook = prod.get_outlook("CATEGORICAL", "MRGL", 2)
    assert abs(outlook.geometry_layers.area - 165.72) < 0.01


def test_880324_largerslight():
    """Test that we discard a polygon that is larger than TSTM."""
    prod = parser(get_test_file("SPCPTS/PTSDY1_larger.txt"))
    outlook = prod.get_outlook("CATEGORICAL", "TSTM", 1)
    assert abs(outlook.geometry_layers.area - 340.537) < 0.01


def test_210501_multipolygon():
    """Test that we handle a polygon that gets clipped into two chunks."""
    # /products/outlook/archive/2021/day1otlk_20210501_1300.html
    prod = parser(get_test_file("SPCPTS/PTSDY1_multipoly.txt"))
    outlook = prod.get_outlook("CATEGORICAL", "TSTM", 1)
    assert abs(outlook.geometry_layers.area - 238.516) < 0.01


def test_debugdraw():
    """Test we can draw a segment."""
    load_conus_data()
    assert debug_draw(0, [[10, 10], [20, 20]]) is not None


def test_drawoutlooks():
    """Test that we can draw an outlook."""
    prod = parser(get_test_file("SPCPTS/PTSDY1_maine2.txt"))
    prod.draw_outlooks()


def test_issue466_maine2():
    """Test that we can handle this harry logic."""
    # /products/outlook/archive/2021/day1otlk_20210602_1300.html
    prod = parser(get_test_file("SPCPTS/PTSDY1_maine2.txt"))
    outlook = prod.get_outlook("CATEGORICAL", "TSTM", 1)
    assert abs(outlook.geometry_layers.area - 469.71) < 0.01


def test_210703_topoerror():
    """Test that we do not get an exception for this."""
    # /products/outlook/archive/2021/day1otlk_20210703_2000.html
    prod = parser(get_test_file("SPCPTS/PTSDY1_topo2.txt"))
    outlook = prod.get_outlook("CATEGORICAL", "TSTM", 1)
    assert abs(outlook.geometry_layers.area - 452.077) < 0.01


def test_210601_hole():
    """Test that we properly get a hole with the TSTM."""
    # /products/outlook/archive/2021/day1otlk_20210601_1300.html
    prod = parser(get_test_file("SPCPTS/PTSDY1_hole.txt"))
    outlook = prod.get_outlook("CATEGORICAL", "TSTM", 1)
    assert abs(outlook.geometry_layers.area - 315.286) < 0.01


def test_210601_last():
    """Test that the last polygon does not dangle in complex logic."""
    prod = parser(get_test_file("SPCPTS/PTSDY1_last.txt"))
    outlook = prod.get_outlook("CATEGORICAL", "TSTM", 1)
    assert abs(outlook.geometry_layers.area - 287.92) < 0.01


def test_210519_singlepoint():
    """Test that we handle when a single point is in the PTS."""
    prod = parser(get_test_file("SPCPTS/PTSDY2_single.txt"))
    outlook = prod.get_outlook("HAIL", "0.05", 2)
    assert abs(outlook.geometry_layers.area - 130.139) < 0.01


def test_890526_multi():
    """Test that we can process this PTS."""
    prod = parser(get_test_file("SPCPTS/PTSDY1_multi.txt"))
    outlook = prod.get_outlook("CATEGORICAL", "SLGT", 1)
    assert abs(outlook.geometry_layers.area - 111.132) < 0.01


def test_210501_day2_west_coast():
    """Test that we do not light up the west coast."""
    # https://.../products/outlook/archive/2021/day2otlk_20210501_1730.html
    prod = parser(get_test_file("SPCPTS/PTSDY2_canada.txt"))
    outlook = prod.get_outlook("CATEGORICAL", "TSTM", 2)
    assert abs(outlook.geometry_layers.area - 351.342) < 0.01


def test_210427_day1_west_coast():
    """Test that we do not light up the west coast."""
    # https://.../products/outlook/archive/2021/day1otlk_20210427_1630.html
    prod = parser(get_test_file("SPCPTS/PTSDY1_west.txt"))
    outlook = prod.get_outlook("CATEGORICAL", "TSTM", 1)
    assert abs(outlook.geometry_layers.area - 359.536) < 0.01


def test_210409_day2_invalid_geom():
    """Test why this outlook bombed for me."""
    prod = parser(get_test_file("SPCPTS/PTSDY2_invalid3.txt"))
    outlook = prod.get_outlook("CATEGORICAL", "TSTM", 2)
    assert abs(outlook.geometry_layers.area - 212.9588) < 0.01


def test_three():
    """Test for a three intersection."""
    prod = parser(get_test_file("SPCPTS/PTSDY1_three.txt"))
    outlook = prod.get_outlook("CATEGORICAL", "SLGT", 1)
    slghtall = outlook.geometry_layers.area
    slghtreal = outlook.geometry.area
    moderate = prod.get_outlook("CATEGORICAL", "MDT", 1)
    modreal = moderate.geometry_layers.area
    assert abs(slghtall - (slghtreal + modreal)) < 0.01


def test_sequence():
    """Test for a bad sequence of multipolygons."""
    prod = parser(get_test_file("SPCPTS/PTSDY1_sequence.txt"))
    outlook = prod.get_outlook("CATEGORICAL", "MDT", 1)
    assert abs(outlook.geometry_layers.area - 28.441) < 0.01


def test_badpoly3():
    """Test that we can get a slight risk from this."""
    prod = parser(get_test_file("SPCPTS/PTSDY1_badpoly3.txt"))
    outlook = prod.get_outlook("CATEGORICAL", "SLGT", 1)
    assert abs(outlook.geometry_layers.area - 14.532) < 0.01


def test_badpoly2():
    """Test that we can get a slight risk from this."""
    prod = parser(get_test_file("SPCPTS/PTSDY1_badpoly2.txt"))
    outlook = prod.get_outlook("CATEGORICAL", "SLGT", 1)
    assert abs(outlook.geometry_layers.area - 47.538) < 0.01


def test_badpoly():
    """Test that we don't get a bad polygon out of this."""
    prod = parser(get_test_file("SPCPTS/PTSDY1_badpoly.txt"))
    outlook = prod.get_outlook("CATEGORICAL", "TSTM", 1)
    assert abs(outlook.geometry_layers.area - 271.45) < 0.01


def test_nogeom4():
    """Test that we can get a slight risk from this."""
    prod = parser(get_test_file("SPCPTS/PTSDY2_nogeom4.txt"))
    outlook = prod.get_outlook("CATEGORICAL", "SLGT", 2)
    assert abs(outlook.geometry_layers.area - 31.252) < 0.01


def test_may3():
    """Test that we can do something with the may 3, 1999 PTS."""
    prod = parser(get_test_file("SPCPTS/PTSDY1_may3.txt"))
    assert prod is not None


def test_pfwfd2():
    """Test parsing of a fire weather data2 product."""
    text = get_test_file("SPCPTS/PFWFD2.txt")
    prod = parser(text)
    prod.get_jabbers("")
    assert prod.cycle == 18
    prod = parser(text.replace("0221 PM", "0721 AM"))
    assert prod.cycle == 8
    prod = parser(text.replace("0221 PM", "0821 AM"))
    assert prod.cycle == -1


@pytest.mark.parametrize("database", ["postgis"])
def test_cycle(dbcursor):
    """Test that we get the cycle right."""
    ans = None
    for i in [1, 3, 2]:  # Run out of order to test some canonical logic
        prod = parser(get_test_file(f"SPCPTS/PTSDY1_20Z_{i}.txt"))
        prod.sql(dbcursor)
        if i == 3:
            ans = prod.get_product_id()
    # Check that we have only one canonical and that it is the last prod
    dbcursor.execute(
        "SELECT product_id from spc_outlook where cycle = 20 and "
        "day = 1 and outlook_type = 'C' and expire = '2002-12-20 12:00+00'"
    )
    assert dbcursor.rowcount == 1
    assert dbcursor.fetchone()["product_id"] == ans


@pytest.mark.parametrize("database", ["postgis"])
def test_product_id_roundtrip(dbcursor):
    """Test that the product_id is persisted to the database."""
    spc = parser(get_test_file("SPCPTS/PTSDY1_maine.txt"))
    spc.sql(dbcursor)
    dbcursor.execute(
        "SELECT product_id from spc_outlooks where day = 1 and "
        "product_issue = '2017-06-19 05:56+00' and outlook_type = 'C'"
    )
    assert dbcursor.rowcount == 9
    assert dbcursor.fetchone()["product_id"] == spc.get_product_id()


def test_170619_maine():
    """Test that we don't light up all of Main for the slight."""
    # https://.../products/outlook/archive/2017/day1otlk_20170619_1200.html
    spc = parser(get_test_file("SPCPTS/PTSDY1_maine.txt"))
    outlook = spc.get_outlook("CATEGORICAL", "SLGT", 1)
    assert abs(outlook.geometry_layers.area - 49.058) < 0.01


def test_issue295_geometryfail():
    """Test that we can make a geometry out of this."""
    # https://.../products/outlook/archive/2020/day1otlk_20200926_1300.html
    s = (
        "45048223 44728372 45018571 44818788 44798832 44758914 "
        "44679048 44759155 45509260 46349268 46749220 47199029 "
        "47608787 47258575"
    )
    load_conus_data(utc(2020, 9, 26))
    res = str2multipolygon(s)
    assert abs(res.geoms[0].area - 21.0814) < 0.001


def test_200602_unpack():
    """Workaround a full failure, but this still fails :("""
    # https://.../products/outlook/archive/2020/day2otlk_20200602_1730.html
    spc = parser(get_test_file("SPCPTS/PTSDY2_unpack.txt"))
    outlook = spc.get_outlook("CATEGORICAL", "SLGT", 2)
    assert abs(outlook.geometry_layers.area - 78.7056) < 0.01


def test_200109_nogeoms():
    """Failed to parse some tricky line work south of New Orleans."""
    # https://.../products/outlook/archive/2020/day2otlk_20200109_1730.html
    spc = parser(get_test_file("SPCPTS/PTSDY2_nogeom3.txt"))
    outlook = spc.get_outlook("CATEGORICAL", "ENH", 2)
    assert abs(outlook.geometry_layers.area - 33.785) < 0.01


def test_190907_invalid():
    """Product hit geos issue."""
    # /products/outlook/archive/2019/day1otlk_20190907_1300.html
    spc = parser(get_test_file("SPCPTS/PTSDY1_190907.txt"))
    outlook = spc.get_outlook("CATEGORICAL", "TSTM", 1)
    assert abs(outlook.geometry_layers.area - 314.761) < 0.01


def test_190905_invalid():
    """Product hit geos issue."""
    spc = parser(get_test_file("SPCPTS/PTSDY1_geos.txt"))
    outlook = spc.get_outlook("CATEGORICAL", "TSTM", 1)
    assert abs(outlook.geometry_layers.area - 263.61) < 0.01


def test_190903_invalid():
    """Product hit invalid geometry error."""
    spc = parser(get_test_file("SPCPTS/PTSDY2_invalid2.txt"))
    outlook = spc.get_outlook("CATEGORICAL", "TSTM", 2)
    assert abs(outlook.geometry_layers.area - 343.74) < 0.01


def test_190801_shapely():
    """Product hit shapely assertion error."""
    spc = parser(get_test_file("SPCPTS/PTSDY1_shapelyerror.txt"))
    outlook = spc.get_outlook("CATEGORICAL", "TSTM", 1)
    assert abs(outlook.geometry_layers.area - 333.678) < 0.01


def test_190625_nogeom2():
    """This hit some error that we need to debug."""
    spc = parser(get_test_file("SPCPTS/PTSDY2_nogeom2.txt"))
    outlook = spc.get_outlook("CATEGORICAL", "SLGT", 2)
    assert abs(outlook.geometry_layers.area - 11.59) < 0.01


def test_190527_canada():
    """SPC Updated marine bounds."""
    # https://.../products/outlook/archive/2019/day1otlk_20190528_0100.html
    spc = parser(get_test_file("SPCPTS/PTSDY1_canada.txt"))
    outlook = spc.get_outlook("CATEGORICAL", "MRGL", 1)
    assert abs(outlook.geometry_layers.area - 118.229) < 0.01


def test_190515_issue117_month():
    """Product crossing year causes grief."""
    spc = parser(get_test_file("SPCPTS/PTSDY2_month.txt"))
    collect = spc.get_outlookcollection(2)
    assert collect.expire == utc(2019, 5, 2, 12)


def test_190509_marinebounds():
    """SPC Updated marine bounds."""
    spc = parser(get_test_file("SPCPTS/PTSDY1_marine.txt"))
    outlook = spc.get_outlook("HAIL", "0.15", 1)
    assert abs(outlook.geometry_layers.area - 17.82) < 0.01


def test_190415_elevated():
    """Can we parse elevated threshold firewx?"""
    spc = parser(get_test_file("SPCPTS/PFWFD1_example.txt"))
    spc.get_jabbers("")
    outlook = spc.get_outlook("FIRE WEATHER CATEGORICAL", "ELEV", 1)
    assert abs(outlook.geometry_layers.area - 145.64) < 0.01
    for level in ["IDRT", "SDRT", "ELEV", "CRIT", "EXTM"]:
        outlook = spc.get_outlook("FIRE WEATHER CATEGORICAL", level, 1)
        assert outlook is not None


def test_180807_idx1_idx2():
    """This Day1 generated an error."""
    spc = parser(get_test_file("SPCPTS/PTSDY1_idx1_idx2.txt"))
    outlook = spc.get_outlook("WIND", "0.05", 1)
    assert abs(outlook.geometry_layers.area - 37.83) < 0.02


@pytest.mark.parametrize("database", ["postgis"])
def test_170926_largeenh(dbcursor):
    """This Day1 generated a massive ENH"""
    spc = parser(get_test_file("SPCPTS/PTSDY1_bigenh.txt"))
    spc.sql(dbcursor)
    # Do twice to force a deletion
    spc.sql(dbcursor)
    outlook = spc.get_outlook("CATEGORICAL", "ENH", 1)
    assert abs(outlook.geometry_layers.area - 17.50) < 0.01


def test_170703_badday3link():
    """Day3 URL is wrong"""
    spc = parser(get_test_file("SPCPTS/PTSDY3.txt"))
    jdict = spc.get_jabbers("", "")
    ans = (
        "The Storm Prediction Center issues Day 3 "
        "Convective Outlook at Nov 19, 8:31z "
        "https://www.spc.noaa.gov/products/outlook/archive/2013/"
        "day3otlk_20131119_0830.html"
    )
    assert jdict[-1][0] == ans


@pytest.mark.parametrize("database", ["postgis"])
def test_170612_nullgeom(dbcursor):
    """See why this has an error with null geom reported"""
    spc = parser(get_test_file("SPCPTS/PTSD48_nullgeom.txt"))
    spc.sql(dbcursor)
    outlook = spc.get_outlook("ANY SEVERE", "0.15", 4)
    assert abs(outlook.geometry_layers.area - 56.84) < 0.01


def test_170522_nogeom():
    """See why this has an error with no-geom reported"""
    spc = parser(get_test_file("SPCPTS/PTSDY1_nogeom2.txt"))
    outlook = spc.get_outlook("TORNADO", "0.02", 1)
    assert abs(outlook.geometry_layers.area - 2.90) < 0.01


def test_170518_bad_dbtime():
    """This went into the database with an incorrect expiration time"""
    spc = parser(get_test_file("SPCPTS/PTSDY1_baddbtime.txt"))
    answer = utc(2017, 5, 1, 12, 0)
    for outlook in spc.outlook_collections.values():
        assert outlook.expire == answer


@pytest.mark.parametrize("database", ["postgis"])
def test_170428_large(dbcursor):
    """PTSDY1 has a large 10 tor"""
    # /products/outlook/archive/2006/day1otlk_20060510_1630.html
    spc = parser(get_test_file("SPCPTS/PTSDY1_largetor10.txt"))
    spc.sql(dbcursor)
    spc.get_outlook("TORNADO", "0.10", 1)
    outlook = spc.get_outlook("CATEGORICAL", "TSTM", 1)
    assert abs(outlook.geometry_layers.area - 428.00) < 0.01


@pytest.mark.parametrize("database", ["postgis"])
def test_170417_empty(dbcursor):
    """An empty PTSD48 was causing an exception in get_jabbers"""
    spc = parser(get_test_file("SPCPTS/PTSD48_empty.txt"))
    spc.sql(dbcursor)
    jabber = spc.get_jabbers("")
    ans = (
        "The Storm Prediction Center issues Days 4-8 "
        "Convective Outlook at Dec 25, 9:41z "
        "https://www.spc.noaa.gov/products/exper/day4-8/archive/"
        "2008/day4-8_20081225.html"
    )
    assert jabber[-1][0] == ans
    ans = (
        "https://mesonet.agron.iastate.edu/plotting/auto/plot/220/"
        "cat:categorical::which:0C::t:conus::network:WFO::wfo:DMX::_r:86::"
        "csector:conus::valid:2008-12-25%200941.png"
    )
    assert jabber[-1][2]["twitter_media"] == ans


@pytest.mark.parametrize("database", ["postgis"])
def test_051128_invalid(dbcursor):
    """Make sure that the SIG wind threshold does not eat the US"""
    spc = parser(get_test_file("SPCPTS/PTSDY1_biggeom2.txt"))
    spc.sql(dbcursor)
    outlook = spc.get_outlook("WIND", "0.05", 1)
    assert outlook.geometry_layers.is_empty
    assert len(spc.warnings) == 4


def test_080731_invalid():
    """Make sure that the SIG wind threshold does not eat the US"""
    spc = parser(get_test_file("SPCPTS/PTSDY1_biggeom.txt"))
    outlook = spc.get_outlook("WIND", "SIGN", 1)
    assert abs(outlook.geometry_layers.area - 15.823) < 0.01


def test_170411_jabber_error():
    """This empty Fire Weather Day 3-8 raised a jabber error"""
    spc = parser(get_test_file("SPCPTS/PFWF38_empty.txt"))
    j = spc.get_jabbers("")
    ans = (
        "The Storm Prediction Center issues Day 3-8 Fire "
        "Weather Outlook at Apr 11, 19:54z "
        "https://www.spc.noaa.gov/products/exper/fire_wx/2017/170413.html"
    )
    assert j[-1][0] == ans


@pytest.mark.parametrize("database", ["postgis"])
def test_170406_day48_pre2015(dbcursor):
    """Can we parse a pre2015 days 4-8"""
    spc = parser(get_test_file("SPCPTS/PTSD48_pre2015.txt"))
    outlook = spc.get_outlook("ANY SEVERE", "0.15", 4)
    assert abs(outlook.geometry_layers.area - 73.116) < 0.01
    outlook = spc.get_outlook("ANY SEVERE", "0.15", 5)
    assert abs(outlook.geometry_layers.area - 72.533) < 0.01
    spc.sql(dbcursor)


def test_jabber_day48():
    """Test that we get a day 4-8 jabber message."""
    spc = parser(get_test_file("SPCPTS/PTSD48.txt"))
    j = spc.get_jabbers("")
    assert len(j) == 16


@pytest.mark.parametrize("database", ["postgis"])
def test_170406_day48(dbcursor):
    """Can we parse a present day days 4-8"""
    spc = parser(get_test_file("SPCPTS/PTSD48.txt"))
    outlook = spc.get_outlook("ANY SEVERE", "0.15", 4)
    assert abs(outlook.geometry_layers.area - 40.05) < 0.01
    spc.sql(dbcursor)
    collect = spc.get_outlookcollection(4)
    assert collect.issue == utc(2017, 4, 9, 12)
    assert collect.expire == utc(2017, 4, 10, 12)


def test_170404_nogeom():
    """nogeom error from a 2002 product"""
    # 26 Sep 2017, we can workaround this now
    spc = parser(get_test_file("SPCPTS/PTSDY1_2002_nogeom.txt"))
    outlook = spc.get_outlook("TORNADO", "0.05", 1)
    assert abs(outlook.geometry_layers.area - 8.76) < 0.01


def test_170404_2002():
    """Can we parse something from 2002?"""
    spc = parser(get_test_file("SPCPTS/PTSDY1_2002.txt"))
    outlook = spc.get_outlook("CATEGORICAL", "SLGT", 1)
    assert abs(outlook.geometry_layers.area - 38.614) < 0.01


def test_170329_notimp():
    """Exception was raised parsing this guy"""
    spc = parser(get_test_file("SPCPTS/PTSDY2_notimp.txt"))
    outlook = spc.get_outlook("CATEGORICAL", "MRGL", 2)
    assert abs(outlook.geometry_layers.area - 110.24) < 0.01


def test_170215_gh23():
    """A marginal for the entire country :/"""
    spc = parser(get_test_file("SPCPTS/PTSDY1_gh23.txt"))
    outlook = spc.get_outlook("CATEGORICAL", "MRGL", 1)
    assert abs(outlook.geometry_layers.area - 19.63) < 0.01


def test_150622_ptsdy1_topo():
    """PTSDY1_topo.txt"""
    spc = parser(get_test_file("SPCPTS/PTSDY1_topo.txt"))
    outlook = spc.get_outlook("CATEGORICAL", "SLGT", 1)
    assert abs(outlook.geometry_layers.area - 91.91) < 0.01


def test_150622_ptsdy2():
    """PTSDY2_invalid.txt parsed ok."""
    spc = parser(get_test_file("SPCPTS/PTSDY2_invalid.txt"))
    outlook = spc.get_outlook("CATEGORICAL", "SLGT", 2)
    assert abs(outlook.geometry_layers.area - 78.14) < 0.01


def test_150622_ptsdy1():
    """PTSDY1_nogeom.txt"""
    spc = parser(get_test_file("SPCPTS/PTSDY1_nogeom.txt"))
    outlook = spc.get_outlook("CATEGORICAL", "SLGT", 1)
    assert abs(outlook.geometry_layers.area - 95.912) < 0.01


def test_150612_ptsdy1_3():
    """We got an error with this, so we shall test"""
    spc = parser(get_test_file("SPCPTS/PTSDY1_3.txt"))
    outlook = spc.get_outlook("CATEGORICAL", "SLGT", 1)
    assert abs(outlook.geometry_layers.area - 53.94) < 0.01


def test_141022_newcats():
    """Make sure we can parse the new categories"""
    spc = parser(
        get_test_file("SPCPTS/PTSDY1_new.txt"),
        utcnow=utc(2014, 10, 13, 16, 21),
    )
    outlook = spc.get_outlook("CATEGORICAL", "ENH", 1)
    assert abs(outlook.geometry_layers.area - 13.02) < 0.01
    outlook = spc.get_outlook("CATEGORICAL", "MRGL", 1)
    assert abs(outlook.geometry_layers.area - 47.01) < 0.01


def test_140709_nogeoms():
    """Can we parse holes."""
    spc = parser(get_test_file("SPCPTS/PTSDY3_nogeoms.txt"))
    outlook = spc.get_outlook("ANY SEVERE", "0.05", 3)
    assert abs(outlook.geometry_layers.area - 99.68) < 0.01


def test_140710_nogeom():
    """Can we parse holes."""
    spc = parser(get_test_file("SPCPTS/PTSDY2_nogeom.txt"))
    outlook = spc.get_outlook("CATEGORICAL", "SLGT", 2)
    assert abs(outlook.geometry_layers.area - 43.02) < 0.01


def test_23jul_failure():
    """CCW line near Boston"""
    # need to load data for this to work as a one
    load_conus_data(utc(2017, 7, 23))
    data = """40067377 40567433 41317429 42097381 42357259 42566991"""
    res = str2multipolygon(data)
    assert abs(res.geoms[0].area - 7.96724) < 0.0001


def test_140707_general():
    """Had a problem with General Thunder, lets test this"""
    # /products/outlook/archive/2014/day1otlk_20140707_1630.html
    spc = parser(get_test_file("SPCPTS/PTSDY1_complex.txt"))
    outlook = spc.get_outlook("CATEGORICAL", "TSTM", 1)
    assert abs(outlook.geometry_layers.area - 606.333) < 0.01


def test_complex():
    """Test our processing"""
    spc = parser(get_test_file("SPCPTS/PTSDY3.txt"))
    outlook = spc.get_outlook("ANY SEVERE", "0.05", 3)
    assert abs(outlook.geometry_layers.area - 10.12) < 0.01


def test_bug_140601_pfwf38():
    """Encounted issue with Fire Outlook Day 3-8"""
    spc = parser(get_test_file("SPCPTS/PFWF38.txt"))
    collect = spc.get_outlookcollection(3)
    assert len(collect.outlooks) == 1


def test_bug_140507_day1():
    """Bug found in production with GEOS Topology Exception"""
    spc = parser(get_test_file("SPCPTS/PTSDY1_topoexp.txt"))
    collect = spc.get_outlookcollection(1)
    assert len(collect.outlooks) == 14


def test_bug_140506_day2():
    """Bug found in production"""
    spc = parser(get_test_file("SPCPTS/PTSDY2.txt"))
    collect = spc.get_outlookcollection(2)
    assert len(collect.outlooks) == 6
    j = spc.get_jabbers("localhost", "localhost")
    ans = (
        "The Storm Prediction Center issues Day 2 "
        "Convective Outlook (Max Risk: Slight) at May 6, 17:31z "
        "https://www.spc.noaa.gov/products/outlook/archive/2014/"
        "day2otlk_20140506_1730.html"
    )
    assert j[-1][0] == ans
    ans = (
        "https://mesonet.agron.iastate.edu/plotting/auto/plot/220/"
        "cat:categorical::which:2C::t:conus::network:WFO::wfo:UNR::_r:86::"
        "csector:conus::valid:2014-05-06%201731.png"
    )
    assert j[-1][2]["twitter_media"] == ans


def test_bug_140518_day2():
    """18 May 2014 tripped error with no exterior polygon found"""
    # /products/outlook/archive/2014/day2otlk_20140518_0600.html
    spc = parser(get_test_file("SPCPTS/PTSDY2_interior.txt"))
    collect = spc.get_outlookcollection(2)
    assert len(collect.outlooks) == 1


def test_bug_140519_day1():
    """19 May 2014 tripped error with no exterior polygon found"""
    spc = parser(get_test_file("SPCPTS/PTSDY1_interior.txt"))
    collect = spc.get_outlookcollection(1)
    assert len(collect.outlooks) == 7


def test_bug():
    """Test bug list index outof range"""
    spc = parser(get_test_file("SPCPTS/PTSDY1_2.txt"))
    collect = spc.get_outlookcollection(1)
    assert len(collect.outlooks) == 1


def test_complex_2():
    """Test our processing"""
    spc = parser(get_test_file("SPCPTS/PTSDY1.txt"))
    outlook = spc.get_outlook("HAIL", "0.05", 1)
    assert abs(outlook.geometry_layers.area - 47.65) < 0.01


@pytest.mark.parametrize("database", ["postgis"])
def test_str1(dbcursor):
    """check spcpts parsing"""
    spc = parser(get_test_file("SPCPTS/SPCPTS.txt"))
    assert spc.valid == utc(2013, 7, 19, 19, 52)
    assert spc.issue == utc(2013, 7, 19, 20, 0)
    assert spc.expire == utc(2013, 7, 20, 12, 0)

    spc.sql(dbcursor)
    j = spc.get_jabbers("")
    assert len(j) >= 1
