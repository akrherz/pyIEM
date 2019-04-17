"""pyiem.plot.util Plotting Utilities!"""


def fitbox(fig, text, x0, x1, y0, y1, **kwargs):
    """Fit text into a NDC box."""
    figbox = fig.get_window_extent().transformed(
        fig.dpi_scale_trans.inverted())
    # need some slop for decimal comparison below
    px0 = x0 * fig.dpi * figbox.width - 0.15
    px1 = x1 * fig.dpi * figbox.width + 0.15
    py0 = y0 * fig.dpi * figbox.height - 0.15
    py1 = y1 * fig.dpi * figbox.height + 0.15
    # print("px0: %s px1: %s py0: %s py1: %s" % (px0, px1, py0, py1))
    xanchor = x0
    if kwargs.get('ha', '') == 'center':
        xanchor = x0 + (x1 - x0) / 2.
    yanchor = y0
    if kwargs.get('va', '') == 'center':
        yanchor = y0 + (y1 - y0) / 2.
    txt = fig.text(
        xanchor, yanchor, text,
        fontsize=50, ha=kwargs.get('ha', 'left'),
        va=kwargs.get('va', 'bottom'),
        color=kwargs.get('color', 'k')
    )
    for fs in range(50, 1, -2):
        txt.set_fontsize(fs)
        tbox = txt.get_window_extent(fig.canvas.get_renderer())
        # print("fs: %s tbox: %s" % (fs, str(tbox)))
        if (tbox.x0 >= px0 and tbox.x1 < px1 and tbox.y0 >= py0 and
                tbox.y1 <= py1):
            break
    return txt
