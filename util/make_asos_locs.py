"""ASOS locations.
"""
import datetime
from geopandas import read_postgis, read_parquet
from pyiem.util import get_dbconn

FILENAME = "../src/pyiem/data/geodf/asos.parquet"


def main():
    """Go Main Go"""
    pgconn = get_dbconn("mesosite")
    df = read_postgis(
        """
        SELECT id, name, geom from stations
        WHERE network ~* 'ASOS' or network = 'AWOS'
        or network = 'WFO'
        ORDER by id ASC
        """,
        pgconn,
        index_col=None,
        geom_col="geom",
    )
    # dedup, sigh
    df = df.groupby("id").first()
    df.to_parquet(FILENAME)
    print(df.head(20))

    sts = datetime.datetime.now()
    read_parquet(FILENAME)
    ets = datetime.datetime.now()
    print((ets - sts).total_seconds())


if __name__ == "__main__":
    main()
