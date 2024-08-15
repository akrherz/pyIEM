"""Create the cities pandas dataframe serialization
https://geodata.lib.berkeley.edu/catalog/stanford-bx729wr3020
"""

from geopandas import read_parquet, read_postgis

from pyiem.database import get_dbconn

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
    read_parquet(FILENAME)


if __name__ == "__main__":
    main()
