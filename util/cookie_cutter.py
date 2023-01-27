"""Generate background rasters.

python cookie_cutter.py /tmp/NE2_HR_LC_SR_W_DR.tif ne2
"""
import os
import subprocess
import sys

from pyiem.plot import MapPlot
from pyiem.reference import state_names, SECTORS, wfo_bounds


def mpgen():
    """Generate map plot instances!"""
    # Twitter is about the widest we reasonably support
    for sector in SECTORS:
        yield MapPlot(sector=sector, twitter=True)
    for state in state_names:
        yield MapPlot(sector="state", state=state, twitter=True)
    for cwa in wfo_bounds:
        yield MapPlot(sector="cwa", cwa=cwa, twitter=True)
    mp = MapPlot(
        sector="custom", west=-180, north=90, east=0, south=0, twitter=True
    )
    mp.panels[0].sector_label = "default"
    yield mp


def main(argv):
    """Go Main Go."""
    for mp in mpgen():
        xmin, xmax, ymin, ymax = mp.panels[0].get_extent()
        epsg = str(mp.panels[0].crs).split(":")[1]
        label = mp.panels[0].get_sector_label()
        basedir = "/opt/miniconda3/pyiem_data/backgrounds"
        if label in ["conus", "default"]:
            basedir = "../src/pyiem/data/backgrounds"
        fnbase = f"{basedir}/{argv[2]}/" f"{label}_{epsg}"
        # buffer 10%
        xbuf = (xmax - xmin) * 0.05
        ybuf = (ymax - ymin) * 0.05
        cmd = [
            "gdalwarp",
            "-t_srs",
            f"{mp.panels[0].crs}",
            "-te",
            f"{xmin - xbuf}",
            f"{ymin - ybuf}",
            f"{xmax + xbuf}",
            f"{ymax + ybuf}",
            "-ts",
            "1280",
            "1024",
            "-co",
            "WORLDFILE=ON",
            "-overwrite",
            argv[1],
            f"{fnbase}.png",
        ]
        subprocess.call(cmd)
        os.unlink(f"{fnbase}.png.aux.xml")
        mp.close()


if __name__ == "__main__":
    main(sys.argv)
