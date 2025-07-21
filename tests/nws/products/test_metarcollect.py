"""Make sure our METAR parsing works!"""

from collections import defaultdict
from unittest import mock

import pytest

from pyiem.nws.products import metarcollect
from pyiem.nws.products.metar_util import metar_from_dict
from pyiem.reference import TRACE_VALUE, VARIABLE_WIND_DIRECTION
from pyiem.util import get_test_file, utc

PARSER = metarcollect.parser
NWSLI_PROVIDER = {
    "CYYE": dict(network="CA_BC_ASOS"),
    "QQQQ": dict(network="FAKE", tzname="America/Chicago"),
    "ZZZZ": dict(network="FAKE", tzname="Nowhere'sVille", iemid=-1),
    "SPS": dict(wfo="OUN"),
    "MIA": dict(wfo="MIA"),
    "ALO": dict(wfo="DSM"),
    "EST": dict(wfo="EST"),
    "MWN": dict(wfo="DMX"),
}
metarcollect.JABBER_SITES = {"KALO": None}
metarcollect.WIND_ALERT_THRESHOLD_KTS_BY_ICAO["KMWN"] = 70


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


def test_gh740_rounding():
    """Test our rounding logic."""
    for x in [31.9, 32.1]:
        assert metarcollect.normalize_temp(x) == 32
    assert abs(metarcollect.normalize_temp(32.2) - 32.2) < 0.01
    assert abs(metarcollect.normalize_temp(31.8) - 31.8) < 0.01


def test_gh683_wind_gust_channels():
    """Test that we don't get a default channel used for this alert."""
    utcnow = utc(2022, 12, 20, 4)
    text = get_test_file("METAR/kmwn.txt")
    prod = PARSER(text, utcnow=utcnow, nwsli_provider=NWSLI_PROVIDER)
    j = prod.get_jabbers("")
    assert "DMX" not in j[0][2]["channels"].split(",")
    text = text.replace("G65KT", "G100KT")
    prod = PARSER(text, utcnow=utcnow, nwsli_provider=NWSLI_PROVIDER)
    j = prod.get_jabbers("")
    assert "DMX" in j[0][2]["channels"].split(",")


def test_normid():
    """Test normalization."""
    assert metarcollect.normid("KDSM") == "DSM"


def test_future_crosses():
    """Test some hairy logic with METARs from the future."""
    utcnow = utc(2015, 9, 15, 23)
    data = "\r\r\n".join(
        [
            "000 ",
            "SAUS44 KISU 152300",
            "METAR "
            + "QQQQ 172153Z 23016G25KT 10SM FEW025 SCT055 17/04 A2982 RMK ",
            "AO2 SLP104 T01720044=",
        ]
    )
    prod = PARSER(data, utcnow=utcnow, nwsli_provider=NWSLI_PROVIDER)
    assert not prod.metars


@pytest.mark.parametrize("database", ["iem"])
def test_250721_wind_date(dbcursor):
    """Test that the peak wind date we get is correct."""
    create_entries(dbcursor)
    code = (
        "QQQQ 302355Z AUTO 02028G45KT 010V080 1 3/4SM RA BKN006 BKN007 08/07 "
        "A2975 RMK AO2 PK WND 32046/2301 RAB2255 SLP077 P0035 60151 T00760067 "
        "10085 20067 58016 $"
    )
    prod = mock.Mock()
    prod.valid = utc(2025, 7, 1, 0, 10)
    prod.utcnow = prod.valid
    mtr = metarcollect.to_metar(prod, code)
    iemob, _ = metarcollect.to_iemaccess(dbcursor, mtr, -1, "America/Chicago")
    assert iemob.data["peak_wind_time"] == utc(2025, 6, 30, 23, 1)


@pytest.mark.parametrize("database", ["iem"])
def test_corrected(dbcursor):
    """Test that the COR does not get dropped from the raw METAR."""
    create_entries(dbcursor)
    code = (
        "QQQQ 131551Z COR VRB03KT 10SM SCT043 32/19 A3002 RMK AO2 SLP760 "
        "T03220194 10328 20228 58011 402500072 60010 70010 $="
    )
    prod = mock.Mock()
    prod.valid = utc(2020, 10, 13, 15)
    prod.utcnow = prod.valid
    mtr = metarcollect.to_metar(prod, code)
    iemob, _ = metarcollect.to_iemaccess(dbcursor, mtr, -1, "America/Chicago")
    assert mtr.code == iemob.data["raw"]
    assert iemob.data["mslp"] == 1076  # sick


@pytest.mark.parametrize("database", ["iem"])
def test_bad_tzname(dbcursor):
    """Test what happens with a bad tzname."""
    create_entries(dbcursor)
    utcnow = utc(2015, 9, 1, 23)
    data = "\r\r\n".join(
        [
            "000 ",
            "SAUS44 KISU 011200",
            "METAR ",
            "ZZZZ 012153Z 23016G25KT 10SM FEW025 SCT055 17/04 A2782 RMK ",
            "AO2 SLP076 T01720044 10178 20122 56014=",
        ]
    )
    prod = PARSER(data, utcnow=utcnow, nwsli_provider=NWSLI_PROVIDER)
    iemob, _ = metarcollect.to_iemaccess(
        dbcursor, prod.metars[0], -1, "America/Chicago"
    )
    assert abs(iemob.data["mslp"] - 907.6) < 0.01  # sick


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
    iemob, _ = metarcollect.to_iemaccess(
        dbcursor, prod.metars[0], -1, "America/Chicago"
    )
    iemob.load(dbcursor)
    assert iemob.data["max_tmpf"] == 63
    # 5 PM temp is 61, but has 6 hour low of 54, high of 64
    data = header + (
        "QQQQ 012253Z 27005KT 10SM FEW025 BKN055 16/05 A2982 RMK AO2 "
        "SLP105 T01610050 10178 20122 56014=\r\r\n"
    )
    prod = PARSER(data, utcnow=utcnow, nwsli_provider=NWSLI_PROVIDER)
    iemob, _ = metarcollect.to_iemaccess(
        dbcursor, prod.metars[0], -1, "America/Chicago"
    )
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
    iemob, _ = metarcollect.to_iemaccess(
        dbcursor, prod.metars[0], -1, "America/Chicago"
    )
    iemob.load(dbcursor)
    assert iemob.data["max_tmpf"] == 63
    # 2 AM temp is 61, but has 6 hour low of 54, high of 64
    data = header + (
        "QQQQ 010753Z 27005KT 10SM FEW025 BKN055 16/05 A2982 RMK AO2 "
        "SLP105 T01610050 10178 20122 56014=\r\r\n"
    )
    prod = PARSER(data, utcnow=utcnow, nwsli_provider=NWSLI_PROVIDER)
    iemob, _ = metarcollect.to_iemaccess(
        dbcursor, prod.metars[0], -1, "America/Chicago"
    )
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
    prod = mock.Mock()
    prod.valid = utc(2017, 1)
    prod.utcnow = utc(2017, 1)
    mtr = metarcollect.to_metar(prod, code)
    iemob, _ = metarcollect.to_iemaccess(dbcursor, mtr, -1, "America/Chicago")
    assert iemob.data["peak_wind_time"] == utc(2016, 12, 31, 20, 25)


@pytest.mark.parametrize("database", ["iem"])
def test_190118_ice(dbcursor):
    """Process a ICE Report."""
    create_entries(dbcursor)
    prod = mock.Mock()
    prod.valid = utc(2022, 10, 3, 17)
    prod.utcnow = utc(2022, 10, 3, 17)
    mtr = metarcollect.to_metar(
        prod,
        (
            "KABI 031752Z 30010KT 6SM BR FEW009 OVC036 02/01 A3003 RMK AO2 "
            "SLP176 60001 I1000 T00170006 10017 21006 56017"
        ),
    )
    assert mtr.ice_accretion_1hr is not None
    iemob, _ = metarcollect.to_iemaccess(dbcursor, mtr, -1, "America/Chicago")
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
        metarcollect.to_iemaccess(dbcursor, metar, -1, "America/Chicago")
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
    prod = mock.Mock()
    prod.valid = utcnow
    prod.utcnow = utcnow
    mtr = metarcollect.to_metar(
        prod,
        (
            "SPECI CYYE 081253Z 01060KT 1/4SM FG SKC 10/10 A3006 RMK P0000 "
            "FG6 SLP188="
        ),
    )
    assert mtr.wind_gust is None
    mtr.time = utcnow
    iemob, _ = metarcollect.to_iemaccess(dbcursor, mtr, -1, "America/Chicago")
    assert iemob.data["phour"] == TRACE_VALUE
    ans = "gust of 0 knots (0.0 mph) from N @ 1253Z"
    assert metarcollect.wind_message(mtr)[0] == ans
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

    iemob, _ = metarcollect.to_iemaccess(
        dbcursor, prod.metars[1], -1, "America/Chicago"
    )
    assert abs(iemob.data["phour"] - 0.46) < 0.01

    # Run twice to trigger skip
    prod.get_jabbers("localhost")


def get_example_metars():
    """Return some example METARs."""
    to_test = [
        "25004KT 10SM CLR M04/M07 A3004 RMK AO2 SLP180 T10391072",
        "17005KT 4SM RA BR OVC005 08/08 A2908 RMK "
        + "AO2 SLP849 P0008 T00830083",
        "28090G102KT 0SM -SN FZFG BLSN VV000 M14/M14 RMK AO2 T11401140",
        "///04KT 10SM CLR M01/M10 A2986 RMK AO2 T10061102",
        "26010KT 9SM -SN OVC037 M02/M08 A2978 "
        + "RMK AO2 SLP091 P0000 60000 T10221078",
        "12005KT 10SM OVC025 08/05 A3041 RMK AO2 "
        + "SLP297 P0000 60003 70003 T00780050",
        "12005KT 10SM 08/05 A3041 RMK AO2 SLP297 P0000 60003 70003 T00780050",
        "06014KT BKN025 06/M03 A3043 RMK AO2 T00611035",
        "26010KT 1/16SM -SN OVC037 M02/M08 A2978 "
        + "RMK AO2 SLP091 P0000 60000 T10221078",
        "26010KT 1/8SM -SN OVC037 M02/M08 A2978 "
        + "RMK AO2 SLP091 P0000 60000 T10221078",
        "26010KT 1/4SM -SN OVC037 M02/M08 A2978 "
        + "RMK AO2 SLP091 P0000 60000 T10221078",
        "26010KT 3/8SM -SN OVC037 M02/M08 A2978 "
        + "RMK AO2 SLP091 P0000 60000 T10221078",
        "26010KT 1/2SM -SN OVC037 M02/M08 A2978 "
        + "RMK AO2 SLP091 P0000 60000 T10221078",
        "26010KT 1SM -SN OVC037 M02/M08 A2978 "
        + "RMK AO2 SLP091 P0000 60000 T10221078",
        "26010KT 1 1/2SM -SN OVC037 M02/M08 A2978 "
        + "RMK AO2 SLP091 P0000 60000 T10221078",
        "26010KT 2SM -SN OVC037 M02/M08 A2978 "
        + "RMK AO2 SLP091 P0000 60000 T10221078",
        "26010KT 2 1/2SM -SN OVC037 M02/M08 A2978 "
        + "RMK AO2 SLP091 P0000 60000 T10221078",
        # Theoretical
        "260//KT 2 1/2SM -SN OVC037 M02/M08 A2978 "
        + "RMK AO2 SLP091 P0000 60000 T10221078",
        "260//KT 2 1/2SM -SN OVC037 A2978 RMK AO2 SLP091 P0000 60000",
        "00000KT 10SM CLR M37/ A3037 RMK AO2 SLP307 T1367",
    ]
    for ans in to_test:
        yield f"METAR QQQQ 221253Z AUTO {ans}"


@pytest.mark.parametrize("database", ["iem"])
@pytest.mark.parametrize("ans", get_example_metars())
def test_metar_roundtrip(dbcursor, ans):
    """Test the roundtripping of METARs."""
    create_entries(dbcursor)
    prod = mock.Mock()
    prod.valid = utc(2025, 3, 22, 13)
    prod.utcnow = prod.valid
    mtr = metarcollect.to_metar(prod, ans)
    iemob, _ = metarcollect.to_iemaccess(dbcursor, mtr, -1, "America/Chicago")
    iemob.data["station"] = "QQQQ"
    assert metar_from_dict(iemob.data) == ans


def test_metar_from_dict_with_variable_wind():
    """Test the METAR from dict with variable wind."""
    values = defaultdict(lambda: None)
    values.update(
        **{
            "valid": utc(2025, 1, 1, 0),
            "station": "KOKC",
            "drct": VARIABLE_WIND_DIRECTION,
            "sknt": 3,
        }
    )

    assert metar_from_dict(values) == "METAR KOKC 010000Z AUTO VRB03KT RMK AO2"
