"""Parsing of Flash Flood Guidances

NWS Discontinued 30 Sep 2018
https://www.weather.gov/media/notification/pdfs/pns18-13disc_county_ffg.pdf
"""
import re
from datetime import timezone, datetime

import pandas as pd
from pyiem.nws.product import TextProduct

SHEFRE = re.compile(
    (
        r"\.B (?P<src>[A-Z]{3}) (?P<date>[0-9]{6,8}) Z "
        r"DH(?P<hh>[0-9]{2})/DC(?P<valid>[0-9]{10,12}) "
        r"/DUE/PPHCF/PPTCF/PPQCF"
    )
)
DATARE = re.compile(
    (
        r"^(?P<ugc>[A-Z0-9]{6})\s+(?P<hour01>[0-9\.]+)/\s+"
        r"(?P<hour03>[0-9\.]+)/\s+(?P<hour06>[0-9\.]+)\s*"
        r"/?\s*(?P<hour12>[0-9\.]+)?\s*"
        r"/?\s*(?P<hour24>[0-9\.]+)?\s*"
    ),
    re.M,
)


def safe(val):
    """Safe conversion to float"""
    if val is None:
        return None
    return float(val)


class FFGProduct(TextProduct):
    """Class representing a FFG Product"""

    def __init__(self, text, utcnow=None):
        """Constructor

        Args:
          text (str): text to parse
        """
        TextProduct.__init__(self, text, utcnow=utcnow)
        self.data = None
        self.issue = None
        self.do_parsing()

    def do_parsing(self):
        """Process this file and save data"""
        shef = SHEFRE.search(self.text)
        if shef is None:
            self.warnings.append("Failed to find SHEF variable!")
            return
        group = shef.groupdict()
        self.issue = datetime.strptime(group["date"][-6:], "%y%m%d").replace(
            tzinfo=timezone.utc
        )
        self.issue = self.issue.replace(hour=(int(group["hh"]) % 24))
        dc = datetime.strptime(group["valid"][-10:], "%y%m%d%H%M").replace(
            tzinfo=timezone.utc
        )
        # Emailed KTUA about this on 17 Apr 2017
        if (
            abs((self.issue - dc).total_seconds()) > (12 * 3600.0)
            and self.source != "KTUA"
        ):
            self.warnings.append(
                "Product has large delta between DC: "
                f"{dc.strftime('%Y-%m-%d %H:%MZ')} and "
                f"SHEF Date: {self.issue.strftime('%Y-%m-%d %H:%MZ')}"
            )
        rows = []
        pos1 = self.unixtext.find(".B ")
        pos2 = self.unixtext.find(".END")
        if pos1 == -1 or pos2 == -1:
            return
        for match in DATARE.finditer(self.unixtext[pos1:pos2]):
            group = match.groupdict()
            rows.append(
                dict(
                    ugc=group["ugc"],
                    hour01=safe(group["hour01"]),
                    hour03=safe(group["hour03"]),
                    hour06=safe(group["hour06"]),
                    hour12=safe(group["hour12"]),
                    hour24=safe(group["hour24"]),
                )
            )
        self.data = pd.DataFrame(rows)

    def sql(self, txn):
        """Do the necessary database work

        Args:
          (psycopg2.transaction): a database transaction
        """
        if self.data is None:
            self.warnings.append("sql() was called with no data parsed!")
            return
        table = "ffg_%s" % (self.issue.year,)
        for _, row in self.data.iterrows():
            txn.execute(
                f"INSERT into {table} (ugc, valid, hour01, hour03, hour06, "
                "hour12, hour24) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    row["ugc"],
                    self.issue,
                    row["hour01"],
                    row["hour03"],
                    row["hour06"],
                    row["hour12"],
                    row["hour24"],
                ),
            )


def parser(text, utcnow=None):
    """parser of raw SPC SAW Text

    Args:
      text (str): the raw text to parse
      utcnow (datetime): the current datetime with timezone set!

    Returns:
      SAWProduct instance
    """
    return FFGProduct(text, utcnow=utcnow)
