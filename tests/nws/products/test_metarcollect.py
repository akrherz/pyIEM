"""Make sure our METAR parsing works!"""

import pytest
from pyiem.reference import TRACE_VALUE
from pyiem.nws.products import metarcollect
from pyiem.util import utc, get_test_file

PARSER = metarcollect.parser
NWSLI_PROVIDER = {
    "CYYE": dict(network="CA_BC_ASOS"),
    "QQQQ": dict(network="FAKE", tzname="America/Chicago"),
    "ZZZZ": dict(network="FAKE", tzname="Nowhere'sVille"),
    "SPS": dict(wfo="OUN"),
    "MIA": dict(wfo="MIA"),
    "ALO": dict(wfo="DSM"),
    "EST": dict(wfo="EST"),
}
metarcollect.JABBER_SITES = {"KALO": None}


def create_entries(cursor):
    """Return a disposable database cursor."""
    # Create fake station, so we can create fake entry in summary
    # and current tables
    cursor.execute(
        "INSERT into stations(id, network, iemid, tzname) "
        "VALUES ('QQQQ', 'FAKE', -1, 'America/Chicago')"
    )
    cursor.execute(
        "INSERT into current(iemid, valid) VALUES (-1, '2015-09-01 00:00+00')"
    )
    cursor.execute(
        "INSERT into summary_2015(iemid, day) VALUES (-1, '2015-09-01')"
    )


def test_future_crosses():
    """Test some hairy logic with METARs from the future."""
    utcnow = utc(2015, 9, 15, 23)
    data = "\r\r\n".join(
        [
            "000 ",
            "SAUS44 KISU 152300",
            "METAR "
            "QQQQ 172153Z 23016G25KT 10SM FEW025 SCT055 17/04 A2982 RMK ",
            "AO2 SLP104 T01720044=",
        ]
    )
    prod = PARSER(data, utcnow=utcnow, nwsli_provider=NWSLI_PROVIDER)
    assert not prod.metars


@pytest.mark.parametrize("database", ["iem"])
def test_corrected(dbcursor):
    """Test that the COR does not get dropped from the raw METAR."""
    create_entries(dbcursor)
    code = (
        "QQQQ 121751Z COR VRB03KT 10SM SCT043 32/19 A3002 RMK AO2 SLP144 "
        "T03220194 10328 20228 58011 $="
    )
    mtr = metarcollect.METARReport(code, year=2020, month=10)
    iemob, _ = mtr.to_iemaccess(dbcursor)
    assert mtr.code == iemob.data["raw"]


@pytest.mark.parametrize("database", ["iem"])
def test_bad_tzname(dbcursor):
    """Test what happens with a bad tzname."""
    utcnow = utc(2015, 9, 1, 23)
    data = "\r\r\n".join(
        [
            "000 ",
            "SAUS44 KISU 011200",
            "METAR ",
            "ZZZZ 012153Z 23016G25KT 10SM FEW025 SCT055 17/04 A2982 RMK ",
            "AO2 SLP104 T01720044 10178 20122 56014=",
        ]
    )
    prod = PARSER(data, utcnow=utcnow, nwsli_provider=NWSLI_PROVIDER)
    prod.metars[0].to_iemaccess(dbcursor)


@pytest.mark.parametrize("database", ["iem"])
def test_issue92_6hour(dbcursor):
    """Can we get the 6 hour right."""
    create_entries(dbcursor)
    utcnow = utc(2015, 9, 1, 23)
    header = "000 \r\r\nSAUS44 KISU 011200\r\r\nMETAR "
    # 4 PM temp is 63
    data = header + (
        "QQQQ 012153Z 23016G25KT 10SM FEW025 SCT055 17/04 A2982 RMK "
        "AO2 SLP104 T01720044=\r\r\n"
    )
    prod = PARSER(data, utcnow=utcnow, nwsli_provider=NWSLI_PROVIDER)
    iemob, _ = prod.metars[0].to_iemaccess(dbcursor)
    iemob.load(dbcursor)
    assert iemob.data["max_tmpf"] == 63
    # 5 PM temp is 61, but has 6 hour low of 54, high of 64
    data = header + (
        "QQQQ 012253Z 27005KT 10SM FEW025 BKN055 16/05 A2982 RMK AO2 "
        "SLP105 T01610050 10178 20122 56014=\r\r\n"
    )
    prod = PARSER(data, utcnow=utcnow, nwsli_provider=NWSLI_PROVIDER)
    iemob, _ = prod.metars[0].to_iemaccess(dbcursor)
    iemob.load(dbcursor)
    assert iemob.data["max_tmpf"] == 64
    assert iemob.data["min_tmpf"] == 54


@pytest.mark.parametrize("database", ["iem"])
def test_issue92_6hour_nouse(dbcursor):
    """We should not use the 6 hour in this case."""
    create_entries(dbcursor)
    utcnow = utc(2015, 9, 1, 9)
    header = "000 \r\r\nSAUS44 KISU 011200\r\r\nMETAR "
    # 1 AM temp is 63
    data = header + (
        "QQQQ 010653Z 23016G25KT 10SM FEW025 SCT055 17/04 A2982 RMK "
        "AO2 SLP104 T01720044=\r\r\n"
    )
    prod = PARSER(data, utcnow=utcnow, nwsli_provider=NWSLI_PROVIDER)
    iemob, _ = prod.metars[0].to_iemaccess(dbcursor)
    iemob.load(dbcursor)
    assert iemob.data["max_tmpf"] == 63
    # 2 AM temp is 61, but has 6 hour low of 54, high of 64
    data = header + (
        "QQQQ 010753Z 27005KT 10SM FEW025 BKN055 16/05 A2982 RMK AO2 "
        "SLP105 T01610050 10178 20122 56014=\r\r\n"
    )
    prod = PARSER(data, utcnow=utcnow, nwsli_provider=NWSLI_PROVIDER)
    iemob, _ = prod.metars[0].to_iemaccess(dbcursor)
    iemob.load(dbcursor)
    assert iemob.data["max_tmpf"] == 63
    assert iemob.data["min_tmpf"] == 61


@pytest.mark.parametrize("database", ["iem"])
def test_issue89_peakwind(dbcursor):
    """Are we roundtripping peak wind."""
    create_entries(dbcursor)
    code = (
        "KALO 010001Z AUTO 17027G37KT 10SM FEW030 SCT110 19/16 A2979 RMK AO2 "
        "PK WND 18049/2025 RAE48 SLP088 P0005 60014 T01890156 58046"
    )
    mtr = metarcollect.METARReport(code, year=2017, month=1)
    iemob, _ = mtr.to_iemaccess(dbcursor)
    assert iemob.data["peak_wind_time"] == utc(2016, 12, 31, 20, 25)


@pytest.mark.parametrize("database", ["iem"])
def test_190118_ice(dbcursor):
    """Process a ICE Report."""
    create_entries(dbcursor)
    mtr = metarcollect.METARReport(
        (
            "KABI 031752Z 30010KT 6SM BR FEW009 OVC036 02/01 A3003 RMK AO2 "
            "SLP176 60001 I1000 T00170006 10017 21006 56017"
        )
    )
    assert mtr.ice_accretion_1hr is not None
    iemob, _ = mtr.to_iemaccess(dbcursor)
    assert iemob.data["ice_accretion_1hr"] == TRACE_VALUE


def test_180604_nonascii():
    """See that we don't error on non-ASCII METARs"""
    utcnow = utc(2018, 6, 4)
    prod = PARSER(get_test_file("METAR/badchars.txt"), utcnow=utcnow)
    assert len(prod.metars) == 3


def test_future():
    """Can we handle products that are around the first"""
    utcnow = utc(2017, 12, 1)
    prod = PARSER(get_test_file("METAR/first.txt"), utcnow=utcnow)
    assert len(prod.metars) == 2
    assert prod.metars[0].time.month == 11
    assert prod.metars[1].time.month == 12


@pytest.mark.parametrize("database", ["iem"])
def test_180201_unparsed(dbcursor):
    """For some reason, this collective was not parsed?!?!"""
    create_entries(dbcursor)
    utcnow = utc(2018, 2, 1, 0)
    prod = PARSER(
        get_test_file("METAR/collective2.txt"),
        utcnow=utcnow,
        nwsli_provider=NWSLI_PROVIDER,
    )
    for metar in prod.metars:
        metar.to_iemaccess(dbcursor)
    assert len(prod.metars) == 35
    assert prod.metars[0].time.month == 1


def test_170824_sa_format():
    """Don't be so noisey when we encounter SA formatted products"""
    utcnow = utc(2017, 8, 24, 14)
    prod = PARSER(
        get_test_file("METAR/sa.txt"),
        utcnow=utcnow,
        nwsli_provider=NWSLI_PROVIDER,
    )
    assert not prod.metars


def test_170809_nocrcrlf():
    """Product fails WMO parsing due to usage of RTD as bbb field"""
    utcnow = utc(2017, 8, 9, 9)
    prod = PARSER(
        get_test_file("METAR/rtd_bbb.txt"),
        utcnow=utcnow,
        nwsli_provider=NWSLI_PROVIDER,
    )
    assert len(prod.metars) == 1


@pytest.mark.parametrize("database", ["iem"])
def test_metarreport(dbcursor):
    """Can we do things with the METARReport"""
    create_entries(dbcursor)
    utcnow = utc(2013, 8, 8, 12, 53)
    mtr = metarcollect.METARReport(
        (
            "SPECI CYYE 081253Z 01060KT 1/4SM FG SKC 10/10 A3006 RMK P0000 "
            "FG6 SLP188="
        )
    )
    assert mtr.wind_gust is None
    mtr.time = utcnow
    mtr.iemid = "CYYE"
    mtr.network = "CA_BC_ASOS"
    iemob, _ = mtr.to_iemaccess(dbcursor)
    assert iemob.data["station"] == "CYYE"
    assert iemob.data["phour"] == TRACE_VALUE
    assert mtr.wind_message() == "gust of 0 knots (0.0 mph) from N @ 1253Z"
    # can we round trip the gust
    iemob.load(dbcursor)
    assert iemob.data["gust"] is None


@pytest.mark.parametrize("database", ["iem"])
def test_basic(dbcursor):
    """Simple tests"""
    create_entries(dbcursor)
    utcnow = utc(2013, 8, 8, 14)
    prod = PARSER(
        get_test_file("METAR/collective.txt"),
        utcnow=utcnow,
        nwsli_provider=NWSLI_PROVIDER,
    )
    assert not prod.warnings
    assert len(prod.metars) == 11
    jmsgs = prod.get_jabbers("localhost")
    assert len(jmsgs) == 7
    ans = (
        "None,None (SPS) ASOS reports Hail -- KSPS 081352Z 10015KT 10SM "
        "TSGRRA BKN022CB BKN050 BKN200 25/16 A2967 RMK AO2 TSB38RAB25GRB49 "
        "SLP036 LTGICCCCG OHD TS OHD GR 1/3 P0000 T02500161"
    )
    assert jmsgs[0][2]["twitter"] == ans

    iemob, _ = prod.metars[1].to_iemaccess(dbcursor)
    assert abs(iemob.data["phour"] - 0.46) < 0.01

    # Run twice to trigger skip
    prod.get_jabbers("localhost")
