"""Can we make calendar plots, yes we can!"""
import datetime

import pytest
from pyiem.plot import calendar_plot

PAIN = 0.02  # how much do we care, sigh.


@pytest.mark.mpl_image_compare(tolerance=0.01, savefig_kwargs={"dpi": 60})
def test_issue101():
    """We like June, it is a good month, don't drop it."""
    sts = datetime.date(2017, 5, 29)
    ets = datetime.date(2017, 9, 30)
    data = {}
    data[datetime.date(2017, 6, 6)] = {"val": "0606"}
    data[datetime.date(2017, 7, 6)] = {"val": "0506"}
    return calendar_plot(
        sts,
        ets,
        data,
        title="Whiz Bang, Wizzardry",
        subtitle="This is officially unofficial and hacky.",
        apctx={"dpi": 60},
    )


@pytest.mark.mpl_image_compare(tolerance=PAIN)
def test_calendar12():
    """See if we can make a calendar plot!"""
    sts = datetime.date(2015, 5, 4)
    ets = datetime.date(2016, 4, 15)
    data = {}
    data[datetime.date(2015, 6, 6)] = {"val": "0606"}
    data[datetime.date(2015, 5, 6)] = {"val": "0506"}
    return calendar_plot(
        sts,
        ets,
        data,
        title="Whiz Bang, Wizzardry",
        subtitle="This is officially unofficial and hacky.",
    )


@pytest.mark.mpl_image_compare(tolerance=0.01)
def test_calendar8():
    """See if we can make a calendar plot!"""
    sts = datetime.date(2015, 5, 4)
    ets = datetime.date(2016, 1, 15)
    data = {}
    data[datetime.date(2015, 6, 6)] = {"val": "0606"}
    data[datetime.date(2015, 5, 6)] = {"val": "0506"}
    return calendar_plot(
        sts,
        ets,
        data,
        title="Whiz Bang, Wizzardry",
        subtitle="This is officially unofficial and hacky.",
    )


@pytest.mark.mpl_image_compare(tolerance=0.01)
def test_calendar4():
    """See if we can make a calendar plot!"""
    sts = datetime.date(2015, 5, 4)
    ets = datetime.date(2015, 8, 15)
    data = {}
    data[datetime.date(2015, 6, 6)] = {"val": "0606"}
    data[datetime.date(2015, 5, 6)] = {"val": "0506"}
    return calendar_plot(
        sts,
        ets,
        data,
        title="Whiz Bang, Wizzardry",
        subtitle="This is officially unofficial and hacky.\nAnd a second line",
    )


@pytest.mark.mpl_image_compare(tolerance=0.01)
def test_calendar2():
    """See if we can make a calendar plot!"""
    sts = datetime.date(2015, 5, 4)
    ets = datetime.date(2015, 6, 15)
    data = {}
    data[datetime.date(2015, 6, 6)] = {"val": "0606"}
    data[datetime.date(2015, 5, 6)] = {"val": "0506"}
    return calendar_plot(
        sts,
        ets,
        data,
        title=(
            "Whiz Bang, Wizzardry. This is even more text and we "
            "have even more."
        ),
        subtitle="This is officially unofficial and hacky.",
    )


@pytest.mark.mpl_image_compare(tolerance=0.01)
def test_calendar():
    """See if we can make a calendar plot!"""
    sts = datetime.date(2015, 5, 4)
    ets = datetime.date(2015, 5, 15)
    data = {}
    data[datetime.date(2015, 5, 16)] = {"val": 300, "color": "#ff0000"}
    data[datetime.date(2015, 5, 6)] = {"val": 1, "cellcolor": "#0000ff"}
    return calendar_plot(
        sts,
        ets,
        data,
        title="Whiz Bang, Wizzardry",
        subtitle="This is officially unofficial and hacky.",
        heatmap=True,
    )
