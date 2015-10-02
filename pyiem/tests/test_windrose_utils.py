import unittest
import datetime
import psycopg2
from pyiem.windrose_utils import windrose, _get_timeinfo


class Test(unittest.TestCase):

    def test_timeinfo(self):
        """Exercise the _get_timeinfo method"""
        res = _get_timeinfo(range(1, 10), 'hour', 24)
        self.assertEquals(res['labeltext'], '(1, 2, 3, 4, 5, 6, 7, 8, 9)')
        res = _get_timeinfo([1], 'month', 1)
        self.assertEquals(res['sqltext'],
                          ' and extract(month from valid) = 1 ')

    def test_windrose(self):
        """Exercise the windrose code"""
        pgconn = psycopg2.connect(database='asos', host="iemdb")
        cursor = pgconn.cursor()
        v = datetime.datetime(2015, 1, 1, 6)
        for s in range(100):
            v += datetime.timedelta(hours=1)
            cursor.execute("""INSERT into t2015(station, valid, sknt, drct)
            VALUES (%s, %s, %s, %s)""", ('AMW2', v, s, s))
        # plot.windrose('AMW2', fp='/tmp/test_plot_windrose.png',
        #              cursor=cursor)
        fig = windrose('AMW2',
                       cursor=cursor, justdata=True)
        self.assertTrue(fig is not None)
        fig = windrose('AMW2',
                       cursor=cursor, sts=datetime.datetime(2001, 1, 1),
                       ets=datetime.datetime(2001, 1, 2))
        self.assertTrue(fig is not None)

        res = windrose('AMW2',
                       cursor=cursor, sts=datetime.datetime(2015, 1, 1),
                       ets=datetime.datetime(2015, 10, 2), justdata=True)
        assert isinstance(res, str)
