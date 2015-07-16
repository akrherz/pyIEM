import unittest
from pyiem.nws import gini
import os


def get_filepath(name):
    ''' Helper function to get the text file contents '''
    basedir = os.path.dirname(__file__)
    return "%s/../../../data/product_examples/%s" % (basedir, name)


class TestGINI(unittest.TestCase):

    def test_gini(self):
        """ check GINI Processing of Goes East VIS parsing """
        fn = get_filepath("TIGH05")
        sat = gini.GINIZFile(open(fn))
        self.assertEqual(sat.archive_filename(), "GOES_HI_WV_201507161745.png")
        self.assertEqual(str(sat),
                         "TIGH05 KNES 161745 Line Size: 560 Num Lines: 520")
        self.assertEqual(sat.awips_grid(), 208)