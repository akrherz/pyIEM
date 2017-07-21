"""Testing of util"""
import datetime
import unittest
import os
from collections import OrderedDict

from pyiem import util
import numpy as np


def get_file(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    fn = "%s/../../data/product_examples/%s" % (basedir, name)
    return open(fn).read()


class TestUtil(unittest.TestCase):

    def test_grid_bounds(self):
        """Can we compute grid bounds correctly"""
        lons = np.arange(-100, -80, 0.1)
        lats = np.arange(29, 51, 0.2)
        (x0, y0, x1, y1) = util.grid_bounds(lons, lats, [-96, 32, -89, 40])
        self.assertEquals(x0, 41)
        self.assertEquals(x1, 111)
        self.assertEquals(y0, 16)
        self.assertEquals(y1, 56)
        (lons, lats) = np.meshgrid(lons, lats)
        (x0, y0, x1, y1) = util.grid_bounds(lons, lats, [-96, 32, -89, 40])
        self.assertEquals(x0, 40)
        self.assertEquals(x1, 110)
        self.assertEquals(y0, 15)
        self.assertEquals(y1, 55)

    def test_noaaport_text(self):
        """See that we do what we expect with noaaport text processing"""
        data = get_file('WCN.txt')
        res = util.noaaport_text(data)
        self.assertEquals(res[:11], "\001\r\r\n098 \r\r\n")

    def test_vtecps(self):
        """Can we properly handle the vtecps form type"""
        cfg = dict(arguments=[
            dict(type='vtec_ps', name='v1', default='UNUSED',
                 label='VTEC Phenomena and Significance 1'),
            dict(type='vtec_ps', name='v2', default='UNUSED', optional=True,
                 label='VTEC Phenomena and Significance 2'),
            dict(type='vtec_ps', name='v3', default='UNUSED', optional=True,
                 label='VTEC Phenomena and Significance 3'),
            dict(type='vtec_ps', name='v4', default='UNUSED', optional=True,
                 label='VTEC Phenomena and Significance 4')])
        form = dict(phenomenav1='SV', significancev1='A',
                    phenomenav4='TO', significancev4='W')
        ctx = util.get_autoplot_context(form, cfg)
        self.assertEqual(ctx['phenomenav1'], 'SV')
        self.assertTrue(ctx['phenomenav2'] is None)
        self.assertEqual(ctx['significancev4'], 'W')

    def test_get_autoplot_context(self):
        """See that we can do things"""
        form = dict(station='AMW', network='IA_ASOS', type2='bogus',
                    t=15)
        form['type'] = 'max-low'
        PDICT = OrderedDict([
                             ('max-high', 'Maximum High'),
                             ('avg-high', 'Average High'),
                             ('min-high', 'Minimum High'),
                             ('max-low', 'Maximum Low')])
        cfg = dict(arguments=[
            dict(type='station', name='station', default='IA0000'),
            dict(type='select', name='type', default='max-high',
                 options=PDICT),
            dict(type='select', name='type2', default='max-high',
                 options=PDICT),
            dict(type='int', name='threshold', default=-99),
            dict(type='int', name='t', default=9, min=0, max=10),
            dict(type='date', name='d', default='2011/11/12'),
            dict(type='year', name='year', default='2011', optional=True),
            dict(type='float', name='f', default=1.10)])
        ctx = util.get_autoplot_context(form, cfg)
        self.assertEqual(ctx['station'], 'AMW')
        self.assertEqual(ctx['network'], 'IA_ASOS')
        self.assertTrue(isinstance(ctx['threshold'], int))
        self.assertEqual(ctx['type'], 'max-low')
        self.assertEqual(ctx['type2'], 'max-high')
        self.assertTrue(isinstance(ctx['f'], float))
        self.assertEqual(ctx['t'], 9)
        self.assertEqual(ctx['d'], datetime.date(2011, 11, 12))
        self.assertTrue('year' not in ctx)

        form = dict(zstation='DSM')
        cfg = dict(arguments=[
            dict(type='zstation', name='station', default='DSM',
                 network='IA_ASOS')])
        ctx = util.get_autoplot_context(form, cfg)
        self.assertEquals(ctx['network'], 'IA_ASOS')

    def test_properties(self):
        """ Try the properties function"""
        prop = util.get_properties()
        self.assertTrue(isinstance(prop, dict))

    def test_drct2text(self):
        """ Test conversion of drct2text """
        self.assertEquals(util.drct2text(360), "N")
        self.assertEquals(util.drct2text(90), "E")
        # A hack to get move coverage
        for i in range(360):
            util.drct2text(i)
