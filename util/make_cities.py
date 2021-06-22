"""Create the cities pandas dataframe serialization
https://geodata.lib.berkeley.edu/catalog/stanford-bx729wr3020
"""
import datetime
import pandas as pd
from pandas.io.sql import read_sql
from pyiem.util import get_dbconn


def main():
    """Go Main Go"""
    pgconn = get_dbconn("postgis")
    df = read_sql(
        """
        SELECT st_x(geom) as lon, st_y(geom) as lat,
        name, pop_2010 from citiesx010g WHERE pop_2010 > 500
        ORDER by pop_2010 DESC
        """,
        pgconn,
        index_col=None,
    )
    df.to_pickle("../src/pyiem/data/pd_cities.pickle")
    print(df.head(20))

    sts = datetime.datetime.now()
    pd.read_pickle("../src/pyiem/data/pd_cities.pickle")
    ets = datetime.datetime.now()
    print((ets - sts).total_seconds())


if __name__ == "__main__":
    main()
