"""Copy GEMPAK table into a parquet file for table usage."""
# stdlib
import datetime

# third party
import pandas as pd
import geopandas as gpd

# Local
from pyiem.util import logger

LOG = logger()
# custom appended from 16 Jul 2021 GC email
QUEUE = {"stns/sfstns.tbl": "sfstns.parquet"}
BASEDIR = "../src/pyiem/data/geodf/"
GEMPAKDIR = "/home/akrherz/projects/gempak/gempak/tables/"


def rectify(sid):
    """Make it match our nomenclature."""
    if len(sid) == 4 and sid.startswith("K"):
        return sid[1:]
    return sid


def process(gemtbl, outfn):
    """Do the processing work!"""
    rows = []
    for line in open(GEMPAKDIR + gemtbl):
        if line.strip() == "" or line.startswith("#") or line.startswith("!"):
            continue
        sid = rectify(line[:4].strip())
        name = line[16:47].strip()
        lat = float(line[56:60]) / 100.0
        lon = float(line[61:67]) / 100.0
        rows.append({"sid": sid, "name": name, "lon": lon, "lat": lat})

    LOG.info("Found %s rows in GEMPAK table %s", len(rows), gemtbl)
    df = pd.DataFrame(rows).groupby("sid").first()
    LOG.info("after dedup, there are %s rows", len(df.index))
    df = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat))
    df = df.drop(["lon", "lat"], axis=1)
    df.to_parquet(BASEDIR + outfn)
    print(df.head(20))

    sts = datetime.datetime.now()
    gpd.read_parquet(BASEDIR + outfn)
    ets = datetime.datetime.now()
    print((ets - sts).total_seconds())


def main():
    """Go Main Go"""
    for gemtbl, outfn in QUEUE.items():
        process(gemtbl, outfn)


if __name__ == "__main__":
    main()
