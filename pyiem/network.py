import psycopg2.extras


class Table(object):

    def __init__(self, network):
        """A class representing a network(s) of IEM metadata

        Args:
          network (str or list): A network identifier used by the IEM, this can
            be either a string or a list of strings.
        """
        self.sts = {}
        if network is None:
            return

        dbconn = psycopg2.connect(database='mesosite', host='iemdb',
                                  user='nobody')
        cursor = dbconn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        if isinstance(network, str):
            network = [network, ]
        for n in network:
            cursor.execute("""
                SELECT *, ST_x(geom) as lon, ST_y(geom) as lat
                from stations WHERE network = %s ORDER by name ASC
                """, (n,))
            for row in cursor:
                self.sts[row['id']] = dict()
                for key in row.keys():
                    self.sts[row['id']][key] = row[key]
        cursor.close()
        dbconn.close()
