"""Parsing of Storm Prediction Center SAW Product """
from pyiem.nws.product import TextProduct
from shapely.geometry import Polygon as ShapelyPolygon
import re
import datetime
LATLON = re.compile(r"LAT\.\.\.LON\s+((?:[0-9]{8}\s+)+)")


class SAWException(Exception):
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

    def find_action(self):
        """Figure out if this is an issuance or cancells statement

        Returns:
          (int): either ISSUES or CANCELS
        """
        if len(re.findall("CANCELLED", self.unixtext)) > 0:
            return self.CANCELS
        return self.ISSUES

    def sql(self, txn):
        """Do the necessary database work

        Args:
          (psycopg2.transaction): a database transaction
        """
        if self.action == self.CANCELS:
            txn.execute("""
                UPDATE watches SET expired = %s WHERE num = %s and
                extract(year from expired) = %s
              """, (self.valid, self.ww_num, self.sts.year))
            if txn.rowcount != 0:
                self.warnings.append(("Expiration of watch resulted in "
                                      "update of %s rows, instead of 1."
                                      ) % (txn.rowcount, ))
            return

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
        myre = "WW ([0-9]*) (TEST)? ?(SEVERE TSTM|TORNADO|SEVERE THUNDERSTORM)"
        tokens = re.findall(myre, self.unixtext)
        if len(tokens) == 0:
            raise SAWException("Could not locate Weather Watch Number")
        return int(tokens[0][0])

    def find_ww_type(self):
        """Find the Weather Watch Type

        Returns:
          (int): The Weather Watch Type
        """
        myre = "WW ([0-9]*) (TEST)? ?(SEVERE TSTM|TORNADO|SEVERE THUNDERSTORM)"
        tokens = re.findall(myre, self.unixtext)
        if len(tokens) == 0:
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
        if len(tokens) == 0:
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

        Args:
          uri (str): un-used in this context
        """
        plain = ""
        html = ""
        xtra = dict()
        url = ("http://www.spc.noaa.gov/products/watch/%s/ww%04i.html"
               ) % (self.valid.year, self.ww_num)
        if self.action == self.CANCELS:
            plain = ("Storm Prediction Center cancels Weather Watch Number %s "
                     "%s") % (self.ww_num, url)
            html = ("<p>Storm Prediction Center cancels <a href=\"%s\">"
                    "Weather Watch Number %s</a></p>"
                    ) % (url, self.ww_num)

        return [[plain, html, xtra]]


def parser(text, utcnow=None):
    """parser of raw SPC SAW Text

    Args:
      text (str): the raw text to parse
      utcnow (datetime): the current datetime with timezone set!

    Returns:
      SAWProduct instance
    """
    return SAWProduct(text, utcnow=utcnow)
