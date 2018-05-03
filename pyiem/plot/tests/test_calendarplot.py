"""Can we make calendar plots, yes we can!"""
import datetime

import pytest
from pyiem.plot import calendar_plot


@pytest.mark.mpl_image_compare(tolerance=0)
def test_calendar12():
    """See if we can make a calendar plot!"""
    sts = datetime.date(2015, 5, 4)
    ets = datetime.date(2016, 4, 15)
    data = dict()
    data[datetime.date(2015, 6, 6)] = {'val': "0606"}
    data[datetime.date(2015, 5, 6)] = {'val': "0506"}
    return calendar_plot(sts, ets, data)


@pytest.mark.mpl_image_compare(tolerance=0)
def test_calendar8():
    """See if we can make a calendar plot!"""
    sts = datetime.date(2015, 5, 4)
    ets = datetime.date(2016, 1, 15)
    data = dict()
    data[datetime.date(2015, 6, 6)] = {'val': "0606"}
    data[datetime.date(2015, 5, 6)] = {'val': "0506"}
    return calendar_plot(sts, ets, data)


@pytest.mark.mpl_image_compare(tolerance=0)
def test_calendar4():
    """See if we can make a calendar plot!"""
    sts = datetime.date(2015, 5, 4)
    ets = datetime.date(2015, 8, 15)
    data = dict()
    data[datetime.date(2015, 6, 6)] = {'val': "0606"}
    data[datetime.date(2015, 5, 6)] = {'val': "0506"}
    return calendar_plot(sts, ets, data)


@pytest.mark.mpl_image_compare(tolerance=0)
def test_calendar2():
    """See if we can make a calendar plot!"""
    sts = datetime.date(2015, 5, 4)
    ets = datetime.date(2015, 6, 15)
    data = dict()
    data[datetime.date(2015, 6, 6)] = {'val': "0606"}
    data[datetime.date(2015, 5, 6)] = {'val': "0506"}
    return calendar_plot(sts, ets, data)


@pytest.mark.mpl_image_compare(tolerance=0)
def test_calendar():
    """See if we can make a calendar plot!"""
    sts = datetime.date(2015, 5, 4)
    ets = datetime.date(2015, 5, 15)
    data = dict()
    data[datetime.date(2015, 5, 16)] = {'val': 300}
    data[datetime.date(2015, 5, 6)] = {'val': 1}
    return calendar_plot(sts, ets, data, heatmap=True)
