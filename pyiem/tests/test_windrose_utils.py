"""tests for windrose_utils."""
import datetime

import pytest
from pyiem.windrose_utils import windrose, _get_timeinfo
from pyiem.util import utc


def test_timeinfo():
    """Exercise the _get_timeinfo method"""
    res = _get_timeinfo(range(1, 10), 'hour', 24)
    assert res['labeltext'] == '(1, 2, 3, 4, 5, 6, 7, 8, 9)'
    res = _get_timeinfo([1], 'month', 1)
    assert res['sqltext'] == ' and extract(month from valid) = 1 '


@pytest.mark.mpl_image_compare(tolerance=0.1)
def test_windrose():
    """Exercise the windrose code"""
    basevalid = utc(2015, 1, 1, 6)
    valid = [basevalid]
    sknt = [None]
    drct = [None]
    for s in range(360):
        basevalid += datetime.timedelta(hours=1)
        valid.append(basevalid)
        # Keep the max speed at ~24kts
        sknt.append(s / 13.)
        drct.append(s)
    fig = windrose('AMW2', sknt=sknt, drct=drct, valid=valid, sname='Ames')
    assert fig is not None

    res = windrose(
        'AMW2', sknt=sknt, drct=drct, valid=valid,
        sts=datetime.datetime(2015, 1, 1),
        ets=datetime.datetime(2015, 10, 2), justdata=True)
    assert isinstance(res, str)

    # allow _get_data to be excercised
    res = windrose('XXXXX')
    assert res is not None

    fig = windrose(
        'AMW2', sknt=sknt, drct=drct, valid=valid,
        sts=datetime.datetime(2001, 1, 1),
        ets=datetime.datetime(2016, 1, 1), nogenerated=True)
    return fig
