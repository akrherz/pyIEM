"""Create the cities pandas dataframe serialization
https://geodata.lib.berkeley.edu/catalog/stanford-bx729wr3020
"""
import datetime
from geopandas import read_postgis, read_parquet
from pyiem.util import get_dbconn

FILENAME = "../src/pyiem/data/geodf/cities.parquet"


def main():
    """Go Main Go"""
    pgconn = get_dbconn("postgis")
    df = read_postgis(
        """
        SELECT geom, name, pop_2010 from citiesx010g WHERE pop_2010 > 500
        ORDER by pop_2010 DESC
        """,
        pgconn,
        index_col=None,
        geom_col="geom",
    )
    df.to_parquet(FILENAME)
    print(df.head(20))

    sts = datetime.datetime.now()
    read_parquet(FILENAME)
    ets = datetime.datetime.now()
    print((ets - sts).total_seconds())


if __name__ == "__main__":
    main()
