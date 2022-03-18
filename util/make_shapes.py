"""Serialization of geometries for use in pyIEM.plot mapping."""
import datetime
import warnings
import sys

import geopandas as gpd
from geopandas import read_postgis
from pyiem.reference import state_bounds
from pyiem.util import get_sqlalchemy_conn

warnings.filterwarnings("ignore", message=".*implementation of Parquet.*")

PATH = "../src/pyiem/data/geodf"
# Be annoying
print("Be sure to run this against Mesonet database and not laptop! DOIT!")


def dump_conus(fn):
    """states."""
    with get_sqlalchemy_conn("postgis", user="nobody") as conn:
        df = read_postgis(
            """SELECT
                ST_Transform(
                    ST_Simplify(
                        ST_Union(ST_Transform(the_geom,2163)),
                        500.),
                    4326) as geom from states
            WHERE state_abbr not in ('HI', 'AK', 'PR', 'AS', 'GU', 'MP', 'VI')
            """,
            conn,
            geom_col="geom",
        )
    df.to_parquet(fn)


def dump_states(fn):
    """states."""
    with get_sqlalchemy_conn("postgis", user="nobody") as conn:
        df = read_postgis(
            """
            SELECT state_abbr, ST_Simplify(the_geom, 0.01) as geom,
            ST_x(ST_Centroid(the_geom)) as lon,
            ST_Y(ST_Centroid(the_geom)) as lat from states
            """,
            conn,
            index_col="state_abbr",
            geom_col="geom",
        )
    df.to_parquet(fn)


def dump_climdiv(fn):
    """climate divisions."""
    with get_sqlalchemy_conn("postgis", user="nobody") as conn:
        df = read_postgis(
            """
            SELECT iemid, geom,
            ST_x(ST_Centroid(geom)) as lon,
            ST_Y(ST_Centroid(geom)) as lat
            from climdiv""",
            conn,
            index_col="iemid",
            geom_col="geom",
        )
    df.to_parquet(fn)


def dump_cwa(fn):
    """WFOs."""
    with get_sqlalchemy_conn("postgis", user="nobody") as conn:
        df = read_postgis(
            """
            SELECT wfo,
            ST_Multi(ST_Buffer(ST_Simplify(the_geom, 0.01), 0)) as geom,
            ST_x(ST_Centroid(the_geom)) as lon,
            ST_Y(ST_Centroid(the_geom)) as lat, region
            from cwa""",
            conn,
            index_col="wfo",
            geom_col="geom",
        )
    # lon, lat is used for labelling and Guam is a special case
    df.at["GUM", "lon"] = (state_bounds["GU"][0] + state_bounds["GU"][2]) / 2.0
    df.at["GUM", "lat"] = (state_bounds["GU"][1] + state_bounds["GU"][3]) / 2.0

    df.to_parquet(fn)


def dump_iowawfo(fn):
    """A region with the Iowa WFOs"""
    with get_sqlalchemy_conn("postgis", user="nobody") as conn:
        df = read_postgis(
            """ SELECT ST_Simplify(ST_Union(the_geom), 0.01) as geom
            from cwa
            WHERE wfo in ('DMX', 'ARX', 'DVN', 'OAX', 'FSD')""",
            conn,
            geom_col="geom",
        )
    df.to_parquet(fn)


def dump_ugc(gtype, fn, is_firewx=False):
    """UGCS."""
    source_limiter = "source != 'fz'"
    if is_firewx:
        source_limiter = "source = 'fz'"

    # We want UGCs valid for the time of running this script
    with get_sqlalchemy_conn("postgis", user="nobody") as conn:
        df = read_postgis(
            "SELECT ugc, wfo as cwa, simple_geom as geom, "
            "ST_x(centroid) as lon, ST_Y(centroid) as lat "
            "from ugcs WHERE begin_ts < now() and "
            "(end_ts is null or end_ts > now()) and substr(ugc, 3, 1) = %s "
            f"and {source_limiter}",
            conn,
            params=(gtype,),
            index_col="ugc",
            geom_col="geom",
        )
    df.to_parquet(fn)


def check_file(fn):
    """regression check."""
    sts = datetime.datetime.now()
    df = gpd.read_parquet(fn)
    ets = datetime.datetime.now()
    for geom in df["geom"]:
        if not geom.is_valid:
            print("Invalid Geom Found?")
            sys.exit()
    print(
        "runtime: %.5fs, entries: %s, fn: %s"
        % ((ets - sts).total_seconds(), len(df.index), fn)
    )


def getfn(prefix):
    """Make the write name."""
    return f"{PATH}/{prefix}.parquet"


def main():
    """Go Main"""
    dump_conus(getfn("conus"))
    check_file(getfn("conus"))
    dump_iowawfo(getfn("iowawfo"))
    dump_ugc("C", getfn("ugcs_county"))
    dump_ugc("Z", getfn("ugcs_zone"), is_firewx=False)
    dump_ugc("Z", getfn("ugcs_firewx"), is_firewx=True)
    check_file(getfn("ugcs_county"))
    check_file(getfn("ugcs_zone"))
    check_file(getfn("ugcs_firewx"))
    dump_cwa(getfn("cwa"))
    check_file(getfn("cwa"))
    dump_climdiv(getfn("climdiv"))
    check_file(getfn("climdiv"))
    dump_states(getfn("us_states"))
    check_file(getfn("us_states"))


if __name__ == "__main__":
    main()
