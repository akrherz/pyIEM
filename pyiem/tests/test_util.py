import datetime
import unittest
from collections import OrderedDict
from pyiem import util


class TestUtil(unittest.TestCase):

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
