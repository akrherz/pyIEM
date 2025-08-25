"""tests for windrose_utils."""

import datetime
from io import BytesIO

import pytest
from metpy.units import units
from pandas import read_csv

from pyiem.plot.windrose import PLOT_CONVENTION_TO
from pyiem.util import utc
from pyiem.windrose_utils import windrose

PAIN = 4.1


def faux_data():
    """Generate some data for plotting."""
    basevalid = utc(2014, 12, 30, 6)
    valid = [basevalid]
    sknt = [None]
    drct = [None]
    for s in range(400):
        valid.append(basevalid + datetime.timedelta(days=s, hours=1))
        # Keep the max speed at ~24kts
        sknt.append(s / 13.0)
        drct.append(s)
    return valid, sknt, drct


def test_rwis():
    """Test that RWIS archive data can be fetched."""
    wr = windrose("RAMI4", database="rwis", justdata=True)
    assert wr is not None


def test_database():
    """Test that we can read data from the database."""
    windrose("AMW2", justdata=True, hours=[1, 2])
    wr = windrose("AMW2", hours=[1, 2])
    assert wr


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
        comment="#",
        index_col="Direction",
        delimiter=" *, *",
        engine="python",
    )
    assert df.index.values[0] == "355-004"
    assert len(df.columns) == 4
    assert abs(df.sum(axis=0).sum() - 100.0) < 0.1


def test_windrose_doy_limiter():
    """Test the day of year limiter logic."""
    for sm, em in [(1, 10), (10, 1)]:
        res = windrose(
            "AMW2",
            sts=datetime.datetime(2014, sm, 1),
            ets=datetime.datetime(2016, em, 2),
            justdata=True,
            limit_by_doy=True,
        )
        assert " Oct " in res


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


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_windrose_plot_convention():
    """Test the plotting convention option."""
    valid, sknt, drct = faux_data()
    return windrose(
        "AMW2",
        sknt=sknt,
        drct=drct,
        valid=valid,
        months=[4, 5, 6],
        generated_string="Generated @ Forever",
        plot_convention=PLOT_CONVENTION_TO,
    )


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_windrose_month_limiter():
    """Test that we can filter by month."""
    valid, sknt, drct = faux_data()
    return windrose(
        "AMW2",
        sknt=sknt,
        drct=drct,
        valid=valid,
        months=[4, 5, 6],
        nogenerated=True,
    )


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_windrose_hour_limiter():
    """Test that we can filter by hour."""
    valid, sknt, drct = faux_data()
    return windrose(
        "AMW2",
        sknt=sknt,
        drct=drct,
        valid=valid,
        hours=list(range(6, 16)),
        nogenerated=True,
    )


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_windrose_upperair():
    """Test the magic that happens when level= is set."""
    valid, sknt, drct = faux_data()
    return windrose(
        "_XXX",
        sknt=sknt,
        drct=drct,
        valid=valid,
        level=500,
        nogenerated=True,
        tzname="UTC",
    )


def test_windrose_upperair_text():
    """Test the magic that happens when level= is set."""
    valid, sknt, drct = faux_data()
    return windrose(
        "_XXX",
        sknt=sknt,
        drct=drct,
        valid=valid,
        level=500,
        nogenerated=True,
        justdata=True,
        tzname="UTC",
    )


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_windrose_hads_wind():
    """Test the database filtering with actual database data."""
    # Faked from iem-database repo store_test_data
    return windrose(
        "EOKI4",
        database="hads",
        months=[4, 5, 6],
        sts=utc(2024, 1, 5),
        ets=utc(2024, 9, 5),
        tzname="America/Chicago",
        nogenerated=True,
    )


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_windrose_upperair_nodata():
    """Test what happens with upperair logic and no data found."""
    return windrose(
        "_XXX",
        level=500,
        months=[
            1,
        ],
        nogenerated=True,
    )


def test_windrose_upperair_nodata_text():
    """Test what happens with upperair logic and no data found."""
    res = windrose("_XXX", level=500, justdata=True, hours=list(range(6, 12)))
    assert res


@pytest.mark.mpl_image_compare(tolerance=PAIN)
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

    return windrose(
        "AMW2",
        sknt=sknt,
        drct=drct,
        valid=valid,
        sts=datetime.datetime(2001, 1, 1),
        ets=datetime.datetime(2016, 1, 1),
        nogenerated=True,
    )
