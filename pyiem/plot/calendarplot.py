"""Calendar Plot"""
from collections import OrderedDict
import datetime

import matplotlib
from matplotlib.patches import Rectangle
matplotlib.use('agg')
import matplotlib.pyplot as plt  # NOPEP8


def _compute_bounds(sts, ets):
    """figure out our monthly calendar bounding boxes"""
    now = sts
    months = []
    while now <= ets:
        months.append(now.strftime("%Y%m"))
        now += datetime.timedelta(days=33)
        now = now.replace(day=1)

    bounds = OrderedDict()
    # 1x1
    padding = 0.025
    if len(months) == 1:
        cols = 1
        width = 1 - 2. * padding
        height = 0.88 - padding
    # 2x2
    elif len(months) <= 4:
        cols = 2
        width = (1. - 3 * padding) / 2.
        height = (0.88 - 2 * padding) / 2.
    # 3x3
    elif len(months) <= 9:
        cols = 3
        width = (1. - 4 * padding) / 3.
        height = (0.88 - 3 * padding) / 3.
    # 3x4
    else:
        cols = 3
        width = (1. - 4 * padding) / 3.
        height = (0.88 - 4 * padding) / 4.

    gx = padding
    gy = 0.9  # upper left corners here
    for i, month in enumerate(months):
        col = (i % cols)
        row = (i / cols) + 1
        bounds[month] = [gx + (col * width) + (col * padding),
                         gy - (row * height) - ((row - 1) * padding),
                         width, height]

    return bounds


def _do_month(month, axes, data, in_sts, in_ets, fontsize):
    """Place data on this axes"""
    axes.get_xaxis().set_visible(False)
    axes.get_yaxis().set_visible(False)

    axes.add_patch(Rectangle((0., 0.90), 1, 0.1, zorder=2,
                             facecolor='tan', edgecolor='tan'))
    axes.text(0.5, 1.01, "%s" % (month, ),
              transform=axes.transAxes, zorder=3, ha='center')

    sts = datetime.date(int(month[:4]), int(month[4:]), 1)
    ets = (sts + datetime.timedelta(days=35)).replace(day=1)

    weeks = int((sts.isoweekday() + (ets - sts).days - 1.) / 7.)
    if (sts.isoweekday() + (ets - sts).days - 1) % 7. != 0:
        weeks += 1
    now = sts
    row = 0
    dy = 0.9 / float(weeks)
    dx = 1. / 7.
    for i, dow in enumerate(['SUN', 'MON', 'TUE', 'WED', 'THU',
                             'FRI', 'SAT']):
        axes.text(1. / 7. * (i + 0.5), 0.95, dow, ha='center', va='center')
    while now < ets:
        val = data.get(now, dict()).get('val')
        if now.isoweekday() == 1 and now != sts:
            row += 1
        if now < in_sts or now >= in_ets:
            now += datetime.timedelta(days=1)
            continue
        bgcolor = 'tan' if val is None else 'k'
        axes.text((now.isoweekday() - 1) * dx + 0.01,
                  0.9 - row * dy - 0.01,
                  str(now.day), fontsize=(fontsize - 4),
                  color='tan',
                  va='top')
        rect = Rectangle(((now.isoweekday() - 1) * dx,
                          0.9 - (row + 1) * dy), dx, dy,
                         zorder=(2 if val is None else 3),
                         facecolor='None', edgecolor=bgcolor)
        axes.add_patch(rect)
        if val is not None:
            color = data[now].get('color', 'k')
            axes.text((now.isoweekday() - 1) * dx + (dx/2.),
                      0.9 - (row + 1) * dy + (dy * 0.25),
                      val, transform=axes.transAxes, va='center',
                      ha='center', color=color, fontsize=fontsize)
        now += datetime.timedelta(days=1)


def calendar_plot(sts, ets, data, **kwargs):
    """Create a plot that looks like a calendar

    Args:
      sts (datetime.date): start date of this plot
      ets (datetime.date): end date of this plot (inclusive)
      data (dict[dict]): dictionary with keys of dates and dicts for
        `val` value and optionally `color` for color
    """
    bounds = _compute_bounds(sts, ets)
    # Compute the number of month calendars we need.

    # We want 'square' boxes for each month's calendar, 4x3
    fig = plt.figure(figsize=(10.24, 7.68))
    fontsize = 12
    if len(bounds) < 3:
        fontsize = 18
    elif len(bounds) < 5:
        fontsize = 16
    elif len(bounds) < 10:
        fontsize = 14
    for month in bounds:
        ax = fig.add_axes(bounds[month])
        _do_month(month, ax, data, sts, ets, fontsize)

    fig.text(0.5, 0.99, kwargs.get('title', ''), va='top',
             ha='center')
    return fig
