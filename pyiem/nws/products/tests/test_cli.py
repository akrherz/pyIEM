"""Test CLI products"""
from __future__ import print_function
import datetime

from pyiem.reference import TRACE_VALUE
from pyiem.util import utc, get_test_file
from pyiem.nws.products.cli import parser as cliparser


def test_190510_parsefail():
    """This CLIDMH is not happy."""
    prod = cliparser(get_test_file('CLI/CLIDMH.txt'))
    assert prod.data[0]['data']['temperature_maximum'] == 74


def test_180208_issue56_tweetmissing():
    """Report None values as missing, not None"""
    prod = cliparser(get_test_file('CLI/CLIFFC.txt'))
    j = prod.get_jabbers('http://localhost', 'http://localhost')
    ans = (
        'PEACHTREE CITY Oct 3 Climate: Hi: 79 Lo: 67 Precip: 0.87 '
        'Snow: Missing '
        'http://localhost?pid=201410032032-KFFC-CDUS42-CLIFFC'
    )
    assert j[0][2]['twitter'] == ans


def test_170530_none():
    """CLILWD errored in production, so we add a test!"""
    prod = cliparser(get_test_file('CLI/CLILWD.txt'))
    assert prod.data[0]['data']['temperature_maximum'] == 76


def test_170315_invalid_dup():
    """CLIANC incorrectly has two CLIs"""
    prod = cliparser(get_test_file('CLI/CLIANC.txt'))
    answers = [23, 22, 31, 10, 29, 33]
    for i, answer in enumerate(answers):
        assert prod.data[i]['data']['temperature_maximum'] == answer


def test_151019_clibna():
    """CLIBNA is a new diction"""
    prod = cliparser(get_test_file('CLI/CLIBNA.txt'))
    assert prod.data[0]['data']['temperature_maximum'] == 47


def test_150303_alaska():
    """CLIANN Attempt to account for the badly formatted CLIs"""
    prod = cliparser(get_test_file('CLI/CLIANN.txt'))
    assert prod.data[0]['data']['temperature_maximum_time'] == '0151 PM'


def test_150112_climso():
    """ CLIMSO_2 found some issue with this in production? """
    prod = cliparser(get_test_file('CLI/CLIMSO_2.txt'))
    assert prod.data[0]['data']['temperature_minimum'] == 16


def test_141230_newregime4():
    """ CLIMBS has a new regime """
    prod = cliparser(get_test_file('CLI/CLIMBS.txt'))
    assert prod.data[0]['data']['temperature_minimum'] == 18


def test_141230_newregime3():
    """ CLICKV has a new regime """
    prod = cliparser(get_test_file('CLI/CLICKV.txt'))
    assert prod.data[0]['data']['temperature_minimum'] == 33


def test_141230_newregime2():
    """ CLISEW has a new regime """
    prod = cliparser(get_test_file('CLI/CLISEW.txt'))
    assert prod.data[0]['data']['temperature_minimum'] == 34


def test_141230_newregime():
    """ CLITCS has a new regime """
    prod = cliparser(get_test_file('CLI/CLITCS.txt'))
    assert prod.data[0]['data']['temperature_minimum'] == 22


def test_141229_newregime9():
    """ CLIMAI has a new regime """
    prod = cliparser(get_test_file('CLI/CLIMAI.txt'))
    assert prod.data[0]['data']['temperature_minimum'] == 61


def test_141229_newregime8():
    """ CLIECP has a new regime """
    prod = cliparser(get_test_file('CLI/CLIECP.txt'))
    assert prod.data[0]['data']['temperature_minimum'] == 62


def test_141229_newregime7():
    """ CLIBOI has a new regime """
    prod = cliparser(get_test_file('CLI/CLIBOI.txt'))
    assert prod.data[0]['data']['temperature_minimum'] == 23


def test_141229_newregime6():
    """ CLIMSO has a new regime """
    prod = cliparser(get_test_file('CLI/CLIMSO.txt'))
    assert prod.data[0]['data']['temperature_minimum'] == 12


def test_141229_newregime4():
    """ CLIOLF has a new regime """
    prod = cliparser(get_test_file('CLI/CLIOLF.txt'))
    assert prod.data[0]['data']['temperature_average'] == -2


def test_141229_newregime5():
    """ CLIICT has a new regime """
    prod = cliparser(get_test_file('CLI/CLIICT.txt'))
    assert prod.data[0]['data']['precip_today'] == 0.00


def test_141229_newregime3():
    """ CLIDRT has a new regime """
    prod = cliparser(get_test_file('CLI/CLIDRT.txt'))
    assert prod.data[0]['data']['temperature_minimum'] == 37


def test_141229_newregime2():
    """ CLIFMY has a new regime """
    prod = cliparser(get_test_file('CLI/CLIFMY.txt'))
    assert prod.data[0]['data']['temperature_minimum'] == 63


def test_141229_newregime():
    """ CLIEKA has a new regime """
    prod = cliparser(get_test_file('CLI/CLIEKA.txt'))
    assert prod.data[0]['data']['precip_today_record_years'][0] == 1896


def test_141215_convkey():
    """ CLIACT Get a warning about convert key """
    prod = cliparser(get_test_file('CLI/CLIACT.txt'))
    assert prod.data[0]['data']['snow_today_record_years'][0] == 1947
    assert prod.data[0]['data']['snow_today_record_years'][1] == 1925


def test_141201_clihou():
    """ CLIHOU See that we can finally parse the CLIHOU product! """
    prod = cliparser(get_test_file('CLI/CLIHOU.txt'))
    assert prod.data[0]['cli_station'] == 'HOUSTON INTERCONTINENTAL'
    assert prod.data[1]['cli_station'] == 'HOUSTON/HOBBY AIRPORT'


def test_141114_coopaux():
    """ CLIEAR Product had aux COOP data, which confused ingest """
    prod = cliparser(get_test_file('CLI/CLIEAR.txt'))
    assert prod.data[0]['data']['precip_today'] == 0


def test_141103_recordsnow():
    """ CLIBGR Make sure we can deal with record snowfall, again... """
    prod = cliparser(get_test_file('CLI/CLIBGR.txt'))
    assert prod.data[0]['data']['snow_today'] == 12.0


def test_141024_recordsnow():
    """ CLIOME See that we can handle record snowfall """
    prod = cliparser(get_test_file('CLI/CLIOME.txt'))
    assert prod.data[0]['data']['snow_today'] == 3.6


def test_141022_correction():
    """ CLIEWN See what happens if we have a valid product correction """
    prod = cliparser(get_test_file('CLI/CLIEWN.txt'))
    assert prod.data[0]['data']['temperature_maximum'] == 83


def test_141013_missing():
    """ CLIEST See why Esterville was not going to the database! """
    prod = cliparser(get_test_file('CLI/CLIEST.txt'))
    assert prod.data[0]['data']['temperature_maximum'] == 62
    assert prod.data[0]['data']['precip_month'] == 1.22


def test_141013_tracetweet():
    """ CLIDSM2 Make sure we convert trace amounts in tweet to trace! """
    prod = cliparser(get_test_file('CLI/CLIDSM2.txt'))
    j = prod.get_jabbers('http://localhost', 'http://localhost')
    ans = (
        'DES MOINES IA Oct 12 Climate: Hi: 56 '
        'Lo: 43 Precip: Trace Snow: 0.0'
        ' http://localhost?pid=201410122226-KDMX-CDUS43-CLIDSM'
    )
    assert j[0][2]['twitter'] == ans


def test_141003_missing():
    """ CLIFFC We are missing some data! """
    prod = cliparser(get_test_file("CLI/CLIFFC.txt"))
    assert prod.data[0]['data']['temperature_maximum_normal'] == 78


def test_141003_alaska():
    """ CLIBET Some alaska data was not getting processed"""
    prod = cliparser(get_test_file("CLI/CLIBET.txt"))
    assert prod.data[0]['data']['temperature_maximum'] == 17
    assert prod.data[0]['data']['snow_jul1'] == 14.4


def test_140930_negative_temps():
    """ CLIALO Royal screwup not supporting negative numbers """
    prod = cliparser(get_test_file('CLI/CLIALO.txt'))
    assert prod.data[0]['data'].get('temperature_minimum') == -21
    assert prod.data[0]['data'].get('temperature_minimum_record') == -21
    assert prod.data[0]['data'].get('snow_today') == 0.0
    assert prod.data[0]['data'].get('snow_today_record') == 13.2
    assert prod.data[0]['data'].get('snow_today_last') == 0.0
    assert prod.data[0]['data'].get('snow_month_last') == TRACE_VALUE
    assert prod.data[0]['data'].get('snow_jul1_last') == 11.3


def test_140930_mm_precip():
    """ CLIABY Make sure having MM as today's precip does not error out """
    prod = cliparser(get_test_file('CLI/CLIABY.txt'))
    assert prod.data[0]['data'].get('precip_today') is None


def test_cli():
    """ CLIJUN Test the processing of a CLI product """
    prod = cliparser(get_test_file('CLI/CLIJNU.txt'))
    assert prod.data[0]['cli_valid'] == datetime.datetime(2013, 6, 30)
    assert prod.valid == utc(2013, 7, 1, 0, 36)
    assert prod.data[0]['data']['temperature_maximum'] == 75
    assert prod.data[0]['data']['temperature_maximum_time'] == "259 PM"
    assert prod.data[0]['data']['temperature_minimum_time'] == "431 AM"
    assert prod.data[0]['data']['precip_today'] == TRACE_VALUE

    j = prod.get_jabbers("http://localhost")
    ans = (
        'JUNEAU Jun 30 Climate Report: High: 75 '
        'Low: 52 Precip: Trace Snow: M '
        'http://localhost?pid=201307010036-PAJK-CDAK47-CLIJNU'
    )
    assert j[0][0] == ans


def test_cli2():
    """ CLIDSM test """
    prod = cliparser(get_test_file('CLI/CLIDSM.txt'))
    assert prod.data[0]['cli_valid'] == datetime.datetime(2013, 8, 1)
    assert prod.data[0]['data']['temperature_maximum'] == 89
    assert prod.data[0]['data']['snow_month'] == 0
    assert prod.data[0]['data']['temperature_minimum_record_years'][0] == 1898
    assert prod.data[0]['data']['snow_today'] == 0
    assert prod.data[0]['data']['precip_jun1'] == 4.25
    assert prod.data[0]['data']['precip_jan1'] == 22.56


def test_cli3():
    """ CLINYC test """
    prod = cliparser(get_test_file('CLI/CLINYC.txt'))
    assert prod.data[0]['data']['snow_today_record_years'][0] == 1925
    assert prod.data[0]['data']['snow_today_record'] == 11.5
