"""Parsing of Storm Prediction Center SAW Product

This does not process the legacy SAW products that did not have LAT...LON
"""
import re
import datetime

from pyiem.nws.product import TextProduct
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.geometry import MultiPolygon

LATLON = re.compile(r"LAT\.\.\.LON\s+((?:[0-9]{8}\s+)+)")
NUM_RE = re.compile((r"WW ([0-9]*) (TEST)?\s?"
                     "(SEVERE TSTM|TORNADO|SEVERE THUNDERSTORM)"))
REPLACES_RE = re.compile("REPLACES WW ([0-9]*)")
DBTYPES = ['TOR', 'SVR']
TYPE2STRING = ['Tornado', 'Severe Thunderstorm']


class SAWException(Exception):
    """Custom local exception"""
    pass


class SAWProduct(TextProduct):
    """Class representing a SAW Product"""
    (TORNADO, SEVERE_THUNDERSTORM) = range(2)
    (ISSUES, CANCELS) = range(2)

    def __init__(self, text, utcnow=None):
        """Constructor

        Args:
          text (str): text to parse
        """
        TextProduct.__init__(self, text, utcnow=utcnow)
        self.saw = int(self.afos[3:].strip())
        self.action = self.find_action()
        self.geometry = self.find_polygon()
        self.ww_num = self.find_ww_num()
        (self.sts, self.ets) = self.find_time()
        self.ww_type = self.find_ww_type()
        self.affected_wfos = []

    def find_action(self):
        """Figure out if this is an issuance or cancells statement

        Return:
          (int): either ISSUES or CANCELS
        """
        if re.findall("CANCELLED", self.unixtext):
            return self.CANCELS
        return self.ISSUES

    def compute_wfos(self, txn):
        """Figure out who is impacted by this watch"""
        if self.geometry is None:
            return
        txn.execute("""
            SELECT distinct wfo from ugcs WHERE
             ST_Contains('SRID=4326;""" + self.geometry.wkt + """', geom)
             and end_ts is null
        """)
        for row in txn:
            self.affected_wfos.append(row[0])

    def sql(self, txn):
        """Do the necessary database work

        Args:
          (psycopg2.transaction): a database transaction
        """
        if self.action == self.ISSUES:
            # Delete any current entries
            txn.execute("""
                DELETE from watches WHERE num = %s and
               extract(year from issued) = %s
            """, (self.ww_num, self.sts.year))
            # Insert into the main watches table
            giswkt = 'SRID=4326;%s' % (MultiPolygon([self.geometry]).wkt,)
            sql = """
                INSERT into watches (sel, issued, expired, type, report,
                geom, num) VALUES(%s,%s,%s,%s,%s,%s, %s)
            """
            args = ('SEL%s' % (self.saw,), self.sts,
                    self.ets, DBTYPES[self.ww_type],
                    self.unixtext, giswkt, self.ww_num)
            txn.execute(sql, args)
            # Update the watches_current table
            sql = """
                UPDATE watches_current SET issued = %s, expired = %s,
                type = %s, report = %s, geom = %s, num = %s WHERE sel = %s
            """
            args = (self.sts,
                    self.ets, DBTYPES[self.ww_type],
                    self.unixtext, giswkt, self.ww_num,
                    'SEL%s' % (self.saw,))
            txn.execute(sql, args)
            # Is this a replacement?
            if REPLACES_RE.findall(self.unixtext):
                rnum = REPLACES_RE.findall(self.unixtext)[0][0]
                txn.execute("""
                    UPDATE watches SET expired  = %s
                    WHERE num = %s and extract(year from expired) = %s
                """, (self.valid, rnum, self.sts.year))
        elif self.action == self.CANCELS:
            for table in ('watches', 'watches_current'):
                txn.execute("""
                    UPDATE """ + table + """ SET expired = %s
                    WHERE num = %s and extract(year from expired) = %s
                """, (self.valid, self.ww_num, self.valid.year))
                if table == 'watches' and txn.rowcount != 0:
                    self.warnings.append(("Expiration of watch resulted in "
                                          "update of %s rows, instead of 1."
                                          ) % (txn.rowcount, ))

    def find_time(self):
        """Find the start and end valid time of this watch

        Returns:
          (datetime, datetime): representing the time of this watch
        """
        if self.action == self.CANCELS:
            return (None, None)
        sts = self.utcnow
        ets = self.utcnow
        tokens = re.findall(("([0-3][0-9])([0-2][0-9])([0-6][0-9])Z - "
                             "([0-3][0-9])([0-2][0-9])([0-6][0-9])Z"),
                            self.unixtext)

        day1 = int(tokens[0][0])
        hour1 = int(tokens[0][1])
        minute1 = int(tokens[0][2])
        day2 = int(tokens[0][3])
        hour2 = int(tokens[0][4])
        minute2 = int(tokens[0][5])

        sts = sts.replace(day=day1, hour=hour1, minute=minute1)
        ets = ets.replace(day=day2, hour=hour2, minute=minute2)

        # If we are near the end of the month and the day1 is 1, add 1 month
        if self.utcnow.day > 27 and day1 == 1:
            sts += datetime.timedelta(days=+35)
            sts = sts.replace(day=1)
        if self.utcnow.day > 27 and day2 == 1:
            ets += datetime.timedelta(days=+35)
            ets = ets.replace(day=1)
        return (sts, ets)

    def find_ww_num(self):
        """Find the Weather Watch Number

        Returns:
          (int): The Weather Watch Number
        """
        tokens = NUM_RE.findall(self.unixtext)
        if not tokens:
            raise SAWException("Could not locate Weather Watch Number")
        return int(tokens[0][0])

    def is_test(self):
        """Is this a test watch?

        Returns:
          boolean if this SAW is a test or not
        """
        tokens = NUM_RE.findall(self.unixtext)
        if not tokens:
            raise SAWException("Could not locate Weather Watch Number")
        return tokens[0][1] == 'TEST'

    def find_ww_type(self):
        """Find the Weather Watch Type

        Returns:
          (int): The Weather Watch Type
        """
        tokens = NUM_RE.findall(self.unixtext)
        if not tokens:
            raise SAWException("Could not locate Weather Watch Type")
        if tokens[0][2] == 'TORNADO':
            return self.TORNADO
        return self.SEVERE_THUNDERSTORM

    def find_polygon(self):
        """Search out the text for the LAT...LON polygon

        Returns:
          (str): Well Known Text (WKT) representation
        """
        if self.action == self.CANCELS:
            return
        tokens = LATLON.findall(self.unixtext.replace("\n", " "))
        if not tokens:
            raise SAWException('Could not parse LAT...LON geometry')
        pts = []
        for pair in tokens[0].split():
            lat = float(pair[:4]) / 100.0
            lon = 0 - float(pair[4:]) / 100.0
            if lon > -40:
                lon = lon - 100.0
            pts.append((lon, lat))
        return ShapelyPolygon(pts)

    def get_jabbers(self, uri, uri2=None):
        """Generate the jabber messages for this Product

        NOTE: In the past, the messages generated here have tripped twitter's
        spam logic, so we are careful to craft unique messages

        Args:
          uri (str): un-used in this context
        """
        res = []
        url = ("http://www.spc.noaa.gov/products/watch/%s/ww%04i.html"
               ) % (self.valid.year, self.ww_num)
        if self.action == self.CANCELS:
            plain = ("Storm Prediction Center cancels Weather Watch Number %s "
                     "%s") % (self.ww_num, url)
            html = ("<p>Storm Prediction Center cancels <a href=\"%s\">"
                    "Weather Watch Number %s</a></p>"
                    ) % (url, self.ww_num)
            res.append([plain, html, dict(channels='SPC')])
            # Now create templates
            plain = ("Storm Prediction Center cancels Weather Watch Number %s "
                     "for portions of %%s %s") % (self.ww_num, url)
            html = ("<p>Storm Prediction Center cancels <a href=\"%s\">"
                    "Weather Watch Number %s</a> for portions of %%s</p>"
                    ) % (url, self.ww_num)
        elif self.action == self.ISSUES:
            plain = ("SPC issues %s Watch %s till %sZ"
                     ) % (TYPE2STRING[self.ww_type], self.ww_num,
                          self.ets.strftime("%-H:%M"))
            html = ("<p>Storm Prediction Center issues "
                    "<a href=\"http://www.spc.noaa.gov/products/watch/"
                    "ww%04i.html\">%s Watch %s</a> "
                    "till %s UTC") % (int(self.ww_num),
                                      TYPE2STRING[self.ww_type], self.ww_num,
                                      self.ets.strftime("%-H:%M"))
            if REPLACES_RE.findall(self.unixtext):
                rtext = ("WW %s "
                         ) % (REPLACES_RE.findall(self.unixtext)[0][0].strip(),
                              )
                plain += ", new watch replaces " + rtext
                html += ", new watch replaces " + rtext

            plain2 = plain + url
            html2 = html + (" (<a href=\"%s?year=%s&amp;num=%s\">Watch "
                            "Quickview</a>)</p>"
                            ) % (uri, self.sts.year, self.ww_num)
            res.append([plain2, html2, dict(channels='SPC')])
            # Now create templates
            plain += " for portions of %%s %s" % (url,)
            html += (" for portions of %%s "
                     "(<a href=\"%s?year=%s&amp;num=%s\">Watch "
                     "Quickview</a>)</p>"
                     ) % (uri, self.sts.year, self.ww_num)

        for wfo in self.affected_wfos:
            res.append([
                plain % (wfo, ),
                html % (wfo, ),
                dict(channels=wfo)
                ])
        return res


def parser(text, utcnow=None):
    """parser of raw SPC SAW Text

    Args:
      text (str): the raw text to parse
      utcnow (datetime): the current datetime with timezone set!

    Returns:
      SAWProduct instance
    """
    return SAWProduct(text, utcnow=utcnow)
