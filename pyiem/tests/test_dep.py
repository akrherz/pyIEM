from pyiem import dep
import unittest
import os
import datetime


def get_path(name):
    basedir = os.path.dirname(__file__)
    return "%s/../../data/wepp/%s" % (basedir, name)


class Tests(unittest.TestCase):

    def test_wb(self):
        df = dep.read_wb(get_path('wb.txt'))
        self.assertAlmostEquals(df['precip'].max(), 162.04, 2)

    def test_cli(self):
        df = dep.read_cli(get_path('cli.txt'))
        self.assertEquals(len(df.index), 4018)

    def test_empty(self):
        df = dep.read_env(get_path('empty_env.txt'))
        self.assertEquals(len(df.index), 0)

    def test_read(self):
        df = dep.read_env(get_path('good_env.txt'))
        df2 = df[df['date'] == datetime.date(2010, 6, 5)]
        self.assertEqual(len(df2.index), 1)
        row = df2.iloc[0]
        self.assertEquals(row['runoff'], 86.3)

    def do_timing(self):
        sts = datetime.datetime.now()
        _ = dep.read_env(get_path('good_env.txt'))
        ets = datetime.datetime.now()
        print("%.5f reads per second" % (1. / (ets - sts).total_seconds(),))
        self.assertEquals(1, 2)
