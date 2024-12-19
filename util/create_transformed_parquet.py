"""Cache transformed data in parquet format.

1. Process cartopy offlinedata
2. Process pyiem bunded geodf
"""

import os

import click
import geopandas as gpd

from pyiem.reference import EPSG
from pyiem.util import logger

LOG = logger()


@click.command()
@click.option("--writepath", default="/opt/miniconda3/pyiem_data/")
@click.option("--justgeodf", is_flag=True, default=False)
def main(writepath, justgeodf):
    """Do Work."""
    pyiem_geodf = os.path.join(
        os.path.dirname(__file__), "..", "src", "pyiem", "data", "geodf"
    )
    for filename in os.listdir(pyiem_geodf):
        LOG.warning("processing %s", filename)
        df = gpd.read_parquet(f"{pyiem_geodf}/{filename}")
        if df.crs is None:
            df = df.set_crs("EPSG:4326")
        for epsg, crs in EPSG.items():
            parquetfn = f"{writepath}/parquet/{epsg}/geodf/{filename}"
            os.makedirs(os.path.dirname(parquetfn), exist_ok=True)
            df.to_crs(crs).to_parquet(parquetfn)
    cartopy_shapefiles = f"{os.environ['CARTOPY_DATA_DIR']}/shapefiles/"
    for root, _dirnames, filenames in os.walk(cartopy_shapefiles):
        for shapefilefn in [s for s in filenames if s.endswith(".shp")]:
            # HACK for CI to speed up, but have one file available
            if justgeodf and shapefilefn != "ne_10m_land.shp":
                continue
            ppath = root.replace(cartopy_shapefiles, "")
            LOG.warning("%s/%s", root, shapefilefn)
            df = gpd.read_file(f"{root}/{shapefilefn}", engine="pyogrio")
            if df.crs is None:
                df = df.set_crs("EPSG:4326")
            for epsg, crs in EPSG.items():
                parquetfn = (
                    f"{writepath}/parquet/{epsg}/{ppath}/"
                    f"{shapefilefn.replace('.shp', '.parquet')}"
                )
                os.makedirs(os.path.dirname(parquetfn), exist_ok=True)
                df.to_crs(crs).to_parquet(parquetfn)


if __name__ == "__main__":
    main()
