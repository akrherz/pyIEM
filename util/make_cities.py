"""Create the cities pandas dataframe serialization
https://www.census.gov/geo/maps-data/data/cbf/cbf_ua.html
"""
from pandas.io.sql import read_sql
import psycopg2
import datetime
import pandas as pd
pgconn = psycopg2.connect(database='postgis', host='iemdb', user='nobody')
df = read_sql("""
    SELECT st_x(st_centroid(geom)) as lon, st_y(st_centroid(geom)) as lat,
    SUBSTRING(name10 FROM '[A-Za-z ''\.]+') as name,
    aland10 / 1000000 as area_km2 from cb_2014_us_ua10_500k
    ORDER by aland10 DESC
    """, pgconn, index_col=None)
df.to_pickle("../pyiem/data/pd_cities.pickle")
print df.head(20)

sts = datetime.datetime.now()
df = pd.read_pickle("../pyiem/data/pd_cities.pickle")
ets = datetime.datetime.now()
print (ets - sts).total_seconds()
