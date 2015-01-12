import os
import datetime
import pytz
import unittest
from pyiem.nws.products.cli import parser as cliparser

def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../../../data/product_examples/%s" % (basedir, name)
    return open(fn).read()



class TestProducts(unittest.TestCase):
    """ Tests """
    def test_150112_climso(self):
        """ CLIMSO_2 found some issue with this in production? """
        prod = cliparser(get_file('CLIMSO_2.txt'))
        self.assertEqual(prod.data[0]['data']['temperature_minimum'],
                        16)

    def test_141230_newregime4(self):
        """ CLIMBS has a new regime """
        prod = cliparser(get_file('CLIMBS.txt'))
        self.assertEqual(prod.data[0]['data']['temperature_minimum'],
                        18)

    def test_141230_newregime3(self):
        """ CLICKV has a new regime """
        prod = cliparser(get_file('CLICKV.txt'))
        self.assertEqual(prod.data[0]['data']['temperature_minimum'],
                        33)
    
    def test_141230_newregime2(self):
        """ CLISEW has a new regime """
        prod = cliparser(get_file('CLISEW.txt'))
        self.assertEqual(prod.data[0]['data']['temperature_minimum'],
                        34)

    def test_141230_newregime(self):
        """ CLITCS has a new regime """
        prod = cliparser(get_file('CLITCS.txt'))
        self.assertEqual(prod.data[0]['data']['temperature_minimum'],
                        22)

    def test_141229_newregime9(self):
        """ CLIMAI has a new regime """
        prod = cliparser(get_file('CLIMAI.txt'))
        self.assertEqual(prod.data[0]['data']['temperature_minimum'],
                        61)

    def test_141229_newregime8(self):
        """ CLIECP has a new regime """
        prod = cliparser(get_file('CLIECP.txt'))
        self.assertEqual(prod.data[0]['data']['temperature_minimum'],
                        62)

    def test_141229_newregime7(self):
        """ CLIBOI has a new regime """
        prod = cliparser(get_file('CLIBOI.txt'))
        self.assertEqual(prod.data[0]['data']['temperature_minimum'],
                         23)

    def test_141229_newregime6(self):
        """ CLIMSO has a new regime """
        prod = cliparser(get_file('CLIMSO.txt'))
        self.assertEqual(prod.data[0]['data']['temperature_minimum'],
                         12)

    def test_141229_newregime4(self):
        """ CLIOLF has a new regime """
        prod = cliparser(get_file('CLIOLF.txt'))
        self.assertEqual(prod.data[0]['data']['temperature_average'],
                         -2)

    def test_141229_newregime5(self):
        """ CLIICT has a new regime """
        prod = cliparser(get_file('CLIICT.txt'))
        self.assertEqual(prod.data[0]['data']['precip_today'],
                         0.00)

    def test_141229_newregime3(self):
        """ CLIDRT has a new regime """
        prod = cliparser(get_file('CLIDRT.txt'))
        self.assertEqual(prod.data[0]['data']['temperature_minimum'],
                         37)

    def test_141229_newregime2(self):
        """ CLIFMY has a new regime """
        prod = cliparser(get_file('CLIFMY.txt'))
        self.assertEqual(prod.data[0]['data']['temperature_minimum'],
                         63)

    def test_141229_newregime(self):
        """ CLIEKA has a new regime """
        prod = cliparser(get_file('CLIEKA.txt'))
        self.assertEqual(prod.data[0]['data']['precip_today_record_years'][0],
                         1896)

    def test_141215_convkey(self):
        """ CLIACT Get a warning about convert key """
        prod = cliparser(get_file('CLIACT.txt'))
        self.assertEqual(prod.data[0]['data']['snow_today_record_years'][0],
                         1947)
        self.assertEqual(prod.data[0]['data']['snow_today_record_years'][1],
                         1925)

    def test_141201_clihou(self):
        """ CLIHOU See that we can finally parse the CLIHOU product! """
        prod = cliparser(get_file('CLIHOU.txt'))
        self.assertEqual(prod.data[0]['cli_station'], 'HOUSTON INTERCONTINENTAL')
        self.assertEqual(prod.data[1]['cli_station'], 'HOUSTON/HOBBY AIRPORT')

    def test_141114_coopaux(self):
        """ CLIEAR Product had aux COOP data, which confused ingest """
        prod = cliparser(get_file('CLIEAR.txt'))
        self.assertEqual(prod.data[0]['data']['precip_today'], 0)

    def test_141103_recordsnow(self):
        """ CLIBGR Make sure we can deal with record snowfall, again... """
        prod = cliparser(get_file('CLIBGR.txt'))
        self.assertEqual(prod.data[0]['data']['snow_today'], 12.0)

    def test_141024_recordsnow(self):
        """ CLIOME See that we can handle record snowfall """
        prod = cliparser(get_file('CLIOME.txt'))
        self.assertEqual(prod.data[0]['data']['snow_today'], 3.6)

    def test_141022_correction(self):
        """ CLIEWN See what happens if we have a valid(?) product correction """
        prod = cliparser(get_file('CLIEWN.txt'))
        self.assertEqual(prod.data[0]['data']['temperature_maximum'], 83)

    def test_141013_missing(self):
        """ CLIEST See why Esterville was not going to the database! """
        prod = cliparser(get_file('CLIEST.txt'))
        self.assertEqual(prod.data[0]['data']['temperature_maximum'], 62)
        self.assertEqual(prod.data[0]['data']['precip_month'], 1.22)

    def test_141013_tracetweet(self):
        """ CLIDSM2 Make sure we convert trace amounts in tweet to trace! """
        prod = cliparser(get_file('CLIDSM2.txt'))
        j = prod.get_jabbers('http://localhost', 'http://localhost')
        self.assertEquals(j[0][2]['twitter'], 
                          ('DES MOINES IA Oct 12 Climate: Hi: 56 '
                                    +'Lo: 43 Precip: Trace Snow: 0.0'
                    +' http://localhost?pid=201410122226-KDMX-CDUS43-CLIDSM'))

    def test_141003_missing(self):
        """ CLIFFC We are missing some data! """
        prod = cliparser(get_file("CLIFFC.txt"))
        self.assertEqual(prod.data[0]['data']['temperature_maximum_normal'], 78)
    
    def test_141003_alaska(self):
        """ CLIBET Some alaska data was not getting processed"""
        prod = cliparser(get_file("CLIBET.txt"))
        self.assertEqual(prod.data[0]['data']['temperature_maximum'], 17)
        self.assertEqual(prod.data[0]['data']['snow_jul1'], 14.4)
    
    def test_140930_negative_temps(self):
        """ CLIALO Royal screwup not supporting negative numbers """
        prod = cliparser(get_file('CLIALO.txt'))
        self.assertEqual(prod.data[0]['data'].get('temperature_minimum'), -21)
        self.assertEqual(prod.data[0]['data'].get('temperature_minimum_record'), -21)
        self.assertEqual(prod.data[0]['data'].get('snow_today'), 0.0)
        self.assertEqual(prod.data[0]['data'].get('snow_today_record'), 13.2)
        self.assertEqual(prod.data[0]['data'].get('snow_today_last'), 0.0)
        self.assertEqual(prod.data[0]['data'].get('snow_month_last'), 0.0001)
        self.assertEqual(prod.data[0]['data'].get('snow_jul1_last'), 11.3)
    
    def test_140930_mm_precip(self):
        """ CLIABY Make sure having MM as today's precip does not error out """
        prod = cliparser(get_file('CLIABY.txt'))
        self.assertTrue(prod.data[0]['data'].get('precip_today') is None)
    
    def test_cli(self):
        """ CLIJUN Test the processing of a CLI product """
        prod = cliparser(get_file('CLIJNU.txt'))
        self.assertEqual(prod.data[0]['cli_valid'], datetime.datetime(2013,6,30))
        self.assertEqual(prod.valid, datetime.datetime(2013,7,1,0,36).replace(
                                    tzinfo=pytz.timezone("UTC")))
        self.assertEqual(prod.data[0]['data']['temperature_maximum'], 75)
        self.assertEqual(prod.data[0]['data']['temperature_maximum_time'], "259 PM")
        self.assertEqual(prod.data[0]['data']['temperature_minimum_time'], "431 AM")
        self.assertEqual(prod.data[0]['data']['precip_today'], 0.0001)
        
        j = prod.get_jabbers("http://localhost")
        self.assertEqual(j[0][0], ('JUNEAU Jun 30 Climate Report: High: 75 '
                                   +'Low: 52 Precip: Trace Snow: M '
                    +'http://localhost?pid=201307010036-PAJK-CDAK47-CLIJNU'))
        
    def test_cli2(self):
        """ CLIDSM test """
        prod = cliparser(get_file('CLIDSM.txt'))
        self.assertEqual(prod.data[0]['cli_valid'], datetime.datetime(2013,8,1))
        self.assertEqual(prod.data[0]['data']['temperature_maximum'], 89)
        self.assertEqual(prod.data[0]['data']['snow_month'], 0)
        self.assertEqual(prod.data[0]['data']['temperature_minimum_record_years'][0], 
                         1898)
        self.assertEqual(prod.data[0]['data']['snow_today'], 0)
        self.assertEqual(prod.data[0]['data']['precip_jun1'], 4.25)
        self.assertEqual(prod.data[0]['data']['precip_jan1'], 22.56)
        
    def test_cli3(self):
        """ CLINYC test """
        prod = cliparser(get_file('CLINYC.txt'))
        self.assertEqual(prod.data[0]['data']['snow_today_record_years'][0], 1925)
        self.assertEqual(prod.data[0]['data']['snow_today_record'], 11.5)
