"""Serialization of geometries for use in pyIEM.plot mapping

We use a pickled protocol=2, which is compat binary.
"""
import psycopg2
import cPickle
from shapely.wkb import loads
import datetime

# Be annoying
print("Be sure to run this against Mesonet database and not laptop!")


def dump_cwa(fn):
    pgconn = psycopg2.connect(database='mesosite', host='iemdb',
                              user='nobody')
    cursor = pgconn.cursor()

    cursor.execute(""" SELECT wfo, ST_asEWKB(ST_Simplify(the_geom, 0.01))
    from cwa""")

    data = {}
    for row in cursor:
        data[row[0]] = dict(geom=loads(str(row[1])))
        # for polygon in geom:
        #    data[row[0]].append(np.asarray(polygon.exterior))

    f = open('../pyiem/data/%s' % (fn, ), 'wb')
    cPickle.dump(data, f, 2)
    f.close()


def dump_ugc(gtype, fn):
    pgconn = psycopg2.connect(database='postgis', host='iemdb',
                              user='nobody')
    cursor = pgconn.cursor()

    cursor.execute(""" SELECT ugc, wfo, ST_asEWKB(simple_geom) from ugcs
        WHERE end_ts is null and substr(ugc, 3, 1) = %s""", (gtype,))

    data = {}
    for row in cursor:
        data[row[0]] = dict(cwa=row[1][:3], geom=loads(str(row[2])))
        # for polygon in geom:
        #    data[row[0]].append(np.asarray(polygon.exterior))

    f = open('../pyiem/data/%s' % (fn, ), 'wb')
    cPickle.dump(data, f, 2)
    f.close()


def check_file(fn):
    sts = datetime.datetime.now()
    data = cPickle.load(open("../pyiem/data/%s" % (fn, ), 'rb'))
    ets = datetime.datetime.now()

    print (ets - sts).total_seconds(), len(data.keys()), fn

dump_ugc('C', 'ugcs_county.pickle')
dump_ugc('Z', 'ugcs_zone.pickle')
check_file('ugcs_county.pickle')
check_file('ugcs_zone.pickle')
dump_cwa("cwa.pickle")
check_file('cwa.pickle')
