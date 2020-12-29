"""tests for windrose_utils."""
import datetime
from io import BytesIO

import pytest
from pandas import read_csv
from metpy.units import units
from pyiem.windrose_utils import windrose, _get_timeinfo
from pyiem.util import utc


def faux_data():
    """Generate some data for plotting."""
    basevalid = utc(2015, 1, 1, 6)
    valid = [basevalid]
    sknt = [None]
    drct = [None]
    for s in range(360):
        valid.append(basevalid + datetime.timedelta(days=s, hours=1))
        # Keep the max speed at ~24kts
        sknt.append(s / 13.0)
        drct.append(s)
    return valid, sknt, drct


def test_database():
    """Test that we can read data from the database."""
    wr = windrose("AMW2", justdata=True, hours=[1, 2])
    assert wr
    wr = windrose("AMW2", hours=[1, 2])


def test_timeinfo():
    """Exercise the _get_timeinfo method"""
    res = _get_timeinfo(range(1, 10), "hour", 24, None)
    assert res["labeltext"] == "(1, 2, 3, 4, 5, 6, 7, 8, 9)"
    res = _get_timeinfo([1], "month", 1, None)
    assert res["sqltext"] == " and extract(month from valid) = 1 "


def test_windrose_without_units():
    """Ensure that we can deal with provided bins."""
    valid, sknt, drct = faux_data()
    res = windrose(
        "AMW2",
        sknt=sknt,
        drct=drct,
        valid=valid,
        months=[4, 5, 6],
        bins=[10, 20, 40],
        justdata=True,
    )
    # python2-3 hackery here
    sio = BytesIO()
    sio.write(res.encode("ascii"))
    sio.seek(0)
    df = read_csv(
        sio,
        skiprows=range(0, 8),
        index_col="Direction",
        delimiter=" *, *",
        engine="python",
    )
    assert df.index.values[0] == "355-004"
    assert len(df.columns) == 4
    assert abs(df.sum(axis=0).sum() - 100.0) < 0.1


def test_windrose_with_units():
    """Ensure that we can deal with provided bins."""
    valid, sknt, drct = faux_data()
    res = windrose(
        "AMW2",
        sknt=sknt,
        drct=drct,
        valid=valid,
        months=[4, 5, 6],
        bins=[0.0001, 20, 40] * units("mph"),
        justdata=True,
    )
    assert res


@pytest.mark.mpl_image_compare(tolerance=0.1)
def test_windrose_month_limiter():
    """Test that we can filter by month."""
    valid, sknt, drct = faux_data()
    fig = windrose(
        "AMW2",
        sknt=sknt,
        drct=drct,
        valid=valid,
        months=[4, 5, 6],
        nogenerated=True,
    )
    return fig


@pytest.mark.mpl_image_compare(tolerance=0.1)
def test_windrose_hour_limiter():
    """Test that we can filter by hour."""
    valid, sknt, drct = faux_data()
    fig = windrose(
        "AMW2",
        sknt=sknt,
        drct=drct,
        valid=valid,
        hours=list(range(6, 16)),
        nogenerated=True,
    )
    return fig


# Troubles here with python2.7 that I punted on.
@pytest.mark.mpl_image_compare(tolerance=20.0)
def test_windrose_upperair():
    """Test the magic that happens when level= is set."""
    valid, sknt, drct = faux_data()
    fig = windrose(
        "_XXX",
        sknt=sknt,
        drct=drct,
        valid=valid,
        level=500,
        nogenerated=True,
        tzname="UTC",
    )
    return fig


def test_windrose_upperair_text():
    """Test the magic that happens when level= is set."""
    valid, sknt, drct = faux_data()
    res = windrose(
        "_XXX",
        sknt=sknt,
        drct=drct,
        valid=valid,
        level=500,
        nogenerated=True,
        justdata=True,
        tzname="UTC",
    )
    assert res


@pytest.mark.mpl_image_compare(tolerance=0.1)
def test_windrose_upperair_nodata():
    """Test what happens with upperair logic and no data found."""
    fig = windrose("_XXX", level=500)
    return fig


def test_windrose_upperair_nodata_text():
    """Test what happens with upperair logic and no data found."""
    res = windrose("_XXX", level=500, justdata=True, hours=list(range(6, 12)))
    assert res


@pytest.mark.mpl_image_compare(tolerance=0.1)
def test_windrose():
    """Exercise the windrose code"""
    valid, sknt, drct = faux_data()
    fig = windrose("AMW2", sknt=sknt, drct=drct, valid=valid, sname="Ames")
    assert fig is not None

    res = windrose(
        "AMW2",
        sknt=sknt,
        drct=drct,
        valid=valid,
        sts=datetime.datetime(2015, 1, 1),
        ets=datetime.datetime(2015, 10, 2),
        justdata=True,
    )
    assert isinstance(res, str)

    # allow _get_data to be excercised
    res = windrose("XXXXX")
    assert res is not None

    fig = windrose(
        "AMW2",
        sknt=sknt,
        drct=drct,
        valid=valid,
        sts=datetime.datetime(2001, 1, 1),
        ets=datetime.datetime(2016, 1, 1),
        nogenerated=True,
    )
    return fig
