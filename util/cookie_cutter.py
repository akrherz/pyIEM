"""Generate background rasters.

python cookie_cutter.py /tmp/NE2_HR_LC_SR_W_DR.tif ne2
"""
import os
import subprocess
import sys

from pyiem.plot import MapPlot
from pyiem.reference import SECTORS, state_names, wfo_bounds


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


def run_warp(crs, xmin, ymin, xmax, ymax, infn, outfn, width=1280, hgt=1024):
    """Go run warp."""
    cmd = [
        "gdalwarp",
        "-t_srs",
        f"{crs}",
        "-te",
        f"{xmin}",
        f"{ymin}",
        f"{xmax}",
        f"{ymax}",
        "-ts",
        f"{width}",
        f"{hgt}",
        "-co",
        "WORLDFILE=ON",
        "-overwrite",
        infn,
        outfn,
    ]
    subprocess.call(cmd)
    os.unlink(f"{outfn}.aux.xml")


def main(argv):
    """Go Main Go."""
    fn = f"/opt/miniconda3/pyiem_data/backgrounds/{argv[2]}/custom_4326.png"
    run_warp("EPSG:4326", -120, 23, -60, 50, argv[1], fn, width=3600, hgt=1700)

    for mp in mpgen():
        xmin, xmax, ymin, ymax = mp.panels[0].get_extent()
        epsg = str(mp.panels[0].crs).split(":")[1]
        label = mp.panels[0].get_sector_label()
        basedir = "/opt/miniconda3/pyiem_data/backgrounds"
        if label in ["conus", "default"]:
            basedir = "../src/pyiem/data/backgrounds"
        # buffer 10%
        xbuf = (xmax - xmin) * 0.05
        ybuf = (ymax - ymin) * 0.05
        run_warp(
            mp.panels[0].crs,
            xmin - xbuf,
            ymin - ybuf,
            xmax + xbuf,
            ymax + ybuf,
            argv[1],
            f"{basedir}/{argv[2]}/{label}_{epsg}.png",
        )
        mp.close()


if __name__ == "__main__":
    main(sys.argv)
