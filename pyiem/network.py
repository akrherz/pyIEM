"""Network Table."""
from collections import OrderedDict

import psycopg2.extras
from pyiem.util import get_dbconn


class Table(object):
    """Our class"""

    def __init__(self, network, cursor=None, only_online=True):
        """A class representing a network(s) of IEM metadata

        Args:
          network (str or list): A network identifier used by the IEM, this can
            be either a string or a list of strings.
          cursor (dbcursor,optional): A database cursor to use for the query
          only_online (bool,otional): Should the listing of stations include
            only those that are currently flagged as online.
        """
        self.sts = OrderedDict()
        if network is None:
            return

        if cursor is None:
            dbconn = get_dbconn('mesosite', user='nobody')
            cursor = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        if isinstance(network, str):
            network = [network, ]
        online_extra = " and online " if only_online else ""

        cursor.execute("""
            WITH myattrs as (
                SELECT a.iemid, array_agg(attr) as attrs,
                array_agg(value) as attr_values from stations s JOIN
                station_attributes a on (s.iemid = a.iemid) WHERE
                s.network in %s GROUP by a.iemid
            )
            SELECT s.*, ST_x(geom) as lon, ST_y(geom) as lat,
            a.attrs, a.attr_values
            from stations s LEFT JOIN myattrs a
            on (s.iemid = a.iemid)
            WHERE network in %s """ + online_extra + """ ORDER by name ASC
            """, (tuple(network), tuple(network)))
        for row in cursor:
            self.sts[row['id']] = dict(row)
            self.sts[row['id']]['attributes'] = dict(
                zip(row['attrs'] or [], row['attr_values'] or []))
