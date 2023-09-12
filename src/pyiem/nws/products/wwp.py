"""Parsing of Storm Prediction Center WWP Product."""
import re

from pyiem.models.wwp import WWPModel
from pyiem.nws.product import TextProduct

# The product format has been remarkably consistent over 16+ years!
WS_RE = re.compile(r"W(?P<typ>[ST])\s+(?P<num>\d\d\d\d)\s*P?D?S?\n")
PROB_RE = re.compile(
    r"PROB OF 2 OR MORE TORNADOES\s+:\s+(?P<tornadoes_2m>[\<\>\d]+)%\n"
    r"PROB OF 1 OR MORE STRONG /E?F2-E?F5/ TORNADOES\s+:"
    r"\s+(?P<tornadoes_1m_strong>[\<\>\d]+)%\n"
    r"PROB OF 10 OR MORE SEVERE WIND EVENTS\s+:\s+(?P<wind_10m>[\<\>\d]+)%\n"
    r"PROB OF 1 OR MORE WIND EVENTS >= 65 KNOTS\s+:"
    r"\s+(?P<wind_1m_65kt>[\<\>\d]+)%\n"
    r"PROB OF 10 OR MORE SEVERE HAIL EVENTS\s+:\s+(?P<hail_10m>[\<\>\d]+)%\n"
    r"PROB OF 1 OR MORE HAIL EVENTS >= 2 INCHES\s+:"
    r"\s+(?P<hail_1m_2inch>[\<\>\d]+)%\n"
    r"PROB OF 6 OR MORE COMBINED SEVERE HAIL/WIND EVENTS\s+:"
    r"\s+(?P<wind_hail_6m>[\<\>\d]+)%\n"
)
ATTR_RE = re.compile(
    r"MAX HAIL /INCHES/\s+:\s+(?P<max_hail_size>[\<\d\.]+)\n"
    r"MAX WIND GUSTS SURFACE /KNOTS/\s+:\s+(?P<max_wind_gust_knots>[\<\d]+)\n"
    r"MAX TOPS /X 100 FEET/\s+:\s+(?P<tops>\d*)\n"
    r"MEAN STORM MOTION VECTOR /DEGREES AND KNOTS/\s+:"
    r"\s+(?P<drct>\d\d\d)(?P<sknt>\d\d)\n"
    r"PARTICULARLY DANGEROUS SITUATION\s+:\s+(?P<is_pds>NO|YES)"
)


def _convprob(val):
    """Safe conversion."""
    # appears currently that these values are always static
    return int(val.replace(">", "").replace("<", ""))


def _parse_data(tp):
    """Fill out the data model."""
    ws = WS_RE.search(tp.unixtext).groupdict()
    prob = PROB_RE.search(tp.unixtext).groupdict()
    attr = ATTR_RE.search(tp.unixtext).groupdict()
    return WWPModel(
        typ="TOR" if ws["typ"] == "T" else "SVR",
        num=int(ws["num"]),
        tornadoes_2m=_convprob(prob["tornadoes_2m"]),
        tornadoes_1m_strong=_convprob(prob["tornadoes_1m_strong"]),
        wind_10m=_convprob(prob["wind_10m"]),
        wind_1m_65kt=_convprob(prob["wind_1m_65kt"]),
        hail_10m=_convprob(prob["hail_10m"]),
        hail_1m_2inch=_convprob(prob["hail_1m_2inch"]),
        hail_wind_6m=_convprob(prob["wind_hail_6m"]),
        max_hail_size=float(attr["max_hail_size"]),
        max_wind_gust_knots=int(attr["max_wind_gust_knots"]),
        max_tops_feet=int(attr["tops"]) * 100.0,
        storm_motion_drct=int(attr["drct"]),
        storm_motion_sknt=int(attr["sknt"]),
        is_pds=(attr["is_pds"] == "YES"),
    )


class WWPProduct(TextProduct):
    """Class representing a WWP Product"""

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
            "tornadoes_2m = %s, "
            "tornadoes_1m_strong = %s, "
            "wind_10m = %s, "
            "wind_1m_65kt = %s, "
            "hail_10m = %s, "
            "hail_1m_2inch = %s, "
            "hail_wind_6m = %s, "
            "max_hail_size = %s, "
            "max_wind_gust_knots = %s, "
            "max_tops_feet = %s, "
            "storm_motion_drct = %s, "
            "storm_motion_sknt = %s, "
            "is_pds = %s, "
            "product_id_wwp = %s "
            "WHERE extract(year from issued at time zone 'UTC') = %s "
            "and num = %s",
            (
                self.data.tornadoes_2m,
                self.data.tornadoes_1m_strong,
                self.data.wind_10m,
                self.data.wind_1m_65kt,
                self.data.hail_10m,
                self.data.hail_1m_2inch,
                self.data.hail_wind_6m,
                self.data.max_hail_size,
                self.data.max_wind_gust_knots,
                self.data.max_tops_feet,
                self.data.storm_motion_drct,
                self.data.storm_motion_sknt,
                self.data.is_pds,
                self.get_product_id(),
                self.valid.year,
                self.data.num,
            ),
        )


def parser(text, utcnow=None, _ugc_provider=None, _nwsli_provider=None):
    """Parse SPC WWP Product.

    Args:
      text (str): the raw text to parse
      utcnow (datetime): the current datetime with timezone set!

    Returns:
      WWPProduct instance
    """
    return WWPProduct(text, utcnow=utcnow)
