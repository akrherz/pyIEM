"""Parser for the CF6 Product."""
import re
import calendar
from io import StringIO
import datetime

from pyiem.nws.product import TextProduct
from pyiem.reference import TRACE_VALUE
import pandas as pd

MONTH_RE = re.compile(r"^MONTH:\s+(?P<month>[A-Z]+)$", re.I)
MONTH_RE_NUM = re.compile(r"^MONTH:\s+(?P<month>[0-9]+)$", re.I)
YEAR_RE = re.compile(r"^YEAR:\s+(?P<year>[0-9]{4})$", re.I)
COL_WIDTHS = [2, 4, 4, 4, 4, 4, 4, 5, 5, 5, 5, 3, 4, 4, 5, 4, 7, 3, 4]
COL_NAMES = [
    "dy",
    "max",
    "min",
    "avg",
    "dep",
    "hdd",
    "cdd",
    "wtr",
    "snw",
    "dpth",
    "avg_spd",
    "max_spd",
    "avg_dir",
    "min_sun",
    "psbl_sun",
    "ss_sky",
    "wx",
    "gust_spd",
    "gust_dir",
]


class CF6Product(TextProduct):
    """
    Represents a CF6 Product
    """

    def __init__(
        self, text, utcnow=None, ugc_provider=None, nwsli_provider=None
    ):
        """constructor"""
        TextProduct.__init__(self, text, utcnow, ugc_provider, nwsli_provider)
        # Hold our parsing results as an array of dicts
        self.station = "%s%s" % (self.source[0], self.afos[3:])
        self.df = None
        self.parser()

    def parser(self):
        """Do the parsing we need to do!"""
        year = None
        month = None
        lines = self.unixtext.split("\n")
        # Arbitrary pick to eliminate products that are likely this:
        # Bad date: 12/2020. Last month in file is 11 / 2020 .
        if len(lines) < 8:
            return
        for line in lines:
            line = line.strip()
            if line.startswith("MONTH:"):
                m = MONTH_RE.match(line)
                if m:
                    month = m.groupdict()["month"]
                m = MONTH_RE_NUM.match(line)
                if m:
                    month = calendar.month_name[int(m.groupdict()["month"])]
            elif line.startswith("YEAR:"):
                m = YEAR_RE.match(line)
                if m:
                    year = m.groupdict()["year"]
            if year is not None and month is not None:
                break
        if year is None or month is None:
            raise ValueError("Failed to find required month and year values")
        day1 = datetime.datetime.strptime(
            "%s %s 1" % (year, month),
            "%Y %B %d" if len(month) > 3 else "%Y %b %d",
        )
        headercount = 0
        sio = StringIO()
        for line in self.unixtext.split("\n"):
            if line.strip().startswith("================"):
                headercount += 1
            if headercount != 2:
                continue
            if len(line) > 70:
                sio.write(line + "\n")
        sio.seek(0)
        df = pd.read_fwf(sio, widths=COL_WIDTHS)
        df = df.replace("T", TRACE_VALUE)
        df.columns = COL_NAMES
        for col in df.columns:
            if col == "wx":
                continue
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["valid"] = df["dy"].apply(
            lambda x: datetime.date(day1.year, day1.month, int(x))
        )
        self.df = df.set_index("valid")

    def sql(self, cursor):
        """Send the data to the database."""
        if self.df is None or self.df.empty:
            return
        # Prevent NaN numbers from going to the database.
        _df = self.df.where(pd.notnull(self.df), None)
        for valid, row in _df.iterrows():
            cursor.execute(
                "DELETE from cf6_data where station = %s and valid = %s",
                (self.station, valid),
            )
            cursor.execute(
                "INSERT into cf6_data(station, valid, product, high, low, "
                "avg_temp, dep_temp, hdd, cdd, precip, snow, snowd_12z, "
                "avg_smph, max_smph, avg_drct, minutes_sunshine, "
                "possible_sunshine, cloud_ss, wxcodes, gust_smph, gust_drct, "
                "updated) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                "%s, %s, %s, %s, %s, %s, %s, %s, now())",
                (
                    self.station,
                    valid,
                    self.get_product_id(),
                    row[COL_NAMES[1]],
                    row[COL_NAMES[2]],
                    row[COL_NAMES[3]],
                    row[COL_NAMES[4]],
                    row[COL_NAMES[5]],
                    row[COL_NAMES[6]],
                    row[COL_NAMES[7]],
                    row[COL_NAMES[8]],
                    row[COL_NAMES[9]],
                    row[COL_NAMES[10]],
                    row[COL_NAMES[11]],
                    row[COL_NAMES[12]],
                    row[COL_NAMES[13]],
                    row[COL_NAMES[14]],
                    row[COL_NAMES[15]],
                    row[COL_NAMES[16]],
                    row[COL_NAMES[17]],
                    row[COL_NAMES[18]],
                ),
            )


def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    """Provide back CF6 objects based on the parsing of this text"""
    return CF6Product(text, utcnow, ugc_provider, nwsli_provider)
