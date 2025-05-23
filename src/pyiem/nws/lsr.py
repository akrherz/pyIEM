"""The Atomic Local Storm Report ... Report"""

# pylint: disable=unsubscriptable-object
import re
from datetime import timedelta, timezone
from urllib.parse import quote

from pyiem import reference
from pyiem.reference import TRACE_VALUE
from pyiem.util import html_escape

UGC_MATCH = re.compile(r"^[A-Z][A-Z][CZ][0-9][0-9][0-9]$")
ICE_ACCUM_V0 = re.compile(r"(\d+)/(\d+)\"?T?H?S? O?F?\s*A?N?\s*(INCHES|INCH)")
ICE_ACCUM_V1 = re.compile(
    r"(0\.\d|\.\d+|\d\.?\d?\d?)\"? (TENTHS?)?\s?O?F?\s*A?N?\s*(INCHES|INCH)"
)
ICE_ACCUM_V2 = re.compile(
    r"(THREE QUARTERS|ONE QUARTER|ONE HALF|HALF|ONE THIRD|QUARTER|ONE|"
    "THREE TENTHS|THIRD|ONE TENTH|TWO THIRDS|TWO TENTHS) "
    r"O?F?\s*A?N?\s*(INCHES|INCH)"
)
ICE_XREF = {
    "ONE TENTH": 0.10,
    "TWO TENTHS": 0.20,
    "ONE QUARTER": 0.25,
    "QUARTER": 0.25,
    "THREE TENTHS": 0.30,
    "ONE THIRD": 0.33,
    "THIRD": 0.33,
    "HALF": 0.5,
    "ONE HALF": 0.5,
    "TWO THIRDS": 0.66,
    "THREE QUARTERS": 0.75,
    "ONE": 1.0,
}

MAG_UNITS = re.compile(
    r"(ACRE|INCHES|INCH|MILE|MPH|KTS|U|FT|F|E|MI|M|TRACE)", re.IGNORECASE
)
# Products that are considered delayed reports
DELAYED_THRESHOLD = timedelta(hours=12)


def _icestorm_remark(remark):
    """Glean a magnitude from an ICE STORM event."""
    if remark is None or remark.find("SNOW DEPTH") > -1:
        return None
    # Remove things that confuse logic
    replaces = [
        ["-", " "],
        ["PRECIPITATION", "SNOW"],
        ["SLEET", "SNOW"],
        ["INCH OF SNOW", " "],
        ["INCHES OF SNOW", " "],
        ["INCHES IN DIAMETER", " "],
        ["INCH TREE BRANCH", " "],
        ["INCH DIAMETER", " "],
    ]
    for subject, replacement in replaces:
        remark = remark.replace(subject, replacement)
    tokens = ICE_ACCUM_V0.findall(remark)
    mags = []
    for _n, _d, _u in tokens:
        mags.append(float(_n) / float(_d))
    if mags:
        return min(mags)

    tokens = ICE_ACCUM_V1.findall(remark)
    mags = []
    for _m, _t, _u in tokens:
        if _t.startswith("TENTH"):
            mags.append(float(_m) / 10.0)
            continue
        mags.append(float(_m))
    if mags:
        return min(mags)
    tokens = ICE_ACCUM_V2.findall(remark)
    if tokens:
        return ICE_XREF[tokens[0][0]]

    return None


def _generate_channels(lsrobj):
    """Generate the channels string for this LSR."""
    cleantype = lsrobj.typetext.replace(" ", "_")
    res = [
        f"LSR{lsrobj.wfo}",
        "LSR.ALL",
        f"LSR.{cleantype.upper()}",
        f"LSR.{lsrobj.state}",
        f"LSR.{lsrobj.state}.{cleantype.upper()}",
    ]
    return ",".join(res)


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


class LSR:
    """Represents a single Local Storm Report within the LSRProduct"""

    def __init__(self):
        """constructor"""
        self.utcvalid = None
        self.valid = None
        self.typetext = None
        self.geometry = None
        self.city: str = None
        self.county: str = None
        self.source = None
        self.remark = None
        self.magnitude_f = None
        self.magnitude_str = None
        self.magnitude_qualifier = None
        self.magnitude_units = None
        self.state = None
        self.source = None
        self.text = None
        self.wfo = None
        self.duplicate = False
        self.z = None
        # Carry a reference to the product that had this LSR
        self.product = None

    def __str__(self):
        """String Representation."""
        s = ""
        for attr in self.__dict__:
            s += f"{attr} {getattr(self, attr, '')}\n"
        return s

    def get_lat(self):
        """Return the LSR latitude."""
        return self.geometry.xy[1][0]

    def get_lon(self):
        """Return the LSR longitude."""
        return self.geometry.xy[0][0]

    def consume_magnitude(self, text):
        """Convert LSR magnitude text into something atomic"""
        # Brute force this special case, which trips up the regex
        if text.upper().strip().startswith("TRACE"):
            self.magnitude_f = TRACE_VALUE
            return
        self.magnitude_str = text
        tokens = MAG_UNITS.findall(text)
        if not tokens:
            if text != "":
                self.product.warnings.append(f"Unable to parse Units |{text}|")
            return
        if len(tokens) == 2:
            self.magnitude_qualifier = tokens[0]
            self.magnitude_units = tokens[1]
        elif len(tokens) == 1:
            self.magnitude_units = tokens[0]
        val = MAG_UNITS.sub("", text).strip()
        if val == "T":
            self.magnitude_f = TRACE_VALUE
        elif val != "":
            self.magnitude_f = float(val)

    def get_dbtype(self):
        """Return the typecode used in the database for this event type"""
        val = self.typetext.upper()
        # Hack for Marine LSRs akrherz/pyIEM#729
        if val == "TSTM WND GST" and UGC_MATCH.match(self.county):
            return "M"
        if val == "HAIL" and UGC_MATCH.match(self.county):
            return "h"
        return reference.lsr_events.get(val, None)

    def sql(self, txn):
        """Provided a database transaction object, persist this LSR"""
        wkt = f"SRID=4326;{self.geometry.wkt}"
        prod = self.product
        # akrherz/pyWWA#150, if a duplicate, just update the product_id_summary
        if self.duplicate and self.product.is_summary():
            txn.execute(
                """
                UPDATE lsrs SET product_id_summary = %s, updated = %s
                WHERE valid = %s
                and typetext = %s and wfo = %s and geom = %s
                """,
                (
                    prod.get_product_id(),
                    prod.valid,
                    self.utcvalid,
                    self.typetext.upper(),
                    self.wfo,
                    wkt,
                ),
            )
            return
        # Different mapping to UGCs
        if self.county is not None and UGC_MATCH.match(self.county):
            fargs = (self.county, self.valid)
            func = "get_gid"
        else:
            fargs = (self.county, self.state)
            func = "get_gid_by_name_state"
        # Newer schema supports range partitioning, so can direct insert
        sql = (
            "INSERT into lsrs (valid, type, magnitude, city, county, "
            "state, source, remark, geom, wfo, typetext, product_id, updated, "
            "unit, qualifier, gid, product_id_summary) values "
            "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
            f"{func}(%s, %s), %s)"
        )
        args = (
            self.utcvalid,
            self.get_dbtype(),
            self.magnitude_f,
            self.city,
            self.county,
            self.state,
            self.source,
            self.remark,
            wkt,
            self.wfo,
            self.typetext.upper(),
            prod.get_product_id(),
            prod.valid,
            self.magnitude_units,
            self.magnitude_qualifier,
            *fargs,
            prod.get_product_id() if prod.is_summary() else None,
        )
        txn.execute(sql, args)

    def get_jabbers(self, uri):
        """Return a Jabber formatted message tuple."""
        url = (
            f"{uri}?by=wfo&amp;wfo={self.wfo}&amp;sts={self.utcvalid:%Y%m%d%H%M}"
            f"&amp;ets={self.utcvalid:%Y%m%d%H%M}"
        )
        time_fmt = "%-I:%M %p"
        # Is this a delayed report?
        if (self.product.valid - self.valid) > DELAYED_THRESHOLD:
            time_fmt = "%-d %b, %-I:%M %p"
        if self.valid.day != self.product.utcnow.day:
            time_fmt = "%-d %b, %-I:%M %p"

        prefix = ""
        timefmt = "At %-I:%M %p"
        # Is this product delayed?
        if (self.product.valid - self.valid) > DELAYED_THRESHOLD:
            prefix = "[Delayed Report] "
            timefmt = "On %b %-d, at %-I:%M %p"
        magstr = self.mag_string()
        tweet = (
            f"{prefix}{self.valid.strftime(timefmt)} {self.z}, "
            f"{_mylowercase(self.city)} [{self.county.title()} Co, "
            f"{self.state}] {self.source} reports {magstr}"
        )
        remark = ""
        if self.remark is not None:
            remark = self.remark.replace("DELAYED REPORT.", "")
            tweet = f"{tweet}. {remark}"
            size = (
                reference.TWEET_CHARS
                - reference.TWEET_URL_CHARS
                - len(tweet)
                - 7  # extra careful and support hash tag
            )
            if size <= 0:
                # We need to truncate and try to be cute to get a whole word
                tweet = tweet[: (size - 5)].rsplit(" ", 1)[0] + "..."

        # rectify
        tweet = " ".join(tweet.split()) + f" #{self.state.lower()}wx"

        xtra = {
            "product_id": self.product.get_product_id(),
            "channels": _generate_channels(self),
            "geometry": f"POINT({self.get_lon()} {self.get_lat()})",
            "ptype": self.get_dbtype(),
            "valid": self.utcvalid.strftime("%Y%m%dT%H:%M:00"),
            "category": "LSR",
            "twitter": f"{tweet} {url}",
            "lat": str(self.get_lat()),
            "long": str(self.get_lon()),
            "twitter_media": (
                "https://mesonet.agron.iastate.edu/plotting/auto/plot/242/"
                f"pid:{self.product.get_product_id()}"
                f"::_:{quote(self.city)}.png"
            ),
        }
        html = (
            f"<p>{prefix}{_mylowercase(self.city)} [{self.county.title()} Co, "
            f'{self.state}] {self.source} <a href="{url}">reports {magstr}'
            f"</a> at {self.valid.strftime(time_fmt)} {self.z} -- "
            f"{html_escape(remark)}</p>"
        )

        plain = (
            f"{prefix}{_mylowercase(self.city)} [{self.county.title()} Co, "
            f"{self.state}] {self.source} reports {magstr} at "
            f"{self.valid.strftime(time_fmt)} {self.z} -- "
            f"{html_escape(remark)} {url}"
        )
        return [plain, html, xtra]

    def assign_timezone(self, tz, z):
        """retroactive assignment of timezone, so to improve attrs"""
        # We can't just assign the timezone (maybe we can someday)
        self.utcvalid = self.valid + timedelta(hours=reference.offsets[z])
        self.utcvalid = self.utcvalid.replace(tzinfo=timezone.utc)
        self.valid = self.utcvalid.astimezone(tz)
        # complexity with non-DST sites
        if z.endswith("ST") and self.valid.dst():
            self.valid -= timedelta(hours=1)
        self.z = z

    def mag_string(self):
        """Return a string representing the magnitude and units"""
        mag_long = str(self.typetext)
        if self.magnitude_units == "MPH":
            mag_long = (
                f"{mag_long} of {self.magnitude_qualifier}"
                f"{self.magnitude_f:.0f} {self.magnitude_units}"
            )
        elif (
            self.typetext.upper() == "HAIL"
            and self.magnitude_f is not None
            and f"{self.magnitude_f:.2f}" in reference.hailsize
        ):
            haildesc = reference.hailsize[f"{self.magnitude_f:.2f}"]
            mag_long = (
                f"{mag_long} of {haildesc} size ({self.magnitude_qualifier}"
                f"{self.magnitude_f:.2f} {self.magnitude_units})"
            )
        elif self.magnitude_units == "F":
            # Report Tornados as EF scale and not F
            mag_long = f"{mag_long} of E{self.magnitude_str}"
        elif self.magnitude_f is not None and 0 < self.magnitude_f < 0.001:
            mag_long = f"Trace of {mag_long}"
        elif self.magnitude_f:
            mag_long = (
                f"{mag_long} of {self.magnitude_f:.2f} {self.magnitude_units}"
            )
        elif self.magnitude_str:
            mag_long = f"{mag_long} of {self.magnitude_str}"
        return mag_long
