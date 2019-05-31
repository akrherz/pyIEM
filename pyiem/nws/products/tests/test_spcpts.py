"""Unit Tests"""
# pylint: disable=redefined-outer-name

import pytest
from psycopg2.extras import RealDictCursor
from pyiem.nws.products.spcpts import parser, str2multipolygon
from pyiem.util import get_dbconn, utc, get_test_file


@pytest.fixture
def dbcursor():
    """Get database."""
    return get_dbconn('postgis').cursor(cursor_factory=RealDictCursor)


def test_190527_canada():
    """SPC Updated marine bounds."""
    spc = parser(get_test_file('SPCPTS/PTSDY1_canada.txt'))
    # spc.draw_outlooks()
    outlook = spc.get_outlook('CATEGORICAL', 'MRGL', 1)
    assert abs(outlook.geometry.area - 118.22) < 0.01


def test_190515_issue117_month():
    """Product crossing year causes grief."""
    spc = parser(get_test_file('SPCPTS/PTSDY2_month.txt'))
    collect = spc.get_outlookcollection(2)
    assert collect.expire == utc(2019, 5, 2, 12)


def test_190509_marinebounds():
    """SPC Updated marine bounds."""
    spc = parser(get_test_file('SPCPTS/PTSDY1_marine.txt'))
    # spc.draw_outlooks()
    outlook = spc.get_outlook('HAIL', '0.15', 1)
    assert abs(outlook.geometry.area - 17.82) < 0.01


def test_190415_elevated():
    """Can we parse elevated threshold firewx?"""
    spc = parser(get_test_file('SPCPTS/PFWFD1_example.txt'))
    outlook = spc.get_outlook('FIRE WEATHER CATEGORICAL', 'ELEV', 1)
    assert abs(outlook.geometry.area - 145.64) < 0.01
    for level in ['IDRT', 'SDRT', 'ELEV', 'CRIT', 'EXTM']:
        outlook = spc.get_outlook('FIRE WEATHER CATEGORICAL', level, 1)
        assert outlook is not None


def test_190415_badtime():
    """This product has a bad time period, we should emit a warning."""
    spc = parser(get_test_file('SPCPTS/PTSDY1_invalidtime.txt'))
    assert any([w.startswith("time_bounds_check") for w in spc.warnings])


def test_180807_idx1_idx2():
    """This Day1 generated an error."""
    spc = parser(get_test_file('SPCPTS/PTSDY1_idx1_idx2.txt'))
    outlook = spc.get_outlook('WIND', '0.05', 1)
    assert abs(outlook.geometry.area - 37.83) < 0.02


def test_170926_largeenh(dbcursor):
    """This Day1 generated a massive ENH"""
    spc = parser(get_test_file('SPCPTS/PTSDY1_bigenh.txt'))
    # spc.draw_outlooks()
    spc.sql(dbcursor)
    outlook = spc.get_outlook('CATEGORICAL', 'ENH', 1)
    assert abs(outlook.geometry.area - 17.50) < 0.01


def test_170703_badday3link():
    """Day3 URL is wrong"""
    spc = parser(get_test_file('SPCPTS/PTSDY3.txt'))
    jdict = spc.get_jabbers('', '')
    ans = (
        'The Storm Prediction Center issues Day 3 '
        'Convective Outlook at Nov 19, 8:31z '
        'https://www.spc.noaa.gov/products/outlook/archive/2013/'
        'day3otlk_20131119_0830.html'
    )
    assert jdict[0][0] == ans


def test_170612_nullgeom(dbcursor):
    """See why this has an error with null geom reported"""
    spc = parser(get_test_file('SPCPTS/PTSD48_nullgeom.txt'))
    # spc.draw_outlooks()
    spc.sql(dbcursor)
    outlook = spc.get_outlook('ANY SEVERE', '0.15', 4)
    assert abs(outlook.geometry.area - 56.84) < 0.01


def test_170522_nogeom():
    """See why this has an error with no-geom reported"""
    spc = parser(get_test_file('SPCPTS/PTSDY1_nogeom2.txt'))
    # spc.draw_outlooks()
    outlook = spc.get_outlook('TORNADO', '0.02', 1)
    assert abs(outlook.geometry.area - 2.90) < 0.01


def test_170518_bad_dbtime():
    """This went into the database with an incorrect expiration time"""
    spc = parser(get_test_file('SPCPTS/PTSDY1_baddbtime.txt'))
    answer = utc(2017, 5, 1, 12, 0)
    for _, outlook in spc.outlook_collections.items():
        assert outlook.expire == answer


def test_170428_large(dbcursor):
    """PTSDY1 has a large 10 tor"""
    spc = parser(get_test_file('SPCPTS/PTSDY1_largetor10.txt'))
    # spc.draw_outlooks()
    spc.sql(dbcursor)
    outlook = spc.get_outlook('TORNADO', '0.10', 1)
    assert abs(outlook.geometry.area - 31.11) < 0.01


def test_170417_empty(dbcursor):
    """An empty PTSD48 was causing an exception in get_jabbers"""
    spc = parser(get_test_file('SPCPTS/PTSD48_empty.txt'))
    # spc.draw_outlooks()
    spc.sql(dbcursor)
    jabber = spc.get_jabbers('')
    ans = (
        "The Storm Prediction Center issues Days 4-8 "
        "Convective Outlook at Dec 25, 9:41z "
        "https://www.spc.noaa.gov/products/exper/day4-8/archive/"
        "2008/day4-8_20081225.html"
    )
    assert jabber[0][0] == ans


def test_051128_invalid(dbcursor):
    """Make sure that the SIG wind threshold does not eat the US"""
    spc = parser(get_test_file('SPCPTS/PTSDY1_biggeom2.txt'))
    # spc.draw_outlooks()
    spc.sql(dbcursor)
    outlook = spc.get_outlook('WIND', 'SIGN', 1)
    assert outlook.geometry.is_empty
    print("\n".join(spc.warnings))
    assert len(spc.warnings) == 2


def test_080731_invalid():
    """Make sure that the SIG wind threshold does not eat the US"""
    spc = parser(get_test_file('SPCPTS/PTSDY1_biggeom.txt'))
    # spc.draw_outlooks()
    outlook = spc.get_outlook('WIND', 'SIGN', 1)
    assert abs(outlook.geometry.area - 15.82) < 0.01
    assert len(spc.warnings) == 1


def test_170411_jabber_error():
    """This empty Fire Weather Day 3-8 raised a jabber error"""
    spc = parser(get_test_file('SPCPTS/PFWF38_empty.txt'))
    j = spc.get_jabbers('')
    ans = (
        "The Storm Prediction Center issues Day 3-8 Fire "
        "Weather Outlook at Apr 11, 19:54z "
        "https://www.spc.noaa.gov/products/exper/fire_wx/2017/170413.html"
    )
    assert j[0][0] == ans


def test_170406_day48_pre2015(dbcursor):
    """Can we parse a pre2015 days 4-8"""
    spc = parser(get_test_file('SPCPTS/PTSD48_pre2015.txt'))
    # spc.draw_outlooks()
    outlook = spc.get_outlook('ANY SEVERE', '0.15', 4)
    assert abs(outlook.geometry.area - 73.116) < 0.01
    outlook = spc.get_outlook('ANY SEVERE', '0.15', 5)
    assert abs(outlook.geometry.area - 72.533) < 0.01
    spc.sql(dbcursor)


def test_170406_day48(dbcursor):
    """Can we parse a present day days 4-8"""
    spc = parser(get_test_file('SPCPTS/PTSD48.txt'))
    # spc.draw_outlooks()
    outlook = spc.get_outlook('ANY SEVERE', '0.15', 4)
    assert abs(outlook.geometry.area - 40.05) < 0.01
    spc.sql(dbcursor)
    collect = spc.get_outlookcollection(4)
    assert collect.issue == utc(2017, 4, 9, 12)
    assert collect.expire == utc(2017, 4, 10, 12)


def test_170404_nogeom():
    """nogeom error from a 2002 product"""
    # 26 Sep 2017, we can workaround this now
    spc = parser(get_test_file('SPCPTS/PTSDY1_2002_nogeom.txt'))
    outlook = spc.get_outlook('TORNADO', '0.05')
    assert abs(outlook.geometry.area - 8.76) < 0.01


def test_170404_2002():
    """Can we parse something from 2002?"""
    spc = parser(get_test_file('SPCPTS/PTSDY1_2002.txt'))
    # spc.draw_outlooks()
    outlook = spc.get_outlook('CATEGORICAL', 'SLGT')
    assert abs(outlook.geometry.area - 38.92) < 0.01


def test_170329_notimp():
    """Exception was raised parsing this guy"""
    spc = parser(get_test_file('SPCPTS/PTSDY2_notimp.txt'))
    # spc.draw_outlooks()
    outlook = spc.get_outlook('CATEGORICAL', 'MRGL')
    assert abs(outlook.geometry.area - 110.24) < 0.01


def test_170215_gh23():
    """A marginal for the entire country :/"""
    spc = parser(get_test_file('SPCPTS/PTSDY1_gh23.txt'))
    # spc.draw_outlooks()
    outlook = spc.get_outlook('CATEGORICAL', 'MRGL')
    assert abs(outlook.geometry.area - 19.63) < 0.01


def test_150622_ptsdy1_topo():
    """PTSDY1_topo.txt """
    spc = parser(get_test_file('SPCPTS/PTSDY1_topo.txt'))
    # spc.draw_outlooks()
    outlook = spc.get_outlook('CATEGORICAL', 'SLGT')
    assert abs(outlook.geometry.area - 91.91) < 0.01


def test_150622_ptsdy2():
    """PTSDY2_invalid.txt """
    with pytest.raises(Exception):
        parser(get_test_file('SPCPTS/PTSDY2_invalid.txt'))


def test_150622_ptsdy1():
    """PTSDY1_nogeom.txt """
    spc = parser(get_test_file('SPCPTS/PTSDY1_nogeom.txt'))
    outlook = spc.get_outlook('CATEGORICAL', 'SLGT')
    assert abs(outlook.geometry.area - 95.88) < 0.01


def test_150612_ptsdy1_3():
    """We got an error with this, so we shall test"""
    spc = parser(get_test_file('SPCPTS/PTSDY1_3.txt'))
    outlook = spc.get_outlook('CATEGORICAL', 'SLGT')
    assert abs(outlook.geometry.area - 53.94) < 0.01


def test_141022_newcats():
    """ Make sure we can parse the new categories """
    spc = parser(
        get_test_file('SPCPTS/PTSDY1_new.txt'),
        utcnow=utc(2014, 10, 13, 16, 21))
    outlook = spc.get_outlook('CATEGORICAL', 'ENH')
    assert abs(outlook.geometry.area - 13.02) < 0.01
    outlook = spc.get_outlook('CATEGORICAL', 'MRGL')
    assert abs(outlook.geometry.area - 47.01) < 0.01


def test_140709_nogeoms():
    """ Make sure we don't have another failure with geom parsing """
    with pytest.raises(Exception):
        parser(get_test_file('SPCPTS/PTSDY3_nogeoms.txt'))


def test_140710_nogeom():
    """ Had a failure with no geometries parsed """
    with pytest.raises(Exception):
        parser(get_test_file('SPCPTS/PTSDY2_nogeom.txt'))


def test_23jul_failure():
    ''' CCW line near Boston '''
    data = """40067377 40567433 41317429 42097381 42357259 42566991"""
    res = str2multipolygon(data)
    assert abs(res[0].area - 7.98403) < 0.0001


def test_140707_general():
    """ Had a problem with General Thunder, lets test this """
    spc = parser(get_test_file('SPCPTS/PTSDY1_complex.txt'))
    # spc.draw_outlooks()
    outlook = spc.get_outlook('CATEGORICAL', 'TSTM')
    assert abs(outlook.geometry.area - 606.33) < 0.01


def test_complex():
    ''' Test our processing '''
    spc = parser(get_test_file('SPCPTS/PTSDY3.txt'))
    outlook = spc.get_outlook('ANY SEVERE', '0.05')
    assert abs(outlook.geometry.area - 10.12) < 0.01


def test_bug_140601_pfwf38():
    ''' Encounted issue with Fire Outlook Day 3-8 '''
    spc = parser(get_test_file('SPCPTS/PFWF38.txt'))
    # spc.draw_outlooks()
    collect = spc.get_outlookcollection(3)
    assert len(collect.outlooks) == 1


def test_bug_140507_day1():
    ''' Bug found in production with GEOS Topology Exception '''
    spc = parser(get_test_file('SPCPTS/PTSDY1_topoexp.txt'))
    # spc.draw_outlooks()
    collect = spc.get_outlookcollection(1)
    assert len(collect.outlooks) == 14


def test_bug_140506_day2():
    """Bug found in production"""
    spc = parser(get_test_file('SPCPTS/PTSDY2.txt'))
    # spc.draw_outlooks()
    collect = spc.get_outlookcollection(2)
    assert len(collect.outlooks) == 6
    j = spc.get_jabbers('localhost', 'localhost')
    ans = (
        'The Storm Prediction Center issues Day 2 '
        'Convective Outlook at May 6, 17:31z '
        'https://www.spc.noaa.gov/products/outlook/archive/2014/'
        'day2otlk_20140506_1730.html'
    )
    assert j[0][0] == ans


def test_bug_140518_day2():
    ''' 18 May 2014 tripped error with no exterior polygon found '''
    spc = parser(get_test_file('SPCPTS/PTSDY2_interior.txt'))
    # spc.draw_outlooks()
    collect = spc.get_outlookcollection(2)
    assert len(collect.outlooks) == 1


def test_bug_140519_day1():
    ''' 19 May 2014 tripped error with no exterior polygon found '''
    spc = parser(get_test_file('SPCPTS/PTSDY1_interior.txt'))
    # spc.draw_outlooks()
    collect = spc.get_outlookcollection(1)
    assert len(collect.outlooks) == 7


def test_bug():
    ''' Test bug list index outof range '''
    spc = parser(get_test_file('SPCPTS/PTSDY1_2.txt'))
    collect = spc.get_outlookcollection(1)
    assert len(collect.outlooks) == 1


def test_complex_2():
    ''' Test our processing '''
    spc = parser(get_test_file('SPCPTS/PTSDY1.txt'))
    # spc.draw_outlooks()
    outlook = spc.get_outlook('HAIL', '0.05')
    assert abs(outlook.geometry.area - 47.65) < 0.01


def test_str1(dbcursor):
    """ check spcpts parsing """
    spc = parser(get_test_file('SPCPTS/SPCPTS.txt'))
    # spc.draw_outlooks()
    assert spc.valid == utc(2013, 7, 19, 19, 52)
    assert spc.issue == utc(2013, 7, 19, 20, 0)
    assert spc.expire == utc(2013, 7, 20, 12, 0)

    spc.sql(dbcursor)
    spc.compute_wfos(dbcursor)
    # It is difficult to get a deterministic result here as in Travis, we
    # don't have UGCS, so the WFO lookup yields no results
    j = spc.get_jabbers("")
    assert len(j) >= 1
