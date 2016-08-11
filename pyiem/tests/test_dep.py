from pyiem import dep
import unittest
import os
import datetime


def get_path(name):
    basedir = os.path.dirname(__file__)
    return "%s/../../data/wepp/%s" % (basedir, name)


class Tests(unittest.TestCase):

    def test_empty(self):
        df = dep.read_env(get_path('empty_env.txt'))
        self.assertEquals(len(df.index), 0)

    def test_read(self):
        df = dep.read_env(get_path('good_env.txt'))
        df2 = df[df['date'] == datetime.date(2010, 6, 5)]
        self.assertEqual(len(df2.index), 1)
        row = df2.iloc[0]
        self.assertEquals(row['runoff'], 86.3)
