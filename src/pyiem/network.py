"""Network Table."""

from collections import OrderedDict

from pyiem.database import get_dbconnc


class Table:
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
            dbconn, _cursor = get_dbconnc("mesosite")
        else:
            dbconn, _cursor = None, cursor
        if isinstance(network, str):
            network = [network]
        if isinstance(network, tuple):
            network = list(network)
        online_extra = " and online " if only_online else ""

        _cursor.execute(
            f"""
            WITH myattrs as (
                SELECT a.iemid, array_agg(attr) as attrs,
                array_agg(value) as attr_values from stations s JOIN
                station_attributes a on (s.iemid = a.iemid) WHERE
                s.network = any(%s) GROUP by a.iemid
            ), mythreading as (
                SELECT a.iemid, array_agg(source_iemid) as threading_sources,
                array_agg(begin_date) as threading_begin_dates,
                array_agg(coalesce(end_date, 'TOMORROW'::date))
                  as threading_end_dates
                from stations s JOIN
                station_threading a on (s.iemid = a.iemid) WHERE
                s.network = any(%s) GROUP by a.iemid
            )
            SELECT s.*, ST_x(geom) as lon, ST_y(geom) as lat,
            a.attrs, a.attr_values, m.threading_sources,
            m.threading_begin_dates, m.threading_end_dates
            from stations s
            LEFT JOIN myattrs a on (s.iemid = a.iemid)
            LEFT JOIN mythreading m on (s.iemid = m.iemid)
            WHERE network = any(%s) {online_extra} ORDER by name ASC
            """,
            (network, network, network),
        )
        for row in _cursor:
            self.sts[row["id"]] = dict(row)
            self.sts[row["id"]]["attributes"] = dict(
                zip(row["attrs"] or [], row["attr_values"] or [], strict=False)
            )
            td = self.sts[row["id"]].setdefault("threading", [])
            for i, s, e in zip(
                row["threading_sources"] or [],
                row["threading_begin_dates"] or [],
                row["threading_end_dates"] or [],
                strict=False,
            ):
                td.append({"iemid": i, "begin_date": s, "end_date": e})
        if cursor is None:
            dbconn.close()

    def get_threading_id(self, sid, valid) -> str:
        """Return a station identifier (not iemid) based on threading.

        Lookup what the threaded station identifier is based on this given
        timestamp/date.

        Args:
          sid (str): station identifier to check threading for.
          valid (datetime.date): lookup for comparison.
        """
        entry = self.sts.get(sid)
        if entry is None or not entry["threading"]:
            return None
        for tinfo in entry["threading"]:
            if valid < tinfo["begin_date"] or valid >= tinfo["end_date"]:
                continue
            return self.get_id_by_key("iemid", tinfo["iemid"])
        return None

    def get_id_by_key(self, key, value) -> str:
        """Find a station id by a given attribute = value.

        Args:
          key (str): attribute to lookup.
          value (mixed): value to compare against

        Returns:
          station_id
        """
        for sid in self.sts:
            if self.sts[sid].get(key) == value:
                return sid
        return None
