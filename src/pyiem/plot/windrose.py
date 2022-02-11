"""A WindrosePlot."""
# pylint: disable=not-callable

import numpy as np
from metpy.units import units
import matplotlib.colors as mpcolors
from matplotlib.ticker import FormatStrFormatter

# Local
from ..reference import Z_OVERLAY2
from .layouts import figure
from .util import update_kwargs_apctx

LABELS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
COLORS = ["#012cff", "#00d5f7", "#7cfd7f", "#fde801", "#ff4503", "#7e0100"]


class WindrosePlot:
    """A plot that has a single windrose on it."""

    @update_kwargs_apctx
    def __init__(self, **kwargs):
        """Construct a WindrosePlot.

        Note that `matplotlib` hard codes a `C` anchor for the axes, so the
        axes needs to be moved later, if necessary.  If you pass a `figsize`
        that is square, the legend will be placed at the bottom of the image.
        Everything else will place it in the top left corner.

        Args:
            figsize (float, float): Image figure size in inches.
            rect ([x,y,width,height]): NDC axes rectangle.
            rmax (float): Maximum radius of the windrose.
        """
        rect = kwargs.pop("rect", None)
        figsize = kwargs.pop("figsize", [8, 8])
        self.legend_anchor = "S"
        if figsize[0] != figsize[1]:
            if rect is None:
                rect = [0.1, 0.07, 0.5, 0.79]  # slide to the left
            # Non-square, place legend in top right
            self.legend_anchor = "NW"
        if rect is None:
            rect = [0, 0.12, 1, 0.76]
        self.rmax = kwargs.pop("rmax", None)
        self.fig = figure(figsize=figsize, **kwargs)
        # The vertical is the limiting factor here, since we need room for
        # the title and legend at the bottom.
        self.ax = self.fig.add_axes(
            rect,
            projection="polar",
            theta_offset=np.pi / 2.0,
            theta_direction=-1,
        )
        self.ax.set_xticks(np.arange(0, 2.0 * np.pi - 0.01, 2.0 * np.pi / 8.0))
        self.ax.set_xticklabels(LABELS)
        self.table = None
        self.calm_percent = None

    def barplot(self, direction, speed, bins, nsector, **kwargs):
        """Do the bar plotting work.

        Args:
          cmap (colormap,optional): Use matplotlib cmap for bars.
        """
        # compute histogram
        self.calm_percent, dir_centers, self.table = histogram(
            speed, direction, bins, nsector
        )
        theta = dir_centers.to(units("radian")).m
        base = np.zeros(dir_centers.m.shape[0])
        width = (theta[1] - theta[0]) * 0.8
        cmap = kwargs.get("cmap")
        if cmap is None:
            cmap = mpcolors.ListedColormap(COLORS, "wrplot")
        norm = mpcolors.BoundaryNorm(np.arange(len(bins.m) + 1), cmap.N)
        for col in range(self.table.shape[1]):
            if col < (bins.m.shape[0] - 1):
                label = f"{bins.m[col]} - {(bins.m[col + 1] - 0.1):.1f}"
            else:
                label = f"{bins.m[col]}+"
            self.ax.bar(
                theta,
                self.table[:, col].m,
                bottom=base,
                width=width,
                align="center",
                label=label,
                color=cmap(norm(col)),
            )
            base += self.table[:, col].m
        if self.rmax is not None:
            self.ax.set_ylim(0, self.rmax)
        # Place axis label in least congested spot
        self.ax.set_rlabel_position(dir_centers.m[np.argmin(base)])
        # Append a % on the label
        self.ax.yaxis.set_major_formatter(FormatStrFormatter("%.1f%%"))
        # Draw Legend
        anchor = [0.5, -0.10]
        if self.legend_anchor == "NW":
            anchor = [-0.09, 0.9]
        self.ax.legend(
            bbox_to_anchor=anchor,
            loc="center",
            ncol=1 if self.legend_anchor == "NW" else 6,
            fontsize=10,
            mode=None,
            columnspacing=0.8,
            handletextpad=0.65,
            # Ugly hack here due to aliasing in pint for mph
            title=(
                f"{'' if self.legend_anchor == 'NW' else 'Wind '}Speed "
                f"[{'mph' if bins.units == units('mph') else bins.units}]"
            ),
        )

    def plot_calm(self):
        """Clear out the center and plot the calm value."""
        maxval = np.max(np.sum(self.table, axis=1))
        # Clear out the center for plotting the calm percentage
        self.ax.set_rorigin(0 - maxval.m * 0.2)
        # Place Calm Percent in the middle
        self.ax.text(
            0.5,
            0.5,
            f"Calm\n{self.calm_percent.m:.1f}%",
            ha="center",
            va="center",
            transform=self.ax.transAxes,
        )

    def draw_logo(self):
        """Brand the plot."""
        raise DeprecationWarning(
            "This API is no longer used, pass logo={iem,dep,None} to the "
            "constructor instead."
        )

    def draw_arrows(self):
        """Place arrows on the border."""
        rmin, rmax = self.ax.get_ylim()
        for x in self.ax.get_xticks():
            # https://github.com/matplotlib/matplotlib/issues/5344
            self.ax.annotate(
                "",
                xy=(x + 0.001, rmax - (rmax - rmin) * 0.12),
                xytext=(x + 0.001, rmax + (rmax - rmin) * 0.02),
                arrowprops=dict(
                    facecolor="None",
                    edgecolor="k",
                    alpha=0.8,
                    shrink=0.09,
                    zorder=10,
                ),
                ha="center",
                va="center",
                zorder=Z_OVERLAY2,
            )


def histogram(speed, direction, bins, nsector):
    """Create the histogram on the given data.

    Args:
      speed (pint.Quantity): wind speed with units attached.
      direction (pint.Quantity): wind direction from North.
      bins (pint.Quantity): wind thresholds to use for bining.  Any value below
        the first value is considered calm.  The last value is extended to
        infinity to represent the last bin.

    Returns:
      calm_percent (float): the percentage of reports below first bin value.
      dir_centers (list): the center of the direction bins.
      table (np.ndarray): The <direction>, <speed> histogram in percent.
    """
    # Figure out the partition size
    angle = 360.0 / float(nsector)
    # Create bins based on centered around 0 degree angle_slices
    dir_bins = np.arange(-angle / 2.0, 360 + angle, angle, dtype=float)
    dir_centers = np.arange(0.0, 360.0, angle, dtype=float)
    dirvals = direction.to(units("degree")).m
    speedvals = speed.to(bins.units).m
    # compute speed bins
    speed_bins = bins.m.tolist()
    speed_bins.insert(0, -np.inf)
    speed_bins.append(np.inf)
    # Compute!
    table = np.histogram2d(
        x=dirvals, y=speedvals, bins=[dir_bins, speed_bins], normed=False
    )[0]
    # Convert to percentage
    table = table * 100.0 / table.sum()
    # Now we clean up some of the assumptions above
    # The first and last rows should be combined as they both are north
    table[0, :] = table[0, :] + table[-1, :]
    # now drop the last row as unused
    table = table[:-1, :]
    # now total up the calm percentage, first col
    calm_percent = np.sum(table[:, 0]) * units("percent")
    # drop the first column as unused
    table = table[:, 1:] * units("percent")
    return calm_percent, dir_centers * units("degree"), table


@update_kwargs_apctx
def plot(direction, speed, **kwargs):
    """Create a WindrosePlot, add bars and other standard things.

    Args:
        direction (pint.Quantity): wind direction from North.
        speed (pint.Quantity): wind speeds with units attached.
        **bins (pint.Quantity): wind speed bins to produce the histogram for.
        **nsector (int): The number of directional centers to divide the wind
          rose into.  The first sector is centered on north.
        **rmax (float): Hard codes the max radius value for the polar plot.
        **cmap (colormap): Matplotlib colormap to use.

    Returns:
        WindrosePlot
    """
    bins = kwargs.pop("bins", None)
    if bins is None:
        bins = np.array([2, 5, 10, 20]) * units("mph")
    nsector = kwargs.pop("nsector", 8)
    cmap = kwargs.pop("cmap", None)
    # kwargs gets passed verbatim to `pyiem.plot.layouts.figure`
    wp = WindrosePlot(**kwargs)
    wp.barplot(direction, speed, bins, nsector, cmap=cmap)
    wp.plot_calm()
    wp.draw_arrows()
    return wp
