"""Calendar Plot"""
import os
from collections import OrderedDict
import datetime
import calendar

import numpy as np
import matplotlib.colors as mpcolors
from matplotlib.patches import Rectangle
import matplotlib.image as mpimage
from pyiem.plot.use_agg import plt
from pyiem.plot.util import fitbox, fontscale

DATADIR = os.sep.join([os.path.dirname(__file__), '..', 'data'])


def iemlogo(fig):
    """Place the IEM Logo"""
    fn = '%s/%s' % (DATADIR, 'logo.png')
    if not os.path.isfile(fn):
        return
    logo = mpimage.imread(fn)
    y0 = fig.get_figheight() * 100. - logo.shape[0] - 5
    fig.figimage(logo, 5, y0, zorder=3)


def _compute_bounds(sts, ets):
    """figure out our monthly calendar bounding boxes"""
    now = sts
    months = []
    lastmonth = -1
    while now <= ets:
        if now.month != lastmonth:
            months.append(now)
            lastmonth = now.month
        now += datetime.timedelta(days=1)

    bounds = OrderedDict()
    # 1x1
    vpadding = 0.015
    hpadding = 0.01
    if len(months) == 1:
        cols = 1
        rows = 1
    # 1x2
    elif len(months) < 3:
        cols = 2
        rows = 1
    # 2x2
    elif len(months) <= 4:
        cols = 2
        rows = 2
    # 3x3
    elif len(months) <= 9:
        cols = 3
        rows = 3
    # 3x4
    else:
        cols = 3
        rows = 4

    monthtotalwidth = 1. / float(cols)
    monthtotalheight = 0.86 / float(rows)
    monthwidth = monthtotalwidth - 2 * hpadding
    monthheight = monthtotalheight - 2 * vpadding

    gx = 0
    gy = 0.9  # upper left corners here
    for i, month in enumerate(months):
        col = (i % cols)
        row = int(i / cols)
        llx = gx + col * monthtotalwidth
        lly = gy - (row + 1) * monthtotalheight
        bounds[month] = [
            llx + hpadding,
            lly + vpadding,
            monthwidth,
            monthheight]
    return bounds


def _do_cell(axes, now, data, row, dx, dy, kwargs):
    """Do what work is necessary within the cell"""
    val = data.get(now, dict()).get('val')
    cellcolor = ('None'
                 if kwargs.get('norm') is None or val is None
                 else kwargs['cmap'](kwargs['norm']([val, ]))[0])
    offx = (now.weekday() + 1) if now.weekday() != 6 else 0
    cellcolor = data.get(now, dict()).get('cellcolor', cellcolor)
    rect = Rectangle((offx * dx, 0.9 - (row + 1) * dy), dx, dy,
                     zorder=(2 if val is None else 3),
                     facecolor=cellcolor,
                     edgecolor='tan' if val is None else 'k')
    axes.add_patch(rect)
    if val is None:
        return
    color = 'k'
    if not isinstance(cellcolor, str):  # this is a string comp here
        color = ('k'
                 if (cellcolor[0] * 256 * 0.299 +
                     cellcolor[1] * 256 * 0.587 +
                     cellcolor[2] * 256 * 0.114) > 186
                 else 'white')
    color = data[now].get('color', color)
    axes.text(offx * dx + (dx/2.),
              0.9 - (row + 1) * dy + (dy * 0.25),
              val, transform=axes.transAxes, va='center',
              ha='center', color=color,
              fontsize=kwargs['fontsize'])


def _do_month(month, axes, data, in_sts, in_ets, kwargs):
    """Place data on this axes"""
    axes.get_xaxis().set_visible(False)
    axes.get_yaxis().set_visible(False)
    pos = axes.get_position()
    ndcheight = (pos.y1 - pos.y0)
    ndcwidth = (pos.x1 - pos.x0)

    fitbox(
        plt.gcf(), month.strftime("%B %Y"),
        pos.x0, pos.x1, pos.y1, pos.y1 + 0.028, ha='center'
    )

    axes.add_patch(Rectangle((0., 0.90), 1, 0.1, zorder=2,
                             facecolor='tan', edgecolor='tan'))

    sts = datetime.date(month.year, month.month, 1)
    ets = (sts + datetime.timedelta(days=35)).replace(day=1)

    calendar.setfirstweekday(calendar.SUNDAY)
    weeks = len(calendar.monthcalendar(month.year, month.month))
    now = sts
    row = 0
    dy = 0.9 / float(weeks)
    dx = 1. / 7.
    for i, dow in enumerate(['SUN', 'MON', 'TUE', 'WED', 'THU',
                             'FRI', 'SAT']):
        axes.text(
            1. / 7. * (i + 0.5), 0.94, dow,
            fontsize=fontscale(ndcwidth / 7. * 0.4),
            ha='center', va='center')
    while now < ets:
        # Is this Sunday?
        if now.weekday() == 6 and now != sts:
            row += 1
        if now < in_sts or now > in_ets:
            now += datetime.timedelta(days=1)
            continue
        offx = (now.weekday() + 1) if now.weekday() != 6 else 0
        axes.text(
            offx * dx + 0.01,
            0.9 - row * dy - 0.01,
            str(now.day), fontsize=fontscale(ndcheight / 5. * 0.25),
            color='tan',
            va='top'
        )
        _do_cell(axes, now, data, row, dx, dy, kwargs)
        now += datetime.timedelta(days=1)


def calendar_plot(sts, ets, data, **kwargs):
    """Create a plot that looks like a calendar

    Args:
      sts (datetime.date): start date of this plot
      ets (datetime.date): end date of this plot (inclusive)
      data (dict[dict]): dictionary with keys of dates and dicts for
        `val` value and optionally `color` for color
      kwargs (dict):
        heatmap (bool): background color for cells based on `val`, False
        cmap (str): color map to use for norm
    """
    bounds = _compute_bounds(sts, ets)
    # Compute the number of month calendars we need.

    # We want 'square' boxes for each month's calendar, 4x3
    fig = plt.figure(figsize=(10.24, 7.68))
    if 'fontsize' not in kwargs:
        kwargs['fontsize'] = 12
        if len(bounds) < 3:
            kwargs['fontsize'] = 18
        elif len(bounds) < 5:
            kwargs['fontsize'] = 16
        elif len(bounds) < 10:
            kwargs['fontsize'] = 14
    if kwargs.get('heatmap', False):
        kwargs['cmap'] = plt.get_cmap(kwargs.get('cmap', 'viridis'))
        maxval = -1000
        for key in data:
            if data[key]['val'] > maxval:
                maxval = data[key]['val']
        # Need at least 3 slots
        maxval = 5 if maxval < 5 else maxval
        kwargs['norm'] = mpcolors.BoundaryNorm(np.arange(0, maxval),
                                               kwargs['cmap'].N)
    for month in bounds:
        ax = fig.add_axes(bounds[month])
        _do_month(month, ax, data, sts, ets, kwargs)

    iemlogo(fig)
    title = kwargs.get('title')
    if title is not None:
        fitbox(fig, title, 0.1, 0.99, 0.95, 0.99)

    subtitle = kwargs.get('subtitle')
    if subtitle is not None:
        fitbox(fig, subtitle, 0.1, 0.99, 0.925, 0.945)

    return fig
