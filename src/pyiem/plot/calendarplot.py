"""Calendar Plot."""
import os
from collections import OrderedDict
import datetime
import calendar

import numpy as np
import matplotlib.colors as mpcolors
from matplotlib.patches import Rectangle
from pyiem.plot.use_agg import plt
from pyiem.plot.colormaps import get_cmap
from pyiem.plot.util import fitbox, fontscale, update_kwargs_apctx
from pyiem.plot.layouts import figure
from pyiem.reference import (
    TWITTER_RESOLUTION_INCH,
    Z_FILL,
    Z_FRAME,
    Z_OVERLAY,
    Z_OVERLAY2,
    Z_OVERLAY_LABEL,
    Z_OVERLAY2_LABEL,
)

DATADIR = os.sep.join([os.path.dirname(__file__), "..", "data"])


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

    monthtotalwidth = 1.0 / float(cols)
    monthtotalheight = 0.86 / float(rows)
    monthwidth = monthtotalwidth - 2 * hpadding
    monthheight = monthtotalheight - 2 * vpadding

    gx = 0
    gy = 0.9  # upper left corners here
    for i, month in enumerate(months):
        col = i % cols
        row = int(i / cols)
        llx = gx + col * monthtotalwidth
        lly = gy - (row + 1) * monthtotalheight
        bounds[month] = [
            llx + hpadding,
            lly + vpadding,
            monthwidth,
            monthheight,
        ]
    return bounds


def _do_cell(axes, now, data, row, dx, dy, kwargs):
    """Do what work is necessary within the cell"""
    val = data.get(now, {}).get("val")
    cellcolor = (
        "None"
        if kwargs.get("norm") is None or val is None
        else kwargs["cmap"](kwargs["norm"]([val]))[0]
    )
    offx = (now.weekday() + 1) if now.weekday() != 6 else 0
    cellcolor = data.get(now, {}).get("cellcolor", cellcolor)
    rect = Rectangle(
        (offx * dx, 0.9 - (row + 1) * dy),
        dx,
        dy,
        zorder=Z_OVERLAY if val is None else Z_OVERLAY2,
        facecolor=cellcolor,
        edgecolor="tan" if val is None else "k",
    )
    axes.add_patch(rect)
    if val is None or (isinstance(val, str) and val.strip() == ""):
        return
    color = "k"
    if not isinstance(cellcolor, str):  # this is a string comp here
        color = (
            "k"
            if (
                cellcolor[0] * 256 * 0.299
                + cellcolor[1] * 256 * 0.587
                + cellcolor[2] * 256 * 0.114
            )
            > 186
            else "white"
        )
    color = data[now].get("color", color)
    # We need to translate the axes NDC coordinates back to the figure coords
    bbox = axes.get_position()
    sdx = (bbox.x1 - bbox.x0) * dx
    sdy = (bbox.y1 - bbox.y0) * dy
    x0 = bbox.x0 + offx * sdx
    ytop = bbox.y0 + (bbox.y1 - bbox.y0) * 0.9
    y0 = ytop - (row + 1) * sdy
    fitbox(
        plt.gcf(),
        val,
        x0,
        x0 + sdx,
        y0,
        y0 + sdy * 0.55,
        ha="center",
        va="center",
        color=color,
        fontsize=kwargs.get("fontsize"),
        zorder=Z_OVERLAY2_LABEL,
    )


def _do_month(month, axes, data, in_sts, in_ets, kwargs):
    """Place data on this axes"""
    # No ticks
    axes.get_xaxis().set_visible(False)
    axes.get_yaxis().set_visible(False)
    # Update axes frame zorder to be on-top
    for _, spine in axes.spines.items():
        spine.set_zorder(Z_FRAME)
    pos = axes.get_position()
    ndcheight = pos.y1 - pos.y0
    ndcwidth = pos.x1 - pos.x0

    fitbox(
        plt.gcf(),
        month.strftime("%B %Y"),
        pos.x0,
        pos.x1,
        pos.y1,
        pos.y1 + 0.028,
        ha="center",
        zorder=Z_OVERLAY,
    )

    axes.add_patch(
        Rectangle(
            (0.0, 0.90),
            1,
            0.1,
            facecolor="tan",
            edgecolor="tan",
            zorder=Z_FILL,
        )
    )

    sts = datetime.date(month.year, month.month, 1)
    ets = (sts + datetime.timedelta(days=35)).replace(day=1)

    calendar.setfirstweekday(calendar.SUNDAY)
    weeks = len(calendar.monthcalendar(month.year, month.month))
    now = sts
    row = 0
    dy = 0.9 / float(weeks)
    dx = 1.0 / 7.0
    for i, dow in enumerate(["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]):
        axes.text(
            1.0 / 7.0 * (i + 0.5),
            0.94,
            dow,
            fontsize=fontscale(ndcwidth / 8.0 * 0.4),
            ha="center",
            va="center",
            zorder=Z_OVERLAY_LABEL,
        )
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
            f"{now.day}",
            fontsize=fontscale(ndcheight / 5.0 * 0.25),
            color="tan",
            va="top",
            zorder=Z_OVERLAY2_LABEL,
        )
        _do_cell(axes, now, data, row, dx, dy, kwargs)
        now += datetime.timedelta(days=1)


@update_kwargs_apctx
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
        apctx (dict): autoplot context.
    """
    bounds = _compute_bounds(sts, ets)
    figsize = kwargs.get("figsize", TWITTER_RESOLUTION_INCH)
    # Compute the number of month calendars we need.

    # We want 'square' boxes for each month's calendar, 4x3
    fig = figure(figsize=figsize, dpi=kwargs.get("dpi", 100))
    if "fontsize" not in kwargs:
        kwargs["fontsize"] = 12
        if len(bounds) < 3:
            kwargs["fontsize"] = 36
        elif len(bounds) < 5:
            kwargs["fontsize"] = 16
        elif len(bounds) < 10:
            kwargs["fontsize"] = 14
    if kwargs.get("heatmap", False):
        kwargs["cmap"] = get_cmap(kwargs.get("cmap", "viridis"))
        maxval = -1000
        for key in data:
            if data[key]["val"] > maxval:
                maxval = data[key]["val"]
        # Need at least 3 slots
        maxval = 5 if maxval < 5 else maxval
        # Need to have more colors than bins
        kwargs["norm"] = mpcolors.BoundaryNorm(
            np.arange(0, maxval, int(maxval / 255.0) + 1), kwargs["cmap"].N
        )
    for month in bounds:
        ax = fig.add_axes(bounds[month])
        _do_month(month, ax, data, sts, ets, kwargs)

    title = kwargs.get("title")
    if title is not None:
        fitbox(fig, title, 0.1, 0.99, 0.95, 0.99)

    subtitle = kwargs.get("subtitle")
    if subtitle is not None:
        if subtitle.find("\n") > 0:  # Allow more room
            fitbox(fig, subtitle, 0.1, 0.99, 0.909, 0.949)
        else:
            fitbox(fig, subtitle, 0.1, 0.99, 0.925, 0.945)

    return fig
