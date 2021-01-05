"""NWS Local Storm Report (LSR) Parsing."""
import datetime
import re
import math


from shapely.geometry import Point as ShapelyPoint
from pyiem.nws.product import TextProduct, TextProductException
from pyiem.nws.lsr import LSR, _icestorm_remark
from pyiem.util import utc
from pyiem import reference

# Don't permit LSRs that are more than 1 hour newer than product time
# or future of the current time
FUTURE_THRESHOLD = datetime.timedelta(hours=1)
SPLITTER = re.compile(
    r"(^[0-9].+?\n^[0-9].+?\n)((?:.*?\n)+?)(?=^[0-9]|$)", re.MULTILINE
)


class LSRProductException(TextProductException):
    """ Something we can raise when bad things happen! """


class LSRProduct(TextProduct):
    """ Represents a text product of the LSR variety """

    def __init__(
        self, text, utcnow=None, ugc_provider=None, nwsli_provider=None
    ):
        """ constructor """
        self.lsrs = []
        self.duplicates = 0
        TextProduct.__init__(
            self,
            text,
            utcnow=utcnow,
            ugc_provider=ugc_provider,
            nwsli_provider=nwsli_provider,
        )

    def get_temporal_domain(self):
        """ Return the min and max timestamps of lsrs """
        if not self.lsrs:
            return None, None
        valids = []
        for lsr in self.lsrs:
            valids.append(lsr.valid)
        return min(valids), max(valids)

    def is_summary(self):
        """ Returns is this LSR is a summary or not """
        return self.unixtext.find("...SUMMARY") > 0

    def get_url(self, baseuri):
        """ Get the URL of this product """
        min_time, max_time = self.get_temporal_domain()
        wfo = self.source[1:]
        return "%s#%s/%s/%s" % (
            baseuri,
            wfo,
            min_time.strftime("%Y%m%d%H%M"),
            max_time.strftime("%Y%m%d%H%M"),
        )

    def get_jabbers(self, uri, _uri2=None):
        """ return a text and html variant for Jabber stuff """
        res = []
        if not self.lsrs:
            return res
        wfo = self.source[1:]
        url = self.get_url(uri)

        for mylsr in self.lsrs:
            if mylsr.duplicate:
                continue
            res.append(mylsr.get_jabbers(uri))

        if self.is_summary():
            extra_text = ""
            if self.duplicates > 0:
                extra_text = (
                    ", %s out of %s reports were previously "
                    "sent and not repeated here."
                ) % (self.duplicates, len(self.lsrs))
            text = "%s: %s issues Summary Local Storm Report %s %s" % (
                wfo,
                wfo,
                extra_text,
                url,
            )

            html = (
                "<p>%s issues "
                "<a href='%s'>Summary Local Storm Report</a>%s</p>"
            ) % (wfo, url, extra_text)
            xtra = {
                "product_id": self.get_product_id(),
                "channels": "LSR%s" % (wfo,),
            }
            res.append([text, html, xtra])
        return res


def _mylowercase(text):
    """ Specialized lowercase function """
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
    dstr = "%s:%s %s %s" % (h12, mm, ampm, lines[1][:10])
    lsr.valid = datetime.datetime.strptime(dstr, "%I:%M %p %m/%d/%Y")
    lsr.assign_timezone(prod.tz, prod.z)
    # Check that we are within bounds
    if lsr.utcvalid > (prod.valid + FUTURE_THRESHOLD) or lsr.utcvalid > (
        utc() + FUTURE_THRESHOLD
    ):
        prod.warnings.append(
            (
                "LSR is from the future!\n"
                "prod.valid: %s lsr.valid: %s\n"
                "%s\n"
            )
            % (prod.valid, lsr.valid, text)
        )
        return None

    lsr.wfo = prod.source[1:]

    lsr.typetext = lines[0][12:29].strip()
    if lsr.typetext.upper() not in reference.lsr_events:
        prod.warnings.append(
            ("Unknown lsr.typetext |%s|\n%s") % (lsr.typetext, text)
        )
        return None

    lsr.city = lines[0][29:53].strip()

    tokens = lines[0][53:].strip().split()
    lat = float(tokens[0][:-1])
    lon = 0 - float(tokens[1][:-1])
    if lon <= -180 or lon >= 180 or lat >= 90 or lat <= -90:
        prod.warnings.append(
            ("Invalid Geometry Lat: %s Lon: %s\n%s") % (lat, lon, text)
        )
        return None
    lsr.geometry = ShapelyPoint((lon, lat))

    lsr.consume_magnitude(lines[1][12:29].strip())
    if lsr.magnitude_f is not None and math.isnan(lsr.magnitude_f):
        prod.warnings.append("LSR has NAN magnitude\n%s" % (text,))
        return None
    lsr.county = lines[1][29:48].strip()
    lsr.state = lines[1][48:50]
    lsr.source = lines[1][53:].strip()
    if len(lines) > 2:
        meat = " ".join(lines[2:]).strip()
        if meat.strip() != "":
            lsr.remark = " ".join(meat.split())
    if lsr.typetext == "ICE STORM" and lsr.magnitude_f is None:
        val = _icestorm_remark(lsr.remark)
        if val is not None:
            lsr.magnitude_f = val
            lsr.magnitude_qualifier = "U"
            lsr.magnitude_units = "INCH"
    return lsr


def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    """Helper function that actually converts the raw text and emits an
    LSRProduct instance or returns an exception"""
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
