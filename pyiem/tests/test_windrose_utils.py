import unittest
import datetime
import pytz
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
        v = datetime.datetime(2015, 1, 1, 6)
        v = v.replace(tzinfo=pytz.utc)
        valid = []
        sknt = []
        drct = []
        for s in range(100):
            v += datetime.timedelta(hours=1)
            valid.append(v)
            sknt.append(s)
            drct.append(s)
        fig = windrose('AMW2', sknt=sknt, drct=drct, valid=valid, sname='Ames')
        self.assertTrue(fig is not None)
        fig = windrose('AMW2',
                       sknt=sknt, drct=drct, valid=valid,
                       sts=datetime.datetime(2001, 1, 1),
                       ets=datetime.datetime(2016, 1, 1))
        # fig.savefig('/tmp/test_plot_windrose.png')
        self.assertTrue(fig is not None)

        res = windrose('AMW2',
                       sknt=sknt, drct=drct, valid=valid,
                       sts=datetime.datetime(2015, 1, 1),
                       ets=datetime.datetime(2015, 10, 2), justdata=True)
        assert isinstance(res, str)
