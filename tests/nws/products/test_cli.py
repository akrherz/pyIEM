"""Test CLI products"""
import datetime

import pytest
from pyiem.reference import TRACE_VALUE
from pyiem.util import utc, get_test_file
from pyiem.nws.products import parser as cliparser
from pyiem.nws.products.cli import get_number, CLIException

NWSLI_PROVIDER = {
    "KIAD": dict(name="HOUSTON INTERCONTINENTAL", access_network="ZZ_ASOS"),
    "KDMH": dict(name="", attributes={"MAPS_TO": "QQQ|ZZ_ASOS"}),
    "KHOU": dict(name="HOUSTON/HOBBY AIRPORT", access_network="ZZ_ASOS"),
    "KRDU": dict(name="RALEIGH-DURHAM", access_network="NC_ASOS"),
    "PADQ": dict(name="KODIAK", access_network="AK_ASOS"),
    "PAKN": dict(name="KING SALMON", access_network="AK_ASOS"),
    "PANC": dict(name="ANCHORAGE AK", access_network="AK_ASOS"),
    "PASN": dict(name="SAINT PAUL ISLAND", access_network="AK_ASOS"),
    "PBET": dict(name="BETHEL", access_network="AK_ASOS"),
    "PCBD": dict(name="COLD BAY", accesss_network="AK_ASOS"),
    "POME": dict(name="NOME WSO AP", access_network="AK_ASOS"),
}


def factory(fn):
    """Common cliparser logic."""
    return cliparser(get_test_file(fn), nwsli_provider=NWSLI_PROVIDER)


def test_clippg3():
    """Test another format from PPG."""
    prod = cliparser(get_test_file("CLI/CLIPPG3.txt"))
    assert prod.data[0]["data"]["temperature_maximum_record_years"][0] == 2009
    assert prod.data[0]["data"]["temperature_maximum_time"] == "0150 PM"


def test_mintempyear_failure():
    """Test that we can handle some GIGO here."""
    text = get_test_file("CLI/CLISAD.txt")
    prod = cliparser(text)
    assert 2002 in prod.data[0]["data"]["temperature_minimum_record_years"]


def test_clirdu():
    """Test handling of another CLI variant."""
    text = get_test_file("CLI/CLIRDU_v2.txt")
    prod = cliparser(text)
    assert prod.data[0]["data"].get("temperature_maximum") == 57


def test_invalid_temperature_year_second_line():
    """Test that we don't allow an invalid year in the second line."""
    text = get_test_file("CLI/CLIEKA.txt")
    text = text.replace("    1978    ", "    9999    ")
    prod = cliparser(text)
    assert "9999" in prod.warnings[1]


def test_invalid_temperature_year():
    """Test that we don't allow an invalid year."""
    text = get_test_file("CLI/CLIRDU.txt")
    text = text.replace("1945  64", " 945  64")
    prod = cliparser(text)
    assert prod.data[0]["data"].get("temperature_maximum_record_years") is None


def test_clippg2():
    """Test that we handle the enlongated format from PPG."""
    prod = factory("CLI/CLIPPG2.txt")
    assert prod.data[0]["data"]["temperature_maximum_record_years"][0] == 1988


def test_climuo():
    """Test that we handle the shortend format from BOI."""
    prod = factory("CLI/CLIMUO.txt")
    assert prod.data[0]["data"]["temperature_maximum_record_years"][0] == 1990


def test_issue408_estimated():
    """Test that we catch some GIO with estimated temperature flag."""
    prod = factory("CLI/CLIRDU.txt")
    assert prod.warnings[0].find("repaired") > -1
    assert prod.data[0]["data"]["temperature_maximum_record_years"][0] == 1945


@pytest.mark.parametrize("database", ["iem"])
def test_issue396_snow_normal(dbcursor):
    """See that snow_normal goes to the database."""
    prod = cliparser(get_test_file("CLI/CLICVG_colon.txt"))
    prod.sql(dbcursor)
    dbcursor.execute(
        "SELECT snow_normal, snowdepth from cli_data where "
        "station = 'KCVG' and valid = '2021-02-04'"
    )
    row = dbcursor.fetchone()
    assert abs(row[0] - 0.2) < 0.01
    assert abs(row[1] - 1) < 0.01


def test_210206_colon():
    """Test that we can handle colons in the timestamp."""
    prod = cliparser(get_test_file("CLI/CLICVG_colon.txt"))
    assert prod.data[0]["data"]["temperature_maximum"] == 39
    assert prod.data[0]["data"]["temperature_maximum_normal"] == 40
    assert prod.data[0]["data"]["snow_today_normal"] == 0.2


def test_wrong_wmo_header():
    """Test that we raise an exception for this."""
    prod = cliparser(
        get_test_file("CLI/CLIANC.txt").replace("CDAK48", "XXXX48")
    )
    assert prod.valid


def test_bad_diction():
    """Test that we raise an exception for this."""
    with pytest.raises(CLIException):
        factory("CLI/CLIPPG.txt")


def test_bad_headline():
    """Test that we raise an exception for this."""
    with pytest.raises(CLIException):
        cliparser(
            get_test_file("CLI/CLIANC.txt").replace("WEATHER ITEM", "XXXX48"),
            nwsli_provider=NWSLI_PROVIDER,
        )


def test_bad_temperature():
    """Test that we raise an exception for this."""
    with pytest.raises(CLIException):
        cliparser(
            get_test_file("CLI/CLIANC.txt").replace(
                "TEMPERATURE", "TEMP3RATURE"
            ),
            nwsli_provider=NWSLI_PROVIDER,
        )


def test_no_weather_item():
    """Test that we raise an exception for this."""
    with pytest.raises(CLIException):
        cliparser(get_test_file("CLI/CLIHOU.txt").replace("WEATHER", "X"))


def test_unknown_station_in_multi():
    """Test that we raise an exception for this."""
    with pytest.raises(CLIException):
        cliparser(get_test_file("CLI/CLIHOU.txt"))


def test_parse_temperature_bad_token():
    """Test when we observe a bad temperature token."""
    prod = cliparser(
        get_test_file("CLI/CLIDMH.txt").replace("AVERAGE  ", "AV3RAG3  ")
    )
    assert prod.data


def test_get_number():
    """Test the number to float conversion."""
    assert get_number("") is None
    assert get_number("ABC") is None


@pytest.mark.parametrize("database", ["iem"])
def test_190510_parsefail(dbcursor):
    """This CLIDMH is not happy."""
    # Create an entry to actually update
    dbcursor.execute(
        "INSERT into stations(iemid, id, network) VALUES (%s, %s, %s)",
        (-1, "QQQ", "ZZ_ASOS"),
    )
    prod = factory("CLI/CLIDMH.txt")
    assert not prod.warnings
    pd0 = prod.data[0]
    assert pd0["access_network"] == "ZZ_ASOS"
    assert prod.data[0]["data"]["temperature_maximum"] == 74
    prod.sql(dbcursor)
    # Run twice to hit a no-op
    prod = factory("CLI/CLIDMH.txt")
    prod.sql(dbcursor)
    assert not prod.warnings


def test_200423_missing_skycover():
    """Test that we are processing skycover properly."""
    prod = factory("CLI/CLICVG.txt")
    assert prod.data[0]["data"]["average_sky_cover"] == 0.4


@pytest.mark.parametrize("database", ["iem"])
def test_database_progression(dbcursor):
    """Test our deletion logic."""

    def _get():
        """Fetch our current value."""
        dbcursor.execute(
            "SELECT high from cli_data "
            "where station = 'KCVG' and valid = '2020-04-22'"
        )
        return dbcursor.fetchone()["high"]

    prod = factory("CLI/CLICVG.txt")
    prod.sql(dbcursor)
    assert abs(_get() - 69.0) < 0.01
    prod = factory("CLI/CLICVG_older.txt")
    prod.sql(dbcursor)
    assert abs(_get() - 69.0) < 0.01
    prod = factory("CLI/CLICVG_newer.txt")
    prod.sql(dbcursor)
    assert abs(_get() - 70.0) < 0.01


@pytest.mark.parametrize("database", ["iem"])
def test_issue15_wind(dbcursor):
    """Test parsing of available wind information."""
    prod = factory("CLI/CLICVG.txt")
    assert abs(prod.data[0]["data"]["resultant_wind_speed"] - 6.0) < 0.01
    assert abs(prod.data[0]["data"]["resultant_wind_direction"] - 180.0) < 0.01
    assert abs(prod.data[0]["data"]["highest_wind_speed"] - 20.0) < 0.01
    assert abs(prod.data[0]["data"]["highest_wind_direction"] - 220.0) < 0.01
    assert abs(prod.data[0]["data"]["highest_gust_speed"] - 26.0) < 0.01
    assert abs(prod.data[0]["data"]["highest_gust_direction"] - 230.0) < 0.01
    assert abs(prod.data[0]["data"]["average_wind_speed"] - 7.7) < 0.01
    prod.sql(dbcursor)
    assert prod.data[0]["db_station"] == "KCVG"


def test_180208_issue56_tweetmissing():
    """Report None values as missing, not None"""
    prod = factory("CLI/CLIFFC.txt")
    j = prod.get_jabbers("http://localhost", "http://localhost")
    ans = (
        'PEACHTREE CITY Oct 3 Climate: High: 79 Low: 67 Precip: 0.87" '
        "Snow: Missing "
        "http://localhost?pid=201410032032-KFFC-CDUS42-CLIFFC"
    )
    assert j[0][2]["twitter"] == ans
    ans = (
        "https://mesonet.agron.iastate.edu/plotting/auto/plot/218/"
        "network:NWSCLI::station:KFFC::date:2014-10-03.png"
    )
    assert j[0][2]["twitter_media"] == ans


def test_170530_none():
    """CLILWD errored in production, so we add a test!"""
    prod = factory("CLI/CLILWD.txt")
    assert prod.data[0]["data"]["temperature_maximum"] == 76


def test_170315_invalid_dup():
    """CLIANC incorrectly has two CLIs"""
    prod = factory("CLI/CLIANC.txt")
    answers = [23, 22, 31, 10, 29, 33]
    for i, answer in enumerate(answers):
        assert prod.data[i]["data"]["temperature_maximum"] == answer


def test_151019_clibna():
    """CLIBNA is a new diction"""
    prod = factory("CLI/CLIBNA.txt")
    assert prod.data[0]["data"]["temperature_maximum"] == 47


def test_150303_alaska():
    """CLIANN Attempt to account for the badly formatted CLIs"""
    prod = factory("CLI/CLIANN.txt")
    assert prod.data[0]["data"]["temperature_maximum_time"] == "0151 PM"


def test_150112_climso():
    """CLIMSO_2 found some issue with this in production?"""
    prod = factory("CLI/CLIMSO_2.txt")
    assert prod.data[0]["data"]["temperature_minimum"] == 16


def test_141230_newregime4():
    """CLIMBS has a new regime"""
    prod = factory("CLI/CLIMBS.txt")
    assert prod.data[0]["data"]["temperature_minimum"] == 18


def test_141230_newregime3():
    """CLICKV has a new regime"""
    prod = factory("CLI/CLICKV.txt")
    assert prod.data[0]["data"]["temperature_minimum"] == 33


def test_141230_newregime2():
    """CLISEW has a new regime"""
    prod = factory("CLI/CLISEW.txt")
    assert prod.data[0]["data"]["temperature_minimum"] == 34


def test_141230_newregime():
    """CLITCS has a new regime"""
    prod = factory("CLI/CLITCS.txt")
    assert prod.data[0]["data"]["temperature_minimum"] == 22


def test_141229_newregime9():
    """CLIMAI has a new regime"""
    prod = factory("CLI/CLIMAI.txt")
    assert prod.data[0]["data"]["temperature_minimum"] == 61


def test_141229_newregime8():
    """CLIECP has a new regime"""
    prod = factory("CLI/CLIECP.txt")
    assert prod.data[0]["data"]["temperature_minimum"] == 62


def test_141229_newregime7():
    """CLIBOI has a new regime"""
    prod = factory("CLI/CLIBOI.txt")
    assert prod.data[0]["data"]["temperature_minimum"] == 23


def test_141229_newregime6():
    """CLIMSO has a new regime"""
    prod = factory("CLI/CLIMSO.txt")
    assert prod.data[0]["data"]["temperature_minimum"] == 12


def test_141229_newregime4():
    """CLIOLF has a new regime"""
    prod = factory("CLI/CLIOLF.txt")
    assert prod.data[0]["data"]["temperature_average"] == -2


def test_141229_newregime5():
    """CLIICT has a new regime"""
    prod = factory("CLI/CLIICT.txt")
    assert prod.data[0]["data"]["precip_today"] == 0.00


def test_141229_newregime3():
    """CLIDRT has a new regime"""
    prod = factory("CLI/CLIDRT.txt")
    assert prod.data[0]["data"]["temperature_minimum"] == 37


def test_141229_newregime2():
    """CLIFMY has a new regime"""
    prod = factory("CLI/CLIFMY.txt")
    assert prod.data[0]["data"]["temperature_minimum"] == 63


def test_141229_newregime():
    """CLIEKA has a new regime"""
    prod = factory("CLI/CLIEKA.txt")
    assert prod.data[0]["data"]["precip_today_record_years"][0] == 1896
    assert prod.data[0]["data"]["precip_today_record_years"][1] == 1999


def test_141215_convkey():
    """CLIACT Get a warning about convert key"""
    prod = factory("CLI/CLIACT.txt")
    assert prod.data[0]["data"]["snow_today_record_years"][0] == 1947
    assert prod.data[0]["data"]["snow_today_record_years"][1] == 1925


def test_141201_clihou():
    """CLIHOU See that we can finally parse the CLIHOU product!"""
    prod = factory("CLI/CLIHOU.txt")
    assert prod.data[0]["cli_station"] == "HOUSTON INTERCONTINENTAL"
    assert prod.data[1]["cli_station"] == "HOUSTON/HOBBY AIRPORT"


def test_141114_coopaux():
    """CLIEAR Product had aux COOP data, which confused ingest"""
    prod = factory("CLI/CLIEAR.txt")
    assert prod.data[0]["data"]["precip_today"] == 0


def test_141103_recordsnow():
    """CLIBGR Make sure we can deal with record snowfall, again..."""
    prod = factory("CLI/CLIBGR.txt")
    assert prod.data[0]["data"]["snow_today"] == 12.0


@pytest.mark.parametrize("database", ["iem"])
def test_141024_recordsnow(dbcursor):
    """CLIOME See that we can handle record snowfall"""
    prod = factory("CLI/CLIOME.txt")
    assert prod.data[0]["data"]["snow_today"] == 3.6
    prod.sql(dbcursor)


def test_141022_correction():
    """CLIEWN See what happens if we have a valid product correction"""
    prod = factory("CLI/CLIEWN.txt")
    assert prod.data[0]["data"]["temperature_maximum"] == 83


def test_141013_missing():
    """CLIEST See why Esterville was not going to the database!"""
    prod = factory("CLI/CLIEST.txt")
    assert prod.data[0]["data"]["temperature_maximum"] == 62
    assert prod.data[0]["data"]["precip_month"] == 1.22


def test_141013_tracetweet():
    """CLIDSM2 Make sure we convert trace amounts in tweet to trace!"""
    prod = factory("CLI/CLIDSM2.txt")
    j = prod.get_jabbers("http://localhost", "http://localhost")
    ans = (
        "DES MOINES IA Oct 12 Climate: High: 56 "
        'Low: 43 Precip: Trace Snow: 0.0" Snow Depth: 0"'
        " http://localhost?pid=201410122226-KDMX-CDUS43-CLIDSM"
    )
    assert j[0][2]["twitter"] == ans


def test_141003_missing():
    """CLIFFC We are missing some data!"""
    prod = factory("CLI/CLIFFC.txt")
    assert prod.data[0]["data"]["temperature_maximum_normal"] == 78


def test_141003_alaska():
    """CLIBET Some alaska data was not getting processed"""
    prod = factory("CLI/CLIBET.txt")
    assert prod.data[0]["data"]["temperature_maximum"] == 17
    assert prod.data[0]["data"]["snow_jul1"] == 14.4
    assert prod.data[0]["data"]["snowdepth"] == 3


def test_140930_negative_temps():
    """CLIALO Royal screwup not supporting negative numbers"""
    prod = factory("CLI/CLIALO.txt")
    assert prod.data[0]["data"].get("temperature_minimum") == -21
    assert prod.data[0]["data"].get("temperature_minimum_record") == -21
    assert prod.data[0]["data"].get("snow_today") == 0.0
    assert prod.data[0]["data"].get("snow_today_record") == 13.2
    assert prod.data[0]["data"].get("snow_today_last") == 0.0
    assert prod.data[0]["data"].get("snow_month_last") == TRACE_VALUE
    assert prod.data[0]["data"].get("snow_jul1_last") == 11.3
    assert prod.data[0]["data"].get("average_sky_cover") is None


def test_140930_mm_precip():
    """CLIABY Make sure having MM as today's precip does not error out"""
    prod = factory("CLI/CLIABY.txt")
    assert prod.data[0]["data"].get("precip_today") is None


def test_cli():
    """CLIJUN Test the processing of a CLI product"""
    prod = factory("CLI/CLIJNU.txt")
    assert prod.data[0]["cli_valid"] == datetime.date(2013, 6, 30)
    assert prod.valid == utc(2013, 7, 1, 0, 36)
    assert prod.data[0]["data"]["temperature_maximum"] == 75
    assert prod.data[0]["data"]["temperature_maximum_time"] == "259 PM"
    assert prod.data[0]["data"]["temperature_minimum_time"] == "431 AM"
    assert prod.data[0]["data"]["precip_today"] == TRACE_VALUE

    j = prod.get_jabbers("http://localhost")
    ans = (
        "JUNEAU Jun 30 Climate Report: High: 75 "
        "Low: 52 Precip: Trace Snow: Missing "
        "http://localhost?pid=201307010036-PAJK-CDAK47-CLIJNU"
    )
    assert j[0][0] == ans


def test_cli2():
    """CLIDSM test"""
    prod = factory("CLI/CLIDSM.txt")
    assert prod.data[0]["cli_valid"] == datetime.date(2013, 8, 1)
    assert prod.data[0]["data"]["temperature_maximum"] == 89
    assert prod.data[0]["data"]["snow_month"] == 0
    assert prod.data[0]["data"]["snowdepth"] == 0
    assert prod.data[0]["data"]["temperature_minimum_record_years"][0] == 1898
    assert prod.data[0]["data"]["snow_today"] == 0
    assert prod.data[0]["data"]["precip_jun1"] == 4.25
    assert prod.data[0]["data"]["precip_jan1"] == 22.56


def test_cli3():
    """CLINYC test"""
    prod = factory("CLI/CLINYC.txt")
    assert prod.data[0]["data"]["snow_today_record_years"][0] == 1925
    assert prod.data[0]["data"]["snow_today_record"] == 11.5
    assert abs(prod.data[0]["data"]["average_sky_cover"] - 0.0) < 0.01
