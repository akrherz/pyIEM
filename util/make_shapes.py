"""Serialization of geometries for use in pyIEM.plot mapping

We use a pickled protocol=2, which is compat binary.
"""
import psycopg2
import cPickle
from shapely.wkb import loads
import datetime

# Be annoying
print("Be sure to run this against Mesonet database and not laptop!")


def dump_states(fn):
    pgconn = psycopg2.connect(database='postgis', host='iemdb',
                              user='nobody')
    cursor = pgconn.cursor()

    cursor.execute(""" SELECT state_abbr,
    ST_asEWKB(ST_Simplify(the_geom, 0.01)),
    ST_x(ST_Centroid(the_geom)), ST_Y(ST_Centroid(the_geom)) from states""")

    data = {}
    for row in cursor:
        data[row[0]] = dict(geom=loads(str(row[1])), lon=row[2], lat=row[3])
        # for polygon in geom:
        #    data[row[0]].append(np.asarray(polygon.exterior))

    f = open('../pyiem/data/%s' % (fn, ), 'wb')
    cPickle.dump(data, f, 2)
    f.close()


def dump_climdiv(fn):
    pgconn = psycopg2.connect(database='postgis', host='iemdb',
                              user='nobody')
    cursor = pgconn.cursor()

    cursor.execute(""" SELECT iemid, ST_asEWKB(geom),
    ST_x(ST_Centroid(geom)), ST_Y(ST_Centroid(geom))
    from climdiv""")

    data = {}
    for row in cursor:
        data[row[0]] = dict(geom=loads(str(row[1])), lon=row[2], lat=row[3])
        # for polygon in geom:
        #    data[row[0]].append(np.asarray(polygon.exterior))

    f = open('../pyiem/data/%s' % (fn, ), 'wb')
    cPickle.dump(data, f, 2)
    f.close()


def dump_cwa(fn):
    pgconn = psycopg2.connect(database='mesosite', host='iemdb',
                              user='nobody')
    cursor = pgconn.cursor()

    cursor.execute(""" SELECT wfo, ST_asEWKB(ST_Simplify(geom, 0.01)),
    ST_x(ST_Centroid(geom)), ST_Y(ST_Centroid(geom)), region
    from cwa""")

    data = {}
    for row in cursor:
        data[row[0]] = dict(geom=loads(str(row[1])), lon=row[2], lat=row[3],
                            region=row[4])
    f = open('../pyiem/data/%s' % (fn, ), 'wb')
    cPickle.dump(data, f, 2)
    f.close()


def dump_iowawfo(fn):
    """ A region with the Iowa WFOs"""
    pgconn = psycopg2.connect(database='postgis', host='iemdb',
                              user='nobody')
    cursor = pgconn.cursor()

    cursor.execute(""" SELECT ST_asEWKB(ST_Simplify(ST_Union(the_geom), 0.01))
        from cwa
        WHERE wfo in ('DMX', 'ARX', 'DVN', 'OAX', 'FSD')""")
    row = cursor.fetchone()

    geo = loads(str(row[0]))
    data = dict()
    data['iowawfo'] = dict(geom=geo,
                           lon=geo.centroid.x, lat=geo.centroid.y)
    f = open('../pyiem/data/%s' % (fn, ), 'wb')
    cPickle.dump(data, f, 2)
    f.close()


def dump_ugc(gtype, fn):
    pgconn = psycopg2.connect(database='postgis', host='iemdb',
                              user='nobody')
    cursor = pgconn.cursor()

    cursor.execute(""" SELECT ugc, wfo, ST_asEWKB(simple_geom),
        ST_x(centroid), ST_Y(centroid) from ugcs
        WHERE end_ts is null and substr(ugc, 3, 1) = %s""", (gtype,))

    data = {}
    for row in cursor:
        data[row[0]] = dict(cwa=row[1][:3], geom=loads(str(row[2])),
                            lon=row[3], lat=row[4])
        # for polygon in geom:
        #    data[row[0]].append(np.asarray(polygon.exterior))

    f = open('../pyiem/data/%s' % (fn, ), 'wb')
    cPickle.dump(data, f, 2)
    f.close()


def check_file(fn):
    sts = datetime.datetime.now()
    data = cPickle.load(open("../pyiem/data/%s" % (fn, ), 'rb'))
    ets = datetime.datetime.now()

    print("runtime: %.5fs, entries: %s, fn: %s" % (
                (ets - sts).total_seconds(), len(data.keys()), fn))

dump_iowawfo('iowawfo.pickle')
dump_ugc('C', 'ugcs_county.pickle')
dump_ugc('Z', 'ugcs_zone.pickle')
check_file('ugcs_county.pickle')
check_file('ugcs_zone.pickle')
dump_cwa("cwa.pickle")
check_file('cwa.pickle')
dump_climdiv("climdiv.pickle")
check_file("climdiv.pickle")
dump_states('us_states.pickle')
check_file('us_states.pickle')
