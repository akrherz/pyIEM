"""Test DEP"""
from __future__ import print_function
import unittest
import os
import datetime

from pyiem import dep


def get_path(name):
    """helper"""
    basedir = os.path.dirname(__file__)
    return "%s/../../data/wepp/%s" % (basedir, name)


class Tests(unittest.TestCase):
    """We need tests!"""

    def test_yld(self):
        """Read a slope file"""
        df = dep.read_yld(get_path('yld.txt'))
        self.assertEquals(len(df.index), 10)
        self.assertAlmostEquals(df['yield_kgm2'].max(), 0.93, 2)

    def test_slp(self):
        """Read a slope file"""
        slp = dep.read_slp(get_path('slp.txt'))
        self.assertEquals(len(slp), 5)
        self.assertAlmostEquals(slp[4]['y'][-1], -8.3, 1)

    def test_man(self):
        """Read a management file please"""
        manfile = dep.read_man(get_path('man.txt'))
        self.assertEquals(manfile['nop'], 5)
        self.assertEquals(manfile['nini'], 2)
        self.assertEquals(manfile['nsurf'], 2)
        self.assertEquals(manfile['nwsofe'], 3)
        self.assertEquals(manfile['nrots'], 1)
        self.assertEquals(manfile['nyears'], 11)

        manfile = dep.read_man(get_path('man2.txt'))
        self.assertEquals(manfile['nop'], 0)

    def test_ofe(self):
        """Read an OFE please"""
        df = dep.read_ofe(get_path('ofe.txt'))
        self.assertAlmostEquals(df['precip'].max(), 107.56, 2)

        df = dep.read_ofe(get_path('ofe2.txt'))
        print(df['sedleave'].sum())
        self.assertAlmostEquals(df['sedleave'].sum(), 400257.48, 2)

    def test_wb(self):
        """read a WB file please"""
        df = dep.read_wb(get_path('wb.txt'))
        self.assertAlmostEquals(df['precip'].max(), 162.04, 2)

    def test_cli(self):
        """read a CLI file please"""
        df = dep.read_cli(get_path('cli.txt'))
        self.assertEquals(len(df.index), 4018)

    def test_empty(self):
        """don't error out on an empty ENV"""
        df = dep.read_env(get_path('empty_env.txt'))
        self.assertEquals(len(df.index), 0)

    def test_read(self):
        """Read a ENV file"""
        df = dep.read_env(get_path('good_env.txt'))
        df2 = df[df['date'] == datetime.date(2010, 6, 5)]
        self.assertEqual(len(df2.index), 1)
        row = df2.iloc[0]
        self.assertEquals(row['runoff'], 86.3)

    def do_timing(self):
        """Hack to do timing"""
        sts = datetime.datetime.now()
        _ = dep.read_env(get_path('good_env.txt'))
        ets = datetime.datetime.now()
        print("%.5f reads per second" % (1. / (ets - sts).total_seconds(),))
        self.assertEquals(1, 2)
