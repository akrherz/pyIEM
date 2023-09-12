"""Parsing of Storm Prediction Center SEL Product."""
import re

from pyiem.models.sel import SELModel
from pyiem.nws.product import TextProduct

# The product format has been remarkably consistent over 16+ years!
WATCH_RE = re.compile(
    r"(?P<typ>SEVERE THUNDERSTORM|TORNADO)\s+WATCH\s+NUMBER\s+"
    r"(?P<num>\d\d\d\d|\d\d\d|\d\d|\d)",
    re.I,
)


def _parse_data(tp):
    """Fill out the data model."""
    # Only look in top 15 lines for the watch details
    meat = (" ".join(tp.unixtext.split("\n")[:15])).replace(" -", "")
    ws = WATCH_RE.search(meat).groupdict()
    return SELModel(
        typ="TOR" if ws["typ"].startswith("T") else "SVR",
        num=int(ws["num"]),
    )


class SELProduct(TextProduct):
    """Class representing a SEL Product"""

    def __init__(self, text, utcnow=None):
        """Constructor

        Args:
          text (str): text to parse
        """
        TextProduct.__init__(self, text, utcnow=utcnow)
        self.data = _parse_data(self)

    def is_test(self):
        """Is this a test product?"""
        return self.data.num > 9000 or self.unixtext.find("...TEST") > 0

    def sql(self, txn):
        """Do the necessary database work

        Args:
          (psycopg.transaction): a database transaction
        """
        # Don't do anything if this is not an issuance
        if self.unixtext.upper().find("HAS ISSUED A") < 0:
            return
        # First, check to see if we already have this num
        txn.execute(
            "SELECT num from watches where "
            "extract(year from issued at time zone 'UTC') = %s and num = %s "
            "and type = %s",
            (self.valid.year, self.data.num, self.data.typ),
        )
        if txn.rowcount == 0:
            # Insert an entry
            txn.execute(
                "INSERT into watches (num, issued, type) VALUES (%s, %s, %s)",
                (self.data.num, self.valid, self.data.typ),
            )
        # Now, update the data
        txn.execute(
            "UPDATE watches SET "
            "product_id_sel = %s "
            "WHERE extract(year from issued at time zone 'UTC') = %s "
            "and num = %s",
            (
                self.get_product_id(),
                self.valid.year,
                self.data.num,
            ),
        )


def parser(text, utcnow=None, _ugc_provider=None, _nwsli_provider=None):
    """Parse SPC SEL Product.

    Args:
      text (str): the raw text to parse
      utcnow (datetime): the current datetime with timezone set!

    Returns:
      WWPProduct instance
    """
    return SELProduct(text, utcnow=utcnow)
