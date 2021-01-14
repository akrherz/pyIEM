"""Serialization of geometries for use in pyIEM.plot mapping

We use a pickled protocol=2, which is compat binary.
"""
import datetime

import pickle
from shapely.wkb import loads
from pyiem.util import get_dbconn

PATH = "../src/pyiem/data"
# Be annoying
print("Be sure to run this against Mesonet database and not laptop!")


def dump_states(fn):
    """states."""
    pgconn = get_dbconn("postgis", user="nobody")
    cursor = pgconn.cursor()

    cursor.execute(
        """ SELECT state_abbr,
    ST_Simplify(the_geom, 0.01),
    ST_x(ST_Centroid(the_geom)), ST_Y(ST_Centroid(the_geom)) from states"""
    )

    data = {}
    for row in cursor:
        data[row[0]] = dict(
            geom=loads(row[1], hex=True), lon=row[2], lat=row[3]
        )
        # for polygon in geom:
        #    data[row[0]].append(np.asarray(polygon.exterior))

    with open("%s/%s" % (PATH, fn), "wb") as f:
        pickle.dump(data, f, 2)


def dump_climdiv(fn):
    """climate divisions."""
    pgconn = get_dbconn("postgis", user="nobody")
    cursor = pgconn.cursor()

    cursor.execute(
        """ SELECT iemid, geom,
    ST_x(ST_Centroid(geom)), ST_Y(ST_Centroid(geom))
    from climdiv"""
    )

    data = {}
    for row in cursor:
        data[row[0]] = dict(
            geom=loads(row[1], hex=True), lon=row[2], lat=row[3]
        )
        # for polygon in geom:
        #    data[row[0]].append(np.asarray(polygon.exterior))

    with open("%s/%s" % (PATH, fn), "wb") as f:
        pickle.dump(data, f, 2)


def dump_cwa(fn):
    """WFOs."""
    pgconn = get_dbconn("postgis", user="nobody")
    cursor = pgconn.cursor()

    cursor.execute(
        """ SELECT wfo, ST_Simplify(the_geom, 0.01),
    ST_x(ST_Centroid(the_geom)), ST_Y(ST_Centroid(the_geom)), region
    from cwa"""
    )

    data = {}
    for row in cursor:
        data[row[0]] = dict(
            geom=loads(row[1], hex=True), lon=row[2], lat=row[3], region=row[4]
        )
    with open("%s/%s" % (PATH, fn), "wb") as f:
        pickle.dump(data, f, 2)


def dump_iowawfo(fn):
    """ A region with the Iowa WFOs"""
    pgconn = get_dbconn("postgis", user="nobody")
    cursor = pgconn.cursor()

    cursor.execute(
        """ SELECT ST_Simplify(ST_Union(the_geom), 0.01)
        from cwa
        WHERE wfo in ('DMX', 'ARX', 'DVN', 'OAX', 'FSD')"""
    )
    row = cursor.fetchone()

    geo = loads(row[0], hex=True)
    data = dict()
    data["iowawfo"] = dict(geom=geo, lon=geo.centroid.x, lat=geo.centroid.y)
    with open("%s/%s" % (PATH, fn), "wb") as f:
        pickle.dump(data, f, 2)


def dump_ugc(gtype, fn):
    """UGCS."""
    pgconn = get_dbconn("postgis", user="nobody")
    cursor = pgconn.cursor()

    # We want UGCs valid for the time of running this script
    cursor.execute(
        "SELECT ugc, wfo, simple_geom, ST_x(centroid), ST_Y(centroid) "
        "from ugcs WHERE begin_ts < now() and "
        "(end_ts is null or end_ts > now()) and substr(ugc, 3, 1) = %s",
        (gtype,),
    )

    data = {}
    for row in cursor:
        data[row[0]] = dict(
            cwa=row[1][:3],
            geom=loads(row[2], hex=True),
            lon=row[3],
            lat=row[4],
        )
        # for polygon in geom:
        #    data[row[0]].append(np.asarray(polygon.exterior))

    with open("%s/%s" % (PATH, fn), "wb") as f:
        pickle.dump(data, f, 2)


def check_file(fn):
    """regression check."""
    sts = datetime.datetime.now()
    data = pickle.load(open("%s/%s" % (PATH, fn), "rb"))
    ets = datetime.datetime.now()

    print(
        "runtime: %.5fs, entries: %s, fn: %s"
        % ((ets - sts).total_seconds(), len(data.keys()), fn)
    )


def main():
    """Go Main"""
    dump_iowawfo("iowawfo.pickle")
    dump_ugc("C", "ugcs_county.pickle")
    dump_ugc("Z", "ugcs_zone.pickle")
    check_file("ugcs_county.pickle")
    check_file("ugcs_zone.pickle")
    dump_cwa("cwa.pickle")
    check_file("cwa.pickle")
    dump_climdiv("climdiv.pickle")
    check_file("climdiv.pickle")
    dump_states("us_states.pickle")
    check_file("us_states.pickle")


if __name__ == "__main__":
    main()
