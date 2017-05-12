"""Calendar Plot"""
import datetime
import matplotlib
from matplotlib.patches import Rectangle
matplotlib.use('agg')
import matplotlib.pyplot as plt


def calendar_plot(sts, ets, data, **kwargs):
    """Create a plot that looks like a calendar

    Args:
      sts (datetime.date): start date of this plot
      ets (datetime.date): end date of this plot
      data (dict[dict]): dictionary with keys of dates and dicts for
        `val` value and optionally `color` for color
    """
    weeks = 1
    now = sts
    while now <= ets:
        if now.isoweekday() == 7 and now != sts:
            weeks += 1
        now += datetime.timedelta(days=1)

    # we need 50 pixels per week, 100 dpi
    boxpixelx = 100
    boxpixely = 50
    headerheight = 125
    height = (headerheight + (weeks * boxpixely)) / 100.
    pixelwidth = 20 + boxpixelx * 7
    pixelheight = int(height * 100)

    fig = plt.figure(figsize=(7.2, height))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.get_xaxis().set_visible(False)
    ax.get_yaxis().set_visible(False)

    dx = boxpixelx / float(pixelwidth)
    dy = boxpixely / float(pixelheight)
    offx = 10 / float(pixelwidth)
    offy = 35 / float(pixelheight)
    offx3 = 3 / float(pixelwidth)
    offy3 = 3 / float(pixelheight)

    ax.text(0.5, 0.99, kwargs.get('title', ''), va='top',
            ha='center')

    for i, dow in enumerate(['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']):
        ax.text(offx + dx * i + (dx / 2.), offy + (weeks * dy) + (dy/2.), dow,
                ha='center')

    now = sts
    week = 1
    while now <= ets:
        weekday = now.isoweekday()
        # Sunday
        if weekday == 7:
            weekday = 0
        if weekday == 0 and now != sts:
            week += 1
        # Compute the lower left corner of where we are in the world
        x = offx + weekday * dx
        y = offy + ((weeks - week) * boxpixely) / float(pixelheight)
        color = 'k'
        fmt = '%-d'
        if now.day == 1:
            fmt = '%b %-d'
            color = 'g'
        ax.text(x + offx3, y + dy - offy3, "%s" % (now.strftime(fmt), ),
                transform=ax.transAxes, va='top', color=color)
        val = data.get(now, dict()).get('val')
        if val is not None:
            color = data[now].get('color', 'k')
            ax.text(x + offx3 + (dx/2.), y + (dy/2.5) - offy3,
                    val, transform=ax.transAxes, va='center',
                    ha='center', color=color, fontsize=16)

        rect = Rectangle((x, y), dx, dy, zorder=2,
                         facecolor='None', edgecolor='tan')
        ax.add_patch(rect)
        now += datetime.timedelta(days=1)

    return fig
