"""Testing!"""

import pytest
from pyiem.nws import product, ugc
from pyiem.nws.product import (
    WMO_RE,
    TextProductException,
    date_tokens2datetime,
    checker,
    str2polygon,
)
from pyiem.nws.products import parser as productparser
from pyiem.util import utc, get_test_file


def test_kawn():
    """Test that a bogus KAWN METAR header doesn't cause trouble."""
    data = get_test_file("METAR/kawn.txt")
    prod = productparser(data)
    assert not prod.warnings
    prod = productparser(data.replace("KAWN", "KZZZ"))
    assert prod.warnings[0].find("KZZZ") > -1


def test_tropical_channels():
    """Test the channels we have some products go into."""
    prod = productparser(get_test_file("tropical/TCUCP1.txt"))
    j = prod.get_jabbers("")
    assert "TCUCP" in j[0][2]["channels"].split(",")


def test_first_flapping():
    """Test for product crossing month backwards, prevent flapping test."""
    # Scenario is utcnow is the first and the WMO header is > 25th
    utcnow = utc(2012, 6, 1)
    prod = productparser(get_test_file("SVRBMX.txt"), utcnow=utcnow)
    assert prod.valid == utc(2012, 5, 31, 23, 11)


def test_no_afos():
    """Test product without AFOS/AWIPS ID."""
    with pytest.raises(TextProductException):
        productparser(get_test_file("PMDSA.txt").replace("PMDSA ", ""))


def test_str2polygon():
    """Test our str2polygon implementation."""
    res = str2polygon("4400 3200 4500 3300 4400 3300")
    assert res is not None


def test_checker():
    """Test that exceptions are raised in certain cases."""
    with pytest.raises(TextProductException):
        checker(-90, 91, "")
    with pytest.raises(TextProductException):
        checker(-650, 31, "")


def test_datetokens_just_hour():
    """Test that we can handle having just an hour."""
    tokens = ["3", "PM", "CDT", "", "MAR", "20", "2019"]
    z, tz, valid = date_tokens2datetime(tokens)
    assert z == "CDT"
    local = valid.astimezone(tz)
    assert local.hour == 15


def test_datetokens():
    """Test that we can rectify a bad hour value."""
    tokens = ["18:45", "PM", "CDT", "", "MAR", "20", "2019"]
    z, tz, valid = date_tokens2datetime(tokens)
    assert z == "CDT"
    local = valid.astimezone(tz)
    assert local.hour == 18


def test_wpc():
    """Can we deal with the AWIPS ID in WPC products."""
    tp = productparser(get_test_file("PMDSA.txt"))
    res = tp.get_jabbers("http://localhost")
    ans = (
        "WBC issues South America Forecast Discussion (PMD) at Jul 13, "
        "11:17 AM EDT http://localhost?pid=202007131517-KWBC-FXSA20-PMDSA"
    )
    assert res[0][0] == ans


def test_200913_dualtime():
    """Process a HLS in two timezones, sigh."""
    tp = productparser(get_test_file("HLS.txt"))
    assert not tp.warnings
    assert tp.z == "EDT"


def test_200731_cvt():
    """See that we handle CVT timezone products."""
    tp = productparser(get_test_file("TCDAT5_CVT.txt"))
    res = tp.get_jabbers("http://localhost")
    ans = (
        "NHC issues TCDAT5 (TCD) at Jul 31, 8:00 PM CVT "
        "http://localhost?pid=202007312100-KNHC-WTNT45-TCDAT5"
    )
    assert res[0][0] == ans


def test_200731_bogus_timezone():
    """Test that we don't bomb out with unknown timezone."""
    tp = productparser(
        get_test_file("TCDAT5_CVT.txt").replace(" CVT ", " ZZT ")
    )
    res = tp.get_jabbers("http://localhost")
    ans = (
        "NHC issues TCDAT5 (TCD) at Jul 31, 8:00 PM ZZT "
        "http://localhost?pid=202007312000-KNHC-WTNT45-TCDAT5"
    )
    assert res[0][0] == ans
    assert len(tp.warnings) == 1
    assert tp.warnings[0] == "product timezone 'ZZT' unknown"


def test_180321_mst():
    """Do we do the right thing with MST products whilst in DST"""
    tp = productparser(get_test_file("AFDMST.txt"))
    res = tp.get_jabbers("http://localhost")
    ans = (
        "PSR issues Area Forecast Discussion (AFD) at Mar 21, 5:15 AM "
        "MST http://localhost?pid=201803211215-KPSR-FXUS65-AFDPSR-AAA"
    )
    assert res[0][0] == ans


def test_180130_chst():
    """Whoa, our offset for CHST appears to be wrong"""
    tp = productparser(get_test_file("CHST.txt"))
    res = utc(2018, 1, 30, 20, 12)
    assert tp.valid == res


def test_170411_fakemnd():
    """This RTP has a quasi-faked timestamp in the header causing error"""
    utcnow = utc(2017, 4, 10, 23, 50)
    tp = productparser(get_test_file("RTPSGX.txt"), utcnow=utcnow)
    res = utc(2017, 4, 10, 23, 30)
    assert tp.valid == res
    res = utc(2017, 4, 10, 23, 24)
    assert tp.wmo_valid == res


def test_210120_numeric_afos():
    """Test that a AFOS ID that starts with a number is OK."""
    replacement = "3MWBRO"
    text = get_test_file("MWWBRO.txt").replace("MWWBRO", replacement)
    assert productparser(text).afos == replacement


def test_151024_cae():
    """Make sure this CAE product works and does not throw an UGC error"""
    tp = productparser(get_test_file("CAEIA.txt"))
    assert tp.afos == "CAEIA"


def test_resent():
    """Make sure we can tell a ...RESENT product"""
    tp = productparser(get_test_file("MWWBRO.txt"))
    assert tp.is_resent()


def test_wmoheader():
    """ " Make sure we can handle some header variations"""
    ar = [
        "FTUS43 KOAX 102320    ",
        "FTUS43 KOAX 102320  COR ",
        "FTUS43 KOAX 102320  COR  ",
        "FTUS43 KOAX 102320",
    ]
    for item in ar:
        assert WMO_RE.match(item) is not None


def test_rfd():
    """Parse a RFD"""
    tp = productparser(get_test_file("RFDOAX.txt"))
    assert tp.get_channels()[0] == "RFDOAX"
    j = tp.get_jabbers("http://localhost")
    ans = (
        "OAX issues Grassland Fire Danger "
        "(RFD) at Jan 19, 4:10 AM CST ...MODERATE FIRE DANGER TODAY... "
        "http://localhost?pid=201501191010-KOAX-FNUS63-RFDOAX"
    )
    assert j[0][0] == ans


def test_hwo():
    """Parse a HWO"""
    tp = productparser(get_test_file("HWO/HWO.txt"))
    assert tp.get_channels()[0] == "HWOLOT"
    j = tp.get_jabbers("http://localhost")
    ans = (
        "LOT issues Hazardous Weather Outlook "
        "(HWO) at Jan 8, 3:23 PM CST "
        "http://localhost?pid=201301082123-KLOT-FLUS43-HWOLOT"
    )
    assert j[0][0] == ans


def test_140710_wmoheader_fail():
    """Make sure COR in WMO header does not trip us up"""
    tp = product.TextProduct(get_test_file("MANANN.txt"))
    assert tp.afos == "MANANN"
    assert tp.is_correction()


def test_now_jabber():
    """See if we can process a NOW and get the jabber result"""
    tp = product.TextProduct(get_test_file("NOWDMX.txt"))
    j = tp.get_jabbers("http://localhost")
    ans = (
        "DMX issues Short-term Forecast (NOW) at Mar 4, 8:42 AM CST "
        "http://localhost?pid=201003041442-KDMX-FPUS73-NOWDMX"
    )
    assert j[0][0] == ans


def test_nomnd_with_timestamp():
    """Make sure we process timestamps correctly when there is no MND"""
    utcnow = utc(2013, 12, 31, 18)
    tp = product.TextProduct(get_test_file("MAVWC0.txt"), utcnow=utcnow)
    ts = utc(2014, 1, 1)
    assert tp.valid == ts


def test_empty():
    """see what happens when we send a blank string"""
    with pytest.raises(TextProductException):
        product.TextProduct("")


def test_invalid_mnd_date():
    """Check parsing of timestamp"""
    answer = utc(2013, 1, 3, 6, 16)
    tp = product.TextProduct(get_test_file("CLI/CLINYC.txt"))
    assert tp.valid == answer


def test_ugc_error130214():
    """Check parsing of SPSJAX"""
    tp = product.TextProduct(get_test_file("SPS/SPSJAX.txt"))
    assert tp.segments[0].ugcs, [
        ugc.UGC("FL", "Z", 23),
        ugc.UGC("FL", "Z", 25),
        ugc.UGC("FL", "Z", 30),
        ugc.UGC("FL", "Z", 31),
        ugc.UGC("FL", "Z", 32),
    ]


def test_no_ugc():
    """Product that does not have UGC encoding"""
    data = get_test_file("CCFMOB.txt")
    tp = product.TextProduct(data)
    assert not tp.segments[0].ugcs


def test_ugc_invalid_coding():
    """UGC code regression"""
    data = get_test_file("FLW_badugc.txt")
    tp = product.TextProduct(data)
    # self.assertRaises(ugc.UGCParseException, product.TextProduct, data )
    assert not tp.segments[0].ugcs


def test_000000_ugctime():
    """When there is 000000 as UGC expiration time"""
    tp = product.TextProduct(get_test_file("RECFGZ.txt"))
    assert tp.segments[0].ugcexpire is None


def test_stray_space_in_ugc():
    """When there are stray spaces in the UGC!"""
    tp = product.TextProduct(get_test_file("RVDCTP.txt"))
    assert len(tp.segments[0].ugcs) == 28


def test_ugc_in_hwo():
    """Parse UGC codes in a HWO"""
    tp = product.TextProduct(get_test_file("HWO/HWO.txt"))
    assert tp.segments[1].ugcs == [
        ugc.UGC("LM", "Z", 740),
        ugc.UGC("LM", "Z", 741),
        ugc.UGC("LM", "Z", 742),
        ugc.UGC("LM", "Z", 743),
        ugc.UGC("LM", "Z", 744),
        ugc.UGC("LM", "Z", 745),
    ]


def test_afos():
    """check AFOS PIL Parsing"""
    tp = product.TextProduct(get_test_file("AFD.txt"))
    assert tp.afos == "AFDBOX"


def test_source():
    """check tp.source Parsing"""
    tp = product.TextProduct(get_test_file("AFD.txt"))
    assert tp.source == "KBOX"


def test_wmo():
    """check tp.wmo Parsing"""
    tp = product.TextProduct(get_test_file("AFD.txt"))
    assert tp.wmo == "FXUS61"


def test_notml():
    """check TOR without TIME...MOT...LOC"""
    tp = product.TextProduct(get_test_file("TOR.txt"))
    assert tp.segments[0].tml_dir is None


def test_signature():
    """check svs_search"""
    tp = product.TextProduct(get_test_file("TOR.txt"))
    assert tp.get_signature() == "CBD"


def test_spanishMWW():
    """check spanish MWW does not break things"""
    tp = product.TextProduct(get_test_file("MWWspanish.txt"))
    assert tp.z is None


def test_svs_search():
    """check svs_search"""
    tp = product.TextProduct(get_test_file("TOR.txt"))
    ans = (
        "* AT 1150 AM CDT...THE NATIONAL WEATHER SERVICE "
        "HAS ISSUED A TORNADO WARNING FOR DESTRUCTIVE "
        "WINDS OVER 110 MPH IN THE EYE WALL AND INNER RAIN "
        "BANDS OF HURRICANE KATRINA. THESE WINDS WILL "
        "OVERSPREAD MARION...FORREST AND LAMAR COUNTIES "
        "DURING THE WARNING PERIOD."
    )
    assert tp.segments[0].svs_search() == ans


def test_product_id():
    """check valid Parsing"""
    tp = product.TextProduct(get_test_file("AFD.txt"))
    assert tp.get_product_id() == "201211270001-KBOX-FXUS61-AFDBOX"


def test_valid():
    """check valid Parsing"""
    tp = product.TextProduct(get_test_file("AFD.txt"))
    ts = utc(2012, 11, 27, 0, 1)
    assert tp.valid == ts


def test_FFA():
    """check FFA Parsing"""
    tp = product.TextProduct(get_test_file("FFA.txt"))
    assert tp.segments[0].get_hvtec_nwsli() == "NWYI3"


def test_valid_nomnd():
    """check valid (no Mass News) Parsing"""
    utcnow = utc(2012, 11, 27)
    tp = product.TextProduct(get_test_file("AFD_noMND.txt"), utcnow=utcnow)
    ts = utc(2012, 11, 27, 0, 1)
    assert tp.valid == ts


def test_headlines():
    """check headlines Parsing"""
    tp = product.TextProduct(get_test_file("AFDDMX.txt"))
    ans = [
        "UPDATED FOR 18Z AVIATION DISCUSSION",
        "Bogus second line with a new line",
    ]
    assert tp.segments[0].headlines == ans


def test_tml():
    """Test TIME...MOT...LOC parsing"""
    ts = utc(2012, 5, 31, 23, 10)
    tp = product.TextProduct(get_test_file("SVRBMX.txt"))
    assert tp.segments[0].tml_dir == 238
    assert tp.segments[0].tml_valid == ts
    assert tp.segments[0].tml_sknt == 39
    assert tp.segments[0].tml_giswkt == "SRID=4326;POINT(-88.53 32.21)"


def test_bullets():
    """Test bullets parsing"""
    tp = product.TextProduct(get_test_file("TORtag.txt"))
    assert len(tp.segments[0].bullets) == 4
    ans = (
        "LOCATIONS IMPACTED INCLUDE... MARYSVILLE...LOVILIA"
        "...HAMILTON AND BUSSEY."
    )
    assert tp.segments[0].bullets[3] == ans

    tp = product.TextProduct(get_test_file("FLSDMX.txt"))
    assert len(tp.segments[2].bullets) == 7
    ans = (
        "IMPACT...AT 35.5 FEET...WATER AFFECTS 285TH "
        "AVENUE NEAR SEDAN BOTTOMS...OR JUST EAST OF THE "
        "INTERSECTION OF 285TH AVENUE AND 570TH STREET."
    )
    assert tp.segments[2].bullets[6] == ans


def test_tags():
    """Test tags parsing"""
    tp = product.TextProduct(get_test_file("TORtag.txt"))
    assert tp.segments[0].tornadotag == "OBSERVED"
    assert tp.segments[0].damagetag == "SIGNIFICANT"


def test_longitude_processing():
    """Make sure that parsed longitude values are negative!"""
    tp = product.TextProduct(get_test_file("SVRBMX.txt"))
    assert abs(tp.segments[0].sbw.exterior.xy[0][0] - -88.39) < 0.01


def test_giswkt():
    """Test giswkt parsing"""
    tp = product.TextProduct(get_test_file("SVRBMX.txt"))
    assert abs(tp.segments[0].sbw.area - 0.16) < 0.01

    ans = (
        "SRID=4326;MULTIPOLYGON "
        "(((-88.390000 32.590000, -88.130000 32.760000, "
        "-88.080000 32.720000, -88.110000 32.690000, "
        "-88.040000 32.690000, -88.060000 32.640000, "
        "-88.080000 32.640000, -88.060000 32.590000, "
        "-87.930000 32.630000, -87.870000 32.570000, "
        "-87.860000 32.520000, -87.920000 32.520000, "
        "-87.960000 32.470000, -88.030000 32.430000, "
        "-88.050000 32.370000, -87.970000 32.350000, "
        "-87.940000 32.310000, -88.410000 32.310000, "
        "-88.390000 32.590000)))"
    )
    assert tp.segments[0].giswkt == ans
