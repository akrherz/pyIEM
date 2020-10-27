"""Parsing NESDIS Satellite Cloud Product (SCP)."""
import re
from datetime import timedelta
from collections import namedtuple

from pyiem.nws.product import TextProduct

SCP = namedtuple(
    "SCP", ["station", "valid", "mid", "high", "cldtop1", "cldtop2", "eca"]
)
LINEFMT = re.compile(r"^([A-Z0-9]){3,5}\s+[0-3][0-9]/[0-2][0-9][0-5][0-9]\s")


def _to_str(val):
    """Safe conversion."""
    if val.strip() == "":
        return None
    return val.strip()


def _to_int(val, multi=100.0):
    """Safe conversion."""
    if val.strip() == "":
        return None
    try:
        return int(val) * multi
    except ValueError:
        return None


def _processor(textprod):
    """Parse out what we can find in the text product."""
    res = []
    for line in textprod.unixtext.split("\n"):
        if not LINEFMT.match(line):
            continue
        if line[9] != "/":
            continue
        station = line[:5].strip()
        da = int(line[7:9])
        hr = int(line[10:12])
        mi = int(line[12:14])
        valid = textprod.valid
        if da != textprod.valid.day:
            # Yesterday
            valid = textprod.valid - timedelta(days=1)
        valid = valid.replace(day=da, hour=hr, minute=mi)
        mid = _to_str(line[17:20])
        high = _to_str(line[23:26])
        cldtop1 = _to_int(line[28:31])
        cldtop2 = _to_int(line[32:35])
        eca = _to_int(line[37:40], 1)
        res.append(
            SCP._make([station, valid, mid, high, cldtop1, cldtop2, eca])
        )

    return res


class SCPProduct(TextProduct):
    """Class representing a SCP Product"""

    def __init__(self, text, utcnow=None):
        """Constructor

        Args:
          text (str): text to parse
        """
        TextProduct.__init__(self, text, utcnow=utcnow)
        self.data = _processor(self)

    def sql(self, txn):
        """Do the necessary database work

        Args:
          (psycopg2.transaction): a database transaction
        """
        inserts = 0
        for ob in self.data:
            inserts += 1
            txn.execute(
                "INSERT into scp_alldata(station, valid, mid, high, cldtop1, "
                "cldtop2, eca, source) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    ob.station,
                    ob.valid,
                    ob.mid,
                    ob.high,
                    ob.cldtop1,
                    ob.cldtop2,
                    ob.eca,
                    self.afos[-1],
                ),
            )
        return inserts


def parser(text, utcnow=None):
    """parser of raw SCP Text.

    Args:
      text (str): the raw text to parse
      utcnow (datetime): the current datetime with timezone set!

    Returns:
      SCPProduct instance
    """
    return SCPProduct(text, utcnow=utcnow)
