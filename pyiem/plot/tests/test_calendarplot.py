"""Can we make calendar plots, yes we can!"""
import unittest
import datetime

from pyiem.plot import calendar_plot


class CalendarPlotTests(unittest.TestCase):
    """Do Some Tests"""

    def test_calendar12(self):
        """See if we can make a calendar plot!"""
        import matplotlib.pyplot as plt
        sts = datetime.date(2015, 5, 4)
        ets = datetime.date(2016, 4, 15)
        data = dict()
        data[datetime.date(2015, 6, 6)] = {'val': "0606"}
        data[datetime.date(2015, 5, 6)] = {'val': "0506"}
        fig = calendar_plot(sts, ets, data)
        self.assertTrue(isinstance(fig, plt.Figure))
        fig.savefig('/tmp/test_calendar12.png')

    def test_calendar8(self):
        """See if we can make a calendar plot!"""
        import matplotlib.pyplot as plt
        sts = datetime.date(2015, 5, 4)
        ets = datetime.date(2016, 1, 15)
        data = dict()
        data[datetime.date(2015, 6, 6)] = {'val': "0606"}
        data[datetime.date(2015, 5, 6)] = {'val': "0506"}
        fig = calendar_plot(sts, ets, data)
        self.assertTrue(isinstance(fig, plt.Figure))
        fig.savefig('/tmp/test_calendar8.png')

    def test_calendar4(self):
        """See if we can make a calendar plot!"""
        import matplotlib.pyplot as plt
        sts = datetime.date(2015, 5, 4)
        ets = datetime.date(2015, 8, 15)
        data = dict()
        data[datetime.date(2015, 6, 6)] = {'val': "0606"}
        data[datetime.date(2015, 5, 6)] = {'val': "0506"}
        fig = calendar_plot(sts, ets, data)
        self.assertTrue(isinstance(fig, plt.Figure))
        fig.savefig('/tmp/test_calendar4.png')

    def test_calendar2(self):
        """See if we can make a calendar plot!"""
        import matplotlib.pyplot as plt
        sts = datetime.date(2015, 5, 4)
        ets = datetime.date(2015, 6, 15)
        data = dict()
        data[datetime.date(2015, 6, 6)] = {'val': "0606"}
        data[datetime.date(2015, 5, 6)] = {'val': "0506"}
        fig = calendar_plot(sts, ets, data)
        self.assertTrue(isinstance(fig, plt.Figure))
        fig.savefig('/tmp/test_calendar2.png')

    def test_calendar(self):
        """See if we can make a calendar plot!"""
        import matplotlib.pyplot as plt
        sts = datetime.date(2015, 5, 4)
        ets = datetime.date(2015, 5, 15)
        data = dict()
        data[datetime.date(2015, 5, 16)] = {'val': 300}
        data[datetime.date(2015, 5, 6)] = {'val': 1}
        fig = calendar_plot(sts, ets, data, heatmap=True)
        self.assertTrue(isinstance(fig, plt.Figure))
        fig.savefig('/tmp/test_calendar.png')
