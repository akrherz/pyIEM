"""Massive omnibus of testing for pyiem.nws.products."""

import pytest

from pyiem.exceptions import HWOException, TextProductException
from pyiem.nws.products import parser
from pyiem.util import get_test_file, utc


def filter_warnings(ar, startswith="get_gid"):
    """Remove non-deterministic warnings

    Some of our tests produce get_gid() warnings, which are safe to ignore
    for the purposes of this testing
    """
    return [a for a in ar if not a.startswith(startswith)]


def test_240425_mnd_timestamp():
    """Test parsing of this old timestamp variant."""
    prod = parser(get_test_file("SVR/SVRILN_mnd_timestamp.txt"))
    assert prod.valid == utc(1996, 6, 23, 0, 57)


def test_220726_utc():
    """Test problem with AM/PM with 12 UTC."""
    utcnow = utc(2022, 7, 26, 0, 49)
    prod = parser(get_test_file("FLS/FLSGUM_timestamp.txt"))
    assert prod.valid == utcnow


def test_220624_micronesia_tz():
    """Test that we understand a timestamp from Micronesia."""
    prod = parser(get_test_file("SFTPQ2.txt"))
    assert prod.valid == utc(2022, 6, 24, 6, 2)


def test_201124_tab_in_afos():
    """Test that we can deal with a tab in the AFOS ID."""
    data = get_test_file("FFW/FFWGUM.txt").replace("FFWGUM", "FFWGUM\t")
    prod = parser(data)
    assert prod.afos == "FFWGUM"


def test_181207_issue74_guam():
    """Guam's longitudes are east, not west like code assumes."""
    prod = parser(get_test_file("FFW/FFWGUM.txt"))
    ans = "SRID=4326;MULTIPOLYGON (((145.80 15.16, 145.74"
    assert prod.segments[0].giswkt.startswith(ans)


def test_180917_issue63_tweet_length():
    """Make sure this tweet text is not too long!"""
    utcnow = utc(2018, 9, 15, 11, 56)
    prod = parser(get_test_file("LSR/LSRCRP.txt"), utcnow=utcnow)
    j = prod.get_jabbers("http://iem.local/")
    assert j[0][2]["twitter"] == (
        "At 6:45 AM CDT, 2 NNE Odem [San Patricio Co, TX] DEPT OF HIGHWAYS "
        "reports FLOOD. ROAD CLOSURE FM 1944 BETWEEN U.S. HIGHWAY 77 AND "
        "SODVILLE ROAD (TEXAS DEPARTMENT OF TRANSPORATION. DRIVETEXAS.ORG.) "
        "LATITUDE/LONGITUDE MARKS APPROXIMATE POSITION... #txwx "
        "http://iem.local/?by=wfo&amp;wfo=CRP&amp;sts=201809151145&amp;ets=201809151145"
    )


def test_170116_mixedlsr():
    """LSRBOU has mixed case, see what we can do"""
    utcnow = utc(2016, 11, 29, 22, 00)
    prod = parser(get_test_file("mIxEd_CaSe/LSRBOU.txt"), utcnow=utcnow)
    j = prod.get_jabbers("http://iem.local/")
    assert j[0][2]["twitter"] == (
        "At 11:00 AM MST, Akron [Washington Co, CO] ASOS reports "
        "High Wind of M63 MPH #cowx "
        "http://iem.local/?by=wfo&amp;wfo=BOU&amp;sts=201611291800&amp;ets=201611291800"
    )


def test_180710_issue58():
    """Crazy MST during MDT"""
    utcnow = utc(2018, 7, 9, 22, 59)
    prod = parser(get_test_file("LSR/LSRPSR.txt"), utcnow=utcnow)
    j = prod.get_jabbers("http://iem.local/")
    ans = (
        "At 3:57 PM MST, 5 WNW Florence [Pinal Co, AZ] TRAINED SPOTTER "
        "reports FLASH FLOOD. STREET FLOODING WITH WATER OVER THE CURBS "
        "IN THE MERRILL RANCH DEVELOPMENT OF FLORENCE. #azwx "
        "http://iem.local/?by=wfo&amp;wfo=PSR&amp;sts=201807092257&amp;ets=201807092257"
    )
    assert j[0][2]["twitter"] == ans
    ans = (
        "5 WNW Florence [Pinal Co, AZ] TRAINED SPOTTER reports FLASH FLOOD "
        "at 3:57 PM MST -- STREET FLOODING WITH WATER OVER THE CURBS IN "
        "THE MERRILL RANCH DEVELOPMENT OF FLORENCE. "
        "http://iem.local/?by=wfo&amp;wfo=PSR&amp;sts=201807092257&amp;ets=201807092257"
    )
    assert j[0][0] == ans


def test_180705_iembot_issue9():
    """LSRBOU has mixed case, see what we can do"""
    utcnow = utc(2018, 7, 4, 22, 11)
    prod = parser(get_test_file("LSR/LSRDMX.txt"), utcnow=utcnow)
    j = prod.get_jabbers("http://iem.local/")
    assert j[0][2]["twitter"] == (
        "At 1:30 PM CDT, 1 WNW Lake Mills [Winnebago Co, IA] TRAINED SPOTTER "
        "reports TSTM WND GST of E61 MPH. SPOTTER MEASURED 61 MPH WIND GUST. "
        "HIS CAR DOOR WAS ALSO CAUGHT BY THE WIND WHEN HE WAS OPENING "
        "THE DOOR, PUSHING THE DOOR INTO HIS FACE. THIS... #iawx "
        "http://iem.local/?by=wfo&amp;wfo=DMX&amp;sts=201807041830&amp;ets=201807041830"
    )


def test_171026_mixedlsr():
    """LSRBYZ has mixed case, see what we can do"""
    utcnow = utc(2017, 10, 29, 19, 18)
    prod = parser(get_test_file("mIxEd_CaSe/LSRBYZ.txt"), utcnow=utcnow)
    j = prod.get_jabbers("http://iem.local/")
    assert j[0][2]["twitter"] == (
        "[Delayed Report] On Oct 26, at 1:00 AM MDT, 3 SSW Luther "
        "[Carbon Co, MT] Mesonet reports Snow of 1.00 inch #mtwx "
        "http://iem.local/?by=wfo&amp;wfo=BYZ&amp;"
        "sts=201710260700&amp;ets=201710260700"
    )


def test_170419_tcp_mixedcase():
    """Mixed case TCP1"""
    prod = parser(get_test_file("TCPAT1_mixedcase.txt"))
    j = prod.get_jabbers("")
    assert j


def test_170403_badtime():
    """Handle when a colon is added to a timestamp"""
    prod = parser(get_test_file("FLWBOI.txt"))
    prod.get_jabbers("http://localhost", "http://localhost")
    ans = utc(2017, 4, 2, 2, 30)
    assert prod.valid == ans


def test_170324_badformat():
    """Look into exceptions"""
    utcnow = utc(2017, 3, 22, 2, 35)
    prod = parser(get_test_file("LSR/LSRPIH.txt"), utcnow=utcnow)
    prod.get_jabbers("http://iem.local/")
    assert len(prod.warnings) == 2
    assert not prod.lsrs


def test_170324_ampersand():
    """LSRs with ampersands may cause trouble"""
    utcnow = utc(2015, 12, 29, 18, 23)
    prod = parser(get_test_file("LSR/LSRBOXamp.txt"), utcnow=utcnow)
    j = prod.get_jabbers("http://iem.local/")
    ans = (
        "Lunenberg [Worcester Co, MA] HAM RADIO reports SNOW of 2.00 INCH "
        "at 11:36 AM EST -- HAM RADIO AND THIS DARYL ADDED &amp; and &lt; "
        "and &gt; "
        "http://iem.local/?by=wfo&amp;wfo=BOX&amp;sts=201512291636&amp;ets=201512291636"
    )
    assert j[0][0] == ans


def test_170207_mixedhwo():
    """Check our parsing of mixed case HWO"""
    prod = parser(get_test_file("mIxEd_CaSe/HWOLOT.txt"))
    j = prod.get_jabbers("http://iem.local/")
    assert not prod.warnings
    assert len(j[0]) == 3


def test_160618_chst_tz():
    """Product has timezone of ChST, do we support it?"""
    prod = parser(get_test_file("AFDPQ.txt"))
    assert prod.valid == utc(2016, 6, 18, 19, 27)


def test_151229_badgeo_lsr():
    """Make sure we reject a bad Geometry LSR"""
    utcnow = utc(2015, 12, 29, 18, 23)
    prod = parser(get_test_file("LSR/LSRBOX.txt"), utcnow=utcnow)
    assert len(prod.warnings) == 1
    assert not prod.lsrs


def test_150422_tornadomag():
    """LSRTAE see what we do with tornado magitnudes"""
    utcnow = utc(2015, 4, 22, 15, 20)
    prod = parser(get_test_file("LSR/LSRTAE.txt"), utcnow=utcnow)
    j = prod.get_jabbers("http://iem.local/")
    assert j[0][1] == (
        "<p>[Delayed Report] 4 W Bruce [Walton Co, FL] NWS EMPLOYEE "
        '<a href="'
        'http://iem.local/?by=wfo&amp;wfo=TAE&amp;sts=201504191322&amp;ets=201504191322">'
        "reports TORNADO of EF0</a> at 19 Apr, 9:22 AM EDT -- "
        "SHORT EF0 TORNADO PATH CONFIRMED BY NWS DUAL POL RADAR DEBRIS "
        "SIGNATURE IN A RURAL AREA WEST OF BRUCE. DAMAGE LIKELY CONFINED "
        "TO TREES. ESTIMATED DURATION 3 MINUTES. PATH LENGTH "
        "APPROXIMATELY 1 MILE.</p>"
    )
    assert j[0][2]["twitter"] == (
        "[Delayed Report] On Apr 19, at 9:22 AM EDT, "
        "4 W Bruce [Walton Co, FL] NWS EMPLOYEE reports "
        "TORNADO of EF0. SHORT EF0 TORNADO PATH CONFIRMED BY NWS DUAL "
        "POL RADAR DEBRIS SIGNATURE IN A RURAL AREA WEST OF BRUCE. "
        "DAMAGE LIKELY CONFINED TO TREES.... #flwx "
        "http://iem.local/?by=wfo&amp;wfo=TAE&amp;sts=201504191322&amp;ets=201504191322"
    )


def test_150202_hwo():
    """HWORNK emitted a poorly worded error message"""
    prod = parser(get_test_file("HWO/HWORNK.txt"))
    with pytest.raises(HWOException):
        prod.get_jabbers("http://localhost", "http://localhost")


def test_160418_hwospn():
    """Make sure a spanish HWO does not trip us up..."""
    utcnow = utc(2016, 4, 18, 10, 10)
    prod = parser(get_test_file("HWO/HWOSPN.txt"), utcnow=utcnow)
    j = prod.get_jabbers("http://localhost", "http://localhost")
    ans = (
        "JSJ issues Hazardous Weather Outlook (HWO) "
        "at Apr 18, 10:18 UTC http://localhost?"
        "pid=201604181018-TJSJ-FLCA42-HWOSPN"
    )
    assert j[0][0] == ans


def test_tcp():
    """See what we can do with TCP"""
    prod = parser(get_test_file("TCPAT1.txt"))
    j = prod.get_jabbers("http://localhost", "http://localhost")
    ans = (
        "National Hurricane Center issues "
        "ADVISORY 19 for POST-TROPICAL CYCLONE ARTHUR "
        "http://localhost?pid=201407051500-KNHC-WTNT31-TCPAT1"
    )
    assert j[0][0] == ans
    ans = (
        "Post-Tropical Cyclone "
        "#Arthur ADVISORY 19 issued. Strong winds and heavy rains to "
        "continue over portions of southeastern canada through tonight. "
        "http://go.usa.gov/W3H"
    )
    assert j[0][2]["twitter"] == ans


def test_140820_badtimestamp():
    """Check our invalid timestamp exception and how it is written"""
    with pytest.raises(TextProductException):
        parser(get_test_file("RWSGTF_badtime.txt"))


def test_160904_resent():
    """Is this product a correction?"""
    prod = parser(get_test_file("TCV/TCVAKQ.txt"))
    jmsgs = prod.get_jabbers("http://localhost")
    ans = (
        "#AKQ issues Tropical Watch/Warning Local Statement (TCV) "
        "at Sep 2, 11:55 AM EDT ...TROPICAL STORM WARNING IN EFFECT... "
        "http://localhost?pid=201609021555-KAKQ-WTUS81-TCVAKQ"
    )
    assert jmsgs[0][2]["twitter"] == ans


def test_jabber_lsrtime():
    """Make sure delayed LSRs have proper dates associated with them"""
    utcnow = utc(2014, 6, 6, 16)
    prod = parser(get_test_file("LSR/LSRFSD.txt"), utcnow=utcnow)
    j = prod.get_jabbers("http://iem.local")
    ans = (
        "<p>[Delayed Report] 2 SSE Harrisburg [Lincoln Co, SD] "
        'TRAINED SPOTTER <a href="http://iem.local?by=wfo&amp;wfo=FSD&amp;'
        "sts=201406052040"
        '&amp;ets=201406052040">reports TORNADO</a> at 5 Jun, 3:40 PM CDT -- '
        "ON GROUND ALONG HIGHWAY 11 NORTH OF 275TH ST</p>"
    )
    assert j[0][1] == ans


def test_spacewx():
    """See if we can parse a space weather product"""
    utcnow = utc(2014, 5, 10)
    prod = parser(get_test_file("SPACEWX.txt"), utcnow=utcnow)
    assert prod is not None


def test_140522_blowingdust():
    """This LSR type is now valid."""
    prod = parser(get_test_file("LSR/LSRTWC.txt"))
    assert prod.lsrs


def test_01():
    """LSR.txt process a valid LSR without blemish"""
    utcnow = utc(2013, 7, 23, 23, 54)
    prod = parser(get_test_file("LSR/LSR.txt"), utcnow=utcnow)
    assert prod.lsrs[0].remark is None
    assert len(prod.lsrs) == 58

    assert abs(prod.lsrs[57].magnitude_f - 73) < 0.01
    assert prod.lsrs[57].county == "MARION"
    assert prod.lsrs[57].state == "IA"
    assert abs(prod.lsrs[57].get_lon() - -93.11) < 0.01
    assert abs(prod.lsrs[57].get_lat() - 41.3) < 0.01

    assert prod.is_summary()
    assert prod.lsrs[57].wfo == "DMX"
