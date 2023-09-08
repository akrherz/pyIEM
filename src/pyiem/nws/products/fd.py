"""Parser for the FD (Temp Wind Aloft Forecasts)."""
import datetime
import re

import numpy as np
import pandas as pd

from pyiem.nws.product import TextProduct

BASED_ON_RE = re.compile("^DATA BASED ON ([0-9]{6})Z", re.M)
VALID_RE = re.compile("^VALID ([0-9]{6})Z", re.M)


def parse_encoding(text):
    """Convert the encoded text into drct, sknt, tmpc."""
    tmpc = np.nan
    drct = np.nan
    sknt = np.nan
    if len(text) not in [4, 6, 7]:
        return drct, sknt, tmpc
    drct = int(text[:2]) * 10
    sknt = int(text[2:4])
    # NWSI 10-812 section 6
    if text.startswith("9900"):
        drct = 0
        sknt = 0
    if len(text) > 4:
        tmpc = int(text[-2:])
        if text[4] == "-" or len(text) == 6:
            tmpc *= -1
    # Fun
    if drct >= 500:
        drct -= 500
        sknt += 100
    return drct, sknt, tmpc


def compute_time(valid, tokens):
    """Figure out the timestamp of interest here."""
    dd, hh, mi = int(tokens[0][:2]), int(tokens[0][2:4]), int(tokens[0][4:6])
    valid2 = valid.replace(hour=hh, minute=mi)
    if valid.day > 25 and dd < 5:
        valid2 += datetime.timedelta(days=10)
    if valid.day < 5 and dd > 25:
        valid2 -= datetime.timedelta(days=10)
    valid2 = valid2.replace(day=dd)
    # In theory, we should not be far apart
    if abs((valid2 - valid).days) > 5:
        raise ValueError(f"Timestamp {valid2} too far from {valid}")
    return valid2


def make4(station, afos):
    """Make this 3 character station, 4!"""
    ccode = afos[3:5]
    if ccode == "US":
        return f"K{station}"
    if ccode == "CN":
        return f"C{station}"
    return f"P{station}"


class FDProduct(TextProduct):
    """
    Represents a FD Product
    """

    def __init__(
        self, text, utcnow=None, ugc_provider=None, nwsli_provider=None
    ):
        """constructor"""
        text = text.replace("\x1e", "")  # Aviation Control
        TextProduct.__init__(self, text, utcnow, ugc_provider, nwsli_provider)
        self.df = None
        self.obtime = compute_time(
            self.valid, BASED_ON_RE.findall(self.unixtext)
        )
        self.ftime = compute_time(self.valid, VALID_RE.findall(self.unixtext))
        self.parser()

    def parser(self):
        """Do the parsing we need to do!"""
        rows = []
        levels = []
        for line in self.unixtext.split("\n"):
            if line.startswith("FT ") and not rows:
                levels = line[3:].strip().split()
                continue
            if not levels:
                continue
            if len(line) < 10:
                continue
            tokens = line.strip().split(" ")
            data = {"station": make4(tokens[0], self.afos)}
            # fill right to left
            for i in range(-1, -1 - len(levels), -1):
                (
                    data[f"drct{levels[i]}"],
                    data[f"sknt{levels[i]}"],
                    data[f"tmpc{levels[i]}"],
                ) = parse_encoding(tokens[i])
            rows.append(data)
        if rows:
            self.df = pd.DataFrame(rows).set_index("station")

    def sql(self, cursor):
        """Send the data to the database."""
        if self.df is None or self.df.empty:
            return
        # Prevent NaN numbers from going to the database.
        sql = ", ".join([f"{c} = %s" for c in self.df.columns])
        for row in self.df.itertuples(index=True):
            # Need upsert as data is split over products
            cursor.execute(
                "SELECT station from alldata_tempwind_aloft "
                "where ftime = %s and station = %s and obtime = %s",
                (self.ftime, row[0], self.obtime),
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    "INSERT into alldata_tempwind_aloft"
                    "(ftime, station, obtime) VALUES (%s, %s, %s)",
                    (self.ftime, row[0], self.obtime),
                )

            # np.nan + float64 columns + psycopg life is fun here
            def _fint(val):
                """Force an int."""
                if np.isnan(val):
                    return None
                return int(val)

            cursor.execute(
                f"""
                UPDATE alldata_tempwind_aloft SET {sql}
                WHERE ftime = %s and station = %s and obtime = %s
                """,
                (
                    *[_fint(x) for x in row[1:]],
                    self.ftime,
                    row[0],
                    self.obtime,
                ),
            )


def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    """Provide back FD objects based on the parsing of this text"""
    return FDProduct(text, utcnow, ugc_provider, nwsli_provider)
