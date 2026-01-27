"""NWS Local Storm Report (LSR) Parsing."""

import math
import re
from datetime import datetime, timedelta, timezone

from shapely.geometry import Point as ShapelyPoint

from pyiem import reference
from pyiem.nws.lsr import LSR, _icestorm_remark
from pyiem.nws.product import TextProduct, TextProductException
from pyiem.util import utc

# Don't permit LSRs that are more than 1 hour newer than product time
# or future of the current time
FUTURE_THRESHOLD = timedelta(hours=1)
SPLITTER = re.compile(
    r"(^[0-9].+?\n^[0-9].+?\n)((?:.*?\n)+?)(?=^[0-9]|$)", re.MULTILINE
)
# Limitation on number of new jabber messages possible within a single prod
MAX_JABBER_MESSAGES = 20


class LSRProductException(TextProductException):
    """Something we can raise when bad things happen!"""


class LSRProduct(TextProduct):
    """Represents a text product of the LSR variety"""

    def __init__(
        self, text, utcnow=None, ugc_provider=None, nwsli_provider=None
    ):
        """constructor"""
        super().__init__(
            text,
            utcnow=utcnow,
            ugc_provider=ugc_provider,
            nwsli_provider=nwsli_provider,
        )
        self.lsrs: list[LSR] = []
        self.duplicates = 0

    def get_temporal_domain(self) -> tuple[datetime | None, datetime | None]:
        """Return the min and max timestamps of lsrs"""
        if not self.lsrs:
            return None, None
        valids = [lsr.valid.astimezone(timezone.utc) for lsr in self.lsrs]
        return min(valids), max(valids)

    def is_summary(self):
        """Returns is this LSR is a summary or not"""
        return self.unixtext.upper().find("...SUMMARY") > 0

    def get_url(self, baseuri: str) -> str:
        """Get the URL of this product"""
        min_time, max_time = self.get_temporal_domain()
        wfo = self.source[1:]
        return (
            f"{baseuri}?by=wfo&amp;wfo={wfo}&amp;sts={min_time:%Y%m%d%H%M}"
            f"&amp;ets={max_time:%Y%m%d%H%M}"
        )

    def get_jabbers(self, uri, _uri2=None):
        """return a text and html variant for Jabber stuff"""
        res = []
        if not self.lsrs:
            return res
        wfo = self.source[1:]
        url = self.get_url(uri)

        if len(self.lsrs) < MAX_JABBER_MESSAGES:
            for mylsr in self.lsrs:
                if mylsr.duplicate:
                    continue
                res.append(mylsr.get_jabbers(uri))

        if self.is_summary() or len(self.lsrs) >= MAX_JABBER_MESSAGES:
            extra_text = " "
            if self.duplicates > 0:
                extra_text = (
                    f", {self.duplicates} out of {len(self.lsrs)} reports "
                    "were previously sent and not repeated here. "
                )
            text = f"{wfo} issues Summary Local Storm Report{extra_text}{url}"

            html = (
                f"<p>{wfo} issues <a href='{url}'>"
                f"Summary Local Storm Report</a>{extra_text}</p>"
            )
            xtra = {
                "product_id": self.get_product_id(),
                "channels": f"LSR{wfo}",
                "twitter": text,
                "twitter_media": (
                    "https://mesonet.agron.iastate.edu/plotting/auto/plot/242/"
                    f"pid:{self.get_product_id()}.png"
                ),
            }
            res.append([text, html, xtra])
        return res


def _mylowercase(text):
    """Specialized lowercase function"""
    tokens = text.split()
    for i, t in enumerate(tokens):
        if len(t) > 3:
            tokens[i] = t.title()
        elif t in [
            "N",
            "NNE",
            "NNW",
            "NE",
            "E",
            "ENE",
            "ESE",
            "SE",
            "S",
            "SSE",
            "SSW",
            "SW",
            "W",
            "WSW",
            "WNW",
            "NW",
        ]:
            continue
    return " ".join(tokens)


def parse_lsr(prod, text):
    """Emit a LSR object based on this text!
    0914 PM     HAIL             SHAW                    33.60N 90.77W
    04/29/2005  1.00 INCH        BOLIVAR            MS   EMERGENCY MNGR
    """
    lines = text.split("\n")
    if len(lines) < 2:
        prod.warnings.append(
            ("LSR text is too short |%s|\n%s")
            % (text.replace("\n", "<NL>"), text)
        )
        return None
    lsr = LSR()
    lsr.product = prod
    lsr.text = text
    tokens = lines[0].split()
    h12 = tokens[0][:-2]
    mm = tokens[0][-2:]
    ampm = tokens[1]
    dstr = f"{h12}:{mm} {ampm} {lines[1][:10]}"
    lsr.valid = datetime.strptime(dstr, "%I:%M %p %m/%d/%Y")
    lsr.assign_timezone(prod.tz, prod.z)
    # Check that we are within bounds
    if lsr.utcvalid > (prod.valid + FUTURE_THRESHOLD) or lsr.utcvalid > (
        utc() + FUTURE_THRESHOLD
    ):
        prod.warnings.append(
            "LSR is from the future!\n"
            f"prod.valid: {prod.valid} lsr.valid: {lsr.valid}\n"
            f"{text}\n"
        )
        return None

    lsr.wfo = prod.source[1:]

    lsr.typetext = lines[0][12:29].strip()
    if lsr.typetext.upper() not in reference.lsr_events:
        prod.warnings.append(f"Unknown lsr.typetext |{lsr.typetext}|\n{text}")
        return None

    lsr.city = lines[0][29:53].strip()

    tokens = lines[0][53:].strip().split()
    lat = float(tokens[0][:-1])
    lat_sign = tokens[0][-1]
    if lat_sign == "S":
        lat = 0 - lat
    lon = 0 - float(tokens[1][:-1])
    lon_sign = tokens[1][-1]
    if lon_sign == "E":
        lon = 0 - lon
    if lon <= -180 or lon >= 180 or lat >= 90 or lat <= -90:
        prod.warnings.append(f"Invalid Geometry Lat: {lat} Lon: {lon}\n{text}")
        return None
    lsr.geometry = ShapelyPoint((lon, lat))

    lsr.consume_magnitude(lines[1][12:29].strip())
    if lsr.magnitude_f is not None and math.isnan(lsr.magnitude_f):
        prod.warnings.append(f"LSR has NAN magnitude\n{text}")
        return None
    # Condition for a specific spacing case we want to workaround
    if lines[1][47] != " " and lines[1][52] != " ":
        prod.warnings.append(f"Workaround LSR spacing for |{lines[1][47:53]}|")
        lines[1] = lines[1][:47] + " " + lines[1][47:]
    lsr.county = lines[1][29:48].strip()
    if lsr.county == "":
        prod.warnings.append(f"LSR has empty county\n{text}")
    lsr.state = lines[1][48:50].strip()
    if lsr.state == "":
        prod.warnings.append(f"LSR has empty state\n{text}")
    lsr.source = lines[1][53:].strip()
    if lsr.source == "":
        prod.warnings.append(f"LSR has empty source\n{text}")
    if len(lines) > 2:
        meat = " ".join(lines[2:]).strip()
        if meat.strip() != "":
            lsr.remark = " ".join(meat.split())
    if lsr.typetext.upper() == "ICE STORM" and lsr.magnitude_f is None:
        val = _icestorm_remark(lsr.remark)
        if val is not None:
            lsr.magnitude_f = val
            lsr.magnitude_qualifier = "U"
            lsr.magnitude_units = "INCH"
    return lsr


def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    """Helper function that actually converts the raw text and emits an
    LSRProduct instance or returns an exception"""
    if ugc_provider is None:
        ugc_provider = {}
    prod = LSRProduct(
        text, utcnow, ugc_provider=ugc_provider, nwsli_provider=nwsli_provider
    )
    if prod.z is None:
        prod.warnings.append("Abort parsing as no timezone was found.")
        return prod
    for match in SPLITTER.finditer(prod.unixtext):
        lsr = parse_lsr(prod, "".join(match.groups()))
        if lsr is None:
            continue
        prod.lsrs.append(lsr)

    return prod
