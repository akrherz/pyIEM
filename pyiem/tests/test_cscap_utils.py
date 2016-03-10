from pyiem.cscap_utils import (translate_years, get_config, save_config,
                               cleanvalue)
import unittest
import tempfile
import os


class Test(unittest.TestCase):

    def test_cleanvalue(self):
        """ see what we can do with cleaning strings"""
        self.assertAlmostEquals(10.54, cleanvalue("10.54%"), 2)
        self.assertEquals(cleanvalue('Did NOt Collect'), 'did not collect')
        self.assertEquals(cleanvalue('<0.2'), '< 0.2')
        self.assertTrue(cleanvalue(' ') is None)

    def test_config(self):
        """Make sure we exercise the config logic as things get hairy"""
        (_, tmpfn) = tempfile.mkstemp()
        # create bogus config file
        cfg = dict(a='a', b='b')
        # Write config to bogus file
        save_config(cfg, tmpfn)
        # Attempt to load it back now
        cfg = get_config(tmpfn)
        self.assertTrue(cfg is not None)
        os.unlink(tmpfn)

    def test_translateyears(self):
        """See that we can translate years properly"""
        x = translate_years("X ('07-'17)")
        self.assertEquals(x[0], 2007)
        x = translate_years("X ('98-'06)")
        self.assertEquals(x[0], 1998)
        self.assertEquals(x[-1], 2006)
        x = translate_years("X ('14, '15, '16, '17)")
        self.assertEquals(x[0], 2014)
        self.assertEquals(x[-1], 2017)
        x = translate_years("X ('06)")
        self.assertEquals(x[0], 2006)
