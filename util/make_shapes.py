"""Serialization of geometries for use in pyIEM.plot mapping."""

import datetime
import sys
import warnings

import geopandas as gpd

from pyiem.database import get_sqlalchemy_conn, sql_helper
from pyiem.reference import state_bounds
from pyiem.util import logger, utc

warnings.filterwarnings("ignore", message=".*implementation of Parquet.*")

LOG = logger()
PATH = "../src/pyiem/data/geodf"
# Be annoying
LOG.info("Be sure to run this against Mesonet database and not laptop! DOIT!")


def dump_conus(fn):
    """states."""
    with get_sqlalchemy_conn("postgis", user="nobody") as conn:
        df = gpd.read_postgis(
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
        df = gpd.read_postgis(
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
        df = gpd.read_postgis(
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
        df = gpd.read_postgis(
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
        df = gpd.read_postgis(
            """ SELECT ST_Simplify(ST_Union(the_geom), 0.01) as geom
            from cwa
            WHERE wfo in ('DMX', 'ARX', 'DVN', 'OAX', 'FSD')""",
            conn,
            geom_col="geom",
        )
    df.to_parquet(fn)


def dump_fema_regions(fn):
    """Dump fema regions."""
    with get_sqlalchemy_conn("postgis", user="nobody") as conn:
        df = gpd.read_postgis(
            sql_helper("""SELECT region, states,
                ST_MakeValid(ST_Simplify(geom, 0.01)) as geom
            from fema_regions"""),
            conn,
            geom_col="geom",
            index_col="region",
        )  # type: ignore
    df.to_parquet(fn)


def dump_ugc(
    gtype: str, fn: str, is_firewx: bool = False, discontinued: bool = False
):
    """Dump UGCs.

    Args:
        gtype (str): C or Z
        fn (str): filename to write
        is_firewx (bool): is this for fire weather
        discontinued (bool): include discontinued UGCs
    """
    params = {"gtype": gtype, "valid": utc()}
    source_limiter = "source != 'fz'"
    if is_firewx:
        source_limiter = "source = 'fz'"
    sql = """
    SELECT ugc, wfo as cwa, simple_geom as geom,
    ST_x(centroid) as lon, ST_Y(centroid) as lat
    from ugcs WHERE begin_ts < :valid and
    (end_ts is null or end_ts > :valid) and substr(ugc, 3, 1) = :gtype
    and {source_limiter} ORDER by ugc ASC
    """
    if discontinued:
        # Life choice here is just to include the most recent version
        sql = """
    with discontinued as (
        SELECT ugc from ugcs WHERE ugc not in (
            select ugc from ugcs where begin_ts < :valid and
            (end_ts is null or end_ts > :valid))
        and substr(ugc, 3, 1) = :gtype
        and {source_limiter}),
    agg as (
        select ugc, rank() OVER (PARTITION by ugc ORDER by end_ts DESC),
        wfo as cwa, simple_geom as geom,
        st_x(centroid) as lon, st_y(centroid) as lat
        from ugcs where ugc in (select ugc from discontinued) and
        {source_limiter})
    SELECT * from agg where rank = 1 ORDER by ugc ASC
        """

    # We want UGCs valid for the time of running this script
    with get_sqlalchemy_conn("postgis", user="nobody") as conn:
        df = gpd.read_postgis(
            sql_helper(sql, source_limiter=source_limiter),
            conn,
            params=params,
            index_col="ugc",
            geom_col="geom",
        )  # type: ignore
    df.to_parquet(fn)


def check_file(fn):
    """regression check."""
    sts = datetime.datetime.now()
    df = gpd.read_parquet(fn)
    ets = datetime.datetime.now()
    for idx, row in df.iterrows():
        if not row["geom"].is_valid:
            LOG.info("%s Abort, invalid geom found @%s %s", fn, idx, row)
            sys.exit()
    LOG.info(
        f"runtime: {(ets - sts).total_seconds():.5f}s, "
        + f"entries: {len(df.index)}, fn: {fn}"
    )


def getfn(prefix):
    """Make the write name."""
    return f"{PATH}/{prefix}.parquet"


def main():
    """Go Main"""
    dump_ugc("C", getfn("ugcs_county"))
    check_file(getfn("ugcs_county"))
    dump_ugc("Z", getfn("ugcs_zone"), is_firewx=False)
    check_file(getfn("ugcs_zone"))
    dump_ugc("Z", getfn("ugcs_firewx"), is_firewx=True)
    check_file(getfn("ugcs_firewx"))
    dump_ugc("C", getfn("ugcs_county_discontinued"), discontinued=True)
    check_file(getfn("ugcs_county_discontinued"))
    dump_ugc(
        "Z",
        getfn("ugcs_zone_discontinued"),
        is_firewx=False,
        discontinued=True,
    )
    check_file(getfn("ugcs_zone_discontinued"))
    dump_ugc(
        "Z",
        getfn("ugcs_firewx_discontinued"),
        is_firewx=True,
        discontinued=True,
    )
    check_file(getfn("ugcs_firewx_discontinued"))
    dump_fema_regions(getfn("fema_regions"))
    check_file(getfn("fema_regions"))
    dump_conus(getfn("conus"))
    check_file(getfn("conus"))
    dump_iowawfo(getfn("iowawfo"))
    dump_cwa(getfn("cwa"))
    check_file(getfn("cwa"))
    dump_climdiv(getfn("climdiv"))
    check_file(getfn("climdiv"))
    dump_states(getfn("us_states"))
    check_file(getfn("us_states"))


if __name__ == "__main__":
    main()
