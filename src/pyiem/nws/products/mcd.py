"""
Supports parsing of Storm Prediction Center's MCD and
parsing of Weather Prediction Center's MPD
"""

import re
from datetime import timedelta, timezone

from shapely.geometry import Polygon as ShapelyPolygon

from pyiem.exceptions import MCDException
from pyiem.models.mcd import MostProbableTags
from pyiem.nws.product import TextProduct
from pyiem.reference import TWEET_CHARS, TWEET_URL_CHARS
from pyiem.util import LOG, html_escape

CORRECTION = re.compile(r"SPC\s+MCD\s+([0-9]{6})\s+COR", re.IGNORECASE)
LATLON = re.compile(r"LAT\.\.\.LON\s+((?:[0-9]{8}\s+)+)")
DISCUSSIONNUM = re.compile(
    r"MESOSCALE (?:PRECIPITATION )?DISCUSSION\s+([0-9]+)", re.IGNORECASE
)
WATCH_PROB = re.compile(
    r"PROBABILITY OF WATCH ISSUANCE\s?\.\.\.\s?([0-9]+) PERCENT", re.IGNORECASE
)
VALID_TIME = re.compile(r"VALID\s+([0-9]{6})Z?\s?-\s?([0-9]{6})Z?", re.I)
CONCERNING = re.compile(r"CONCERNING\s?\.\.\.(.*?)\n\n", re.I)
MOST_PROB_TAGS = re.compile(
    r"^MOST PROBABLE PEAK (TORNADO INTENSITY|WIND GUST|HAIL SIZE)\s*"
    r"\.\.\.\s*(.*)$",
    re.MULTILINE,
)


class MCDProduct(TextProduct):
    """
    Represents a Storm Prediction Center Mesoscale Convective Discussion
    """

    def __init__(
        self, text, utcnow=None, ugc_provider=None, nwsli_provider=None
    ):
        """constructor"""
        super().__init__(text, utcnow, ugc_provider, nwsli_provider)
        self.geometry = self.parse_geometry()
        self.discussion_num = self.parse_discussion_num()
        self.attn_wfo = self.parse_attn_wfo()
        if not self.attn_wfo:
            raise MCDException("Could not parse attention WFOs")
        self.attn_rfc = self.parse_attn_rfc()
        self.areas_affected = self.parse_areas_affected()
        self.concerning = self.parse_concerning()
        self.watch_prob = self.find_watch_probability()
        self.most_prob_tags: MostProbableTags = self.parse_most_prob_tags()
        self.sts, self.ets = self.find_valid_times()
        self.is_correction = self.parse_correction()
        self.cwsus = []

    def parse_most_prob_tags(self) -> MostProbableTags:
        """Glean what we can for these tags."""
        tokens = MOST_PROB_TAGS.findall(self.unixtext)
        hail = None
        tornado = None
        gust = None
        for token in tokens:
            if token[0] == "HAIL SIZE":
                hail = token[1].strip()
            elif token[0] == "TORNADO INTENSITY":
                tornado = token[1].strip()
            elif token[0] == "WIND GUST":
                gust = token[1].strip()
        return MostProbableTags(hail=hail, tornado=tornado, gust=gust)

    def parse_correction(self) -> bool:
        """Look for the correction flag."""
        return bool(CORRECTION.search(self.unixtext))

    def find_valid_times(self):
        """Figure out when this product is valid for"""
        tokens = VALID_TIME.findall(self.unixtext)
        if not tokens:
            self.warnings.append("failed to find VALID...")
            return None, None
        day1 = int(tokens[0][0][:2])
        hour1 = int(tokens[0][0][2:4])
        min1 = int(tokens[0][0][4:])
        day2 = int(tokens[0][1][:2])
        hour2 = int(tokens[0][1][2:4])
        min2 = int(tokens[0][1][4:])
        issue = self.valid.replace(day=day1, hour=hour1, minute=min1)
        expire = self.valid.replace(day=day2, hour=hour2, minute=min2)
        if day1 < self.valid.day and day1 == 1:
            issue = self.valid + timedelta(days=25)
            issue = issue.replace(day=day1, hour=hour1, minute=min1)
        if day2 < self.valid.day and day2 == 1:
            expire = self.valid + timedelta(days=25)
            expire = expire.replace(day=day2, hour=hour2, minute=min2)

        return (
            issue.replace(tzinfo=timezone.utc),
            expire.replace(tzinfo=timezone.utc),
        )

    def find_watch_probability(self):
        """Find the probability of watch issuance for SPC MCD"""
        tokens = WATCH_PROB.findall(self.unixtext.replace("\n", ""))
        if not tokens:
            return None
        return int(tokens[0])

    def get_prob_extra(self):
        """Return some text."""
        prob_extra = ""
        if self.watch_prob is not None:
            prob_extra = f" [watch prob: {self.watch_prob:.0f}%]"
        most_probs = []
        if self.most_prob_tags.tornado:
            most_probs.append(f"Tornado: {self.most_prob_tags.tornado}")
        if self.most_prob_tags.hail:
            most_probs.append(f"Hail: {self.most_prob_tags.hail}")
        if self.most_prob_tags.gust:
            most_probs.append(f"Gust: {self.most_prob_tags.gust}")
        if most_probs:
            prob_extra += f" [Most Prob: {', '.join(most_probs)}]"
        return prob_extra

    def tweet(self):
        """Return twitter message"""
        charsleft = TWEET_CHARS - TWEET_URL_CHARS - 1
        if self.afos == "SWOMCD":
            center = "SPC"
        else:
            center = "WPC"
        concerning_text = ""
        if self.concerning is not None:
            concerning_text = f" concerning {self.concerning}"
        prob_extra = self.get_prob_extra()
        attempt = ("#%s %s %s %s%s%s: %s ") % (
            center,
            "issues" if not self.is_correction else "corrects",
            self.afos[3:],
            self.discussion_num,
            concerning_text,
            prob_extra,
            self.areas_affected,
        )
        return f"{attempt[:charsleft]}{self.get_url()}"

    def get_url(self):
        """Return the URL for SPC's website"""
        if self.afos == "SWOMCD":
            return ("https://www.spc.noaa.gov/products/md/%s/md%04i.html") % (
                self.valid.year,
                self.discussion_num,
            )
        return (
            "https://www.wpc.ncep.noaa.gov/metwatch/"
            "metwatch_mpd_multi.php?md=%s&yr=%s"
        ) % (self.discussion_num, self.valid.year)

    def parse_areas_affected(self):
        """Return the areas affected"""
        sections = self.unixtext.split("\n\n")
        for section in sections:
            if section.strip().find("AREAS AFFECTED...") == 0:
                return section[17:].replace("\n", " ")
        return None

    def get_jabbers(self, uri, _uri2=None):
        """Return plain text and html variants for a Jabber msg

        Args:
          uri (str): URL number one needed for constructing the URI
          _uri2 (str): not used, but needed for the over-ride

        Returns:
          (list): List of lists, plain text, html text, xtra dict
        """
        # convert htmlentities
        spcuri = html_escape(self.get_url())
        center = "Storm Prediction Center"
        pextra = ""
        if self.afos == "FFGMPD":
            center = "Weather Prediction Center"
            pextra = "Precipitation "
        prob_extra = self.get_prob_extra() + " "
        concerning_text = ""
        if self.concerning is not None:
            concerning_text = f" concerning {self.concerning}"
        plain = ("%s issues Mesoscale %sDiscussion #%s%s%s%s") % (
            center,
            pextra,
            self.discussion_num,
            concerning_text,
            prob_extra,
            spcuri,
        )
        html = (
            '<p>%s %s <a href="%s">'
            "Mesoscale %sDiscussion #%s</a>%s%s"
            '(<a href="%s?pid=%s">View text</a>)</p>'
        ) % (
            center,
            "issues" if not self.is_correction else "corrects",
            spcuri,
            pextra,
            self.discussion_num,
            concerning_text,
            prob_extra,
            uri,
            self.get_product_id(),
        )
        channels = self.get_channels()
        channels.extend(["%s.%s" % (self.afos, w) for w in self.attn_wfo])
        channels.extend(["%s.%s" % (self.afos, w) for w in self.attn_rfc])
        channels.extend(["%s.%s" % (self.afos, w) for w in self.cwsus])
        xtra = dict(
            channels=",".join(channels),
            product_id=self.get_product_id(),
            twitter=self.tweet(),
        )
        return [[plain, html, xtra]]

    def parse_concerning(self):
        """Figure out the concerning text, if it exists."""
        tokens = CONCERNING.findall(self.unixtext)
        if not tokens:
            return None
        return tokens[0].strip().removesuffix("...")

    def parse_discussion_num(self):
        """Figure out what discussion number this is"""
        tokens = DISCUSSIONNUM.findall(self.unixtext)
        if not tokens:
            raise MCDException("Could not parse discussion number")
        return int(tokens[0])

    def parse_geometry(self):
        """Find the polygon that's in this MCD product"""
        tokens = LATLON.findall(self.unixtext.replace("\n", " "))
        if not tokens:
            raise MCDException("Could not parse LAT...LON geometry")
        pts = []
        for pair in tokens[0].split():
            lat = float(pair[:4]) / 100.0
            lon = 0 - float(pair[4:]) / 100.0
            if lon > -40:
                lon = lon - 100.0
            pts.append((lon, lat))
        return ShapelyPolygon(pts)

    def database_save(self, txn):
        """Save this product to the database"""
        table = "mcd" if self.afos == "SWOMCD" else "mpd"
        if self.is_correction:
            txn.execute(
                f"delete from {table} where year = %s and num = %s",
                (self.valid.year, self.discussion_num),
            )
            if txn.rowcount == 0:
                self.warnings.append(
                    "Correction product, but no original found in database."
                )
        # Remove any previous entries
        sql = f"DELETE from {table} where product_id = %s and num = %s"
        txn.execute(sql, (self.get_product_id(), self.discussion_num))
        if txn.rowcount > 0:
            LOG.warning(
                "mcd.database_save %s %s removed %s entries",
                self.get_product_id(),
                self.discussion_num,
                txn.rowcount,
            )
        giswkt = f"SRID=4326;{self.geometry.wkt}"
        sql = (
            f"INSERT into {table} (product_id, geom, issue, expire, "
            "num, year, watch_confidence, concerning, most_prob_tornado, "
            "most_prob_hail, most_prob_gust) "
            "values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        )
        args = (
            self.get_product_id(),
            giswkt,
            self.sts,
            self.ets,
            self.discussion_num,
            self.valid.year,
            self.find_watch_probability(),
            self.concerning,
            self.most_prob_tags.tornado,
            self.most_prob_tags.hail,
            self.most_prob_tags.gust,
        )
        txn.execute(sql, args)


def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    """Helper function"""
    return MCDProduct(text, utcnow, ugc_provider, nwsli_provider)
