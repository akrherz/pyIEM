"""Base Class encapsulating a NWS Text Product"""
from datetime import timezone, timedelta, datetime
from collections import OrderedDict
import re

try:
    from zoneinfo import ZoneInfo  # type: ignore
except ImportError:
    from backports.zoneinfo import ZoneInfo  # type: ignore

from shapely.geometry import Polygon, MultiPolygon
from shapely.wkt import dumps

from pyiem import reference
from pyiem.util import LOG
from pyiem.exceptions import TextProductException, InvalidPolygon
from pyiem.nws import ugc, vtec, hvtec


# The AWIPS Product Identifier is supposed to be 6chars as per directive,
# but in practice it is sometimes something between 4 and 6 chars
# We need to be careful this does not match the LDM sequence identifier
AFOSRE = re.compile(r"^([A-Z0-9]{4,6})\s*\t*$", re.M)
TIME_FMT = (
    "([0-9:]+) (AM|PM) ([A-Z][A-Z][A-Z]?T) ([A-Z][A-Z][A-Z]) "
    "([A-Z][A-Z][A-Z]) ([0-9]+) ([1-2][0-9][0-9][0-9])"
)
TIME_RE = re.compile(f"^{TIME_FMT}$", re.M | re.IGNORECASE)
TIME_UTC_RE = re.compile(
    TIME_FMT.replace("(AM|PM) ([A-Z][A-Z][A-Z]?T)", r"(AM|PM)?\s?(UTC)"),
    re.M | re.I,
)
# Sometimes products have a duplicated timestamp in another tz
TIME_EXT_RE = re.compile(
    rf"^{TIME_FMT}\s?/\s?{TIME_FMT}\s?/$", re.M | re.IGNORECASE
)
# Without the line start and end requirement
TIME_RE_ANYWHERE = re.compile(f"{TIME_FMT}", re.IGNORECASE)

# Note that bbb of RTD is supported here, but does not appear to be allowed
WMO_RE = re.compile(
    "^(?P<ttaaii>[A-Z0-9]{4,6}) (?P<cccc>[A-Z]{4}) "
    r"(?P<ddhhmm>[0-3][0-9][0-2][0-9][0-5][0-9])\s*"
    r"(?P<bbb>[ACR][ACMORT][A-Z])?\s*$",
    re.M,
)
TIME_MOT_LOC = re.compile(
    r"TIME\.\.\.MOT\.\.\.LOC\s+(?P<ztime>[0-9]{4})Z\s+"
    r"(?P<dir>[0-9]{1,3})DEG\s+"
    r"(?P<sknt>[0-9]{1,3})KT\s+(?P<loc>[0-9 ]+)"
)
LAT_LON_PREFIX = re.compile(r"LAT\.\.\.LON", re.IGNORECASE)
LAT_LON = re.compile(r"([0-9]{4,8})\s+")
# This is a legacy tag that is no longer used, but we want to continue to
# parse it.
WINDHAIL = re.compile(
    r".*WIND\.\.\.HAIL (?P<winddir>[><]?)(?P<wind>[0-9]+)"
    "(?P<windunits>MPH|KTS) "
    r"(?P<haildir>[><]?)(?P<hail>[0-9\.]+)IN"
)
HAILTAG = re.compile(
    r".*(HAIL|MAX HAIL SIZE)\.\.\.(?P<haildir>[><]?)(?P<hail>[0-9\.]+)\s?IN"
)
WINDTAG = re.compile(
    r".*(WIND|MAX WIND GUST)\.\.\.(?P<winddir>[><]?)\s?(?P<wind>[0-9]+)\s?"
    "(?P<windunits>MPH|KTS)"
)
TORNADOTAG = re.compile(
    r".*TORNADO\.\.\.(?P<tornado>RADAR INDICATED|" "OBSERVED|POSSIBLE)"
)
SPOUTTAG = re.compile(
    r".*(?P<species>LAND|WATER)SPOUT\.\.\."
    "(?P<spout>RADAR INDICATED|OBSERVED|POSSIBLE)"
)
DAMAGETAG = re.compile(
    r".*(?P<species>TORNADO|THUNDERSTORM) DAMAGE THREAT\.\.\."
    "(?P<damage>CONSIDERABLE|SIGNIFICANT|CATASTROPHIC|DESTRUCTIVE)"
)
THREATTAG = re.compile(
    r"(?P<species>HAIL|WIND) THREAT\.\.\."
    r"(?P<tag>RADAR INDICATED|OBSERVED|POSSIBLE)"
)
FLOOD_TAGS = re.compile(
    r".*(?P<key>FLASH FLOOD|FLASH FLOOD DAMAGE THREAT|EXPECTED RAINFALL|"
    r"DAM FAILURE|LEVEE FAILURE)\.\.\.(?P<value>.*?)\n"
)
TORNADO = re.compile(r"^AT |^\* AT")
RESENT = re.compile(r"\.\.\.(RESENT|RETRANSMITTED|CORRECTED)")
EMERGENCY_RE = re.compile(r"(TORNADO|FLASH\s+FLOOD)\s+EMERGENCY", re.I)
PDS_RE = re.compile(
    r"THIS\s+IS\s+A\s+PARTICULARLY\s+DANGEROUS\s+SITUATION", re.I
)

KNOWN_BAD_TTAAII = ["KAWN"]


def checker(lon, lat, strdata):
    """make sure our values are within physical bounds"""
    if lat >= 90 or lat <= -90:
        raise TextProductException(f"invalid latitude {lat} from {strdata}")
    if lon > 180 or lon < -180:
        raise TextProductException(f"invalid longitude {lon} from {strdata}")
    return (lon, lat)


def str2polygon(strdata):
    """Convert some string data into a polygon"""
    pts = []
    partial = None

    # We have two potential formats, one with 4 or 5 places and one
    # with eight!
    vals = re.findall(LAT_LON, strdata)
    for val in vals:
        if len(val) == 8:
            lat = float(val[:4]) / 100.00
            lon = float(val[4:]) / 100.00
            if lon < 40:
                lon += 100.0
            lon = 0 - lon
            pts.append(checker(lon, lat, strdata))
        else:
            fval = float(val) / 100.00
            if partial is None:  # we have lat
                partial = fval
                continue
            # we have a lon
            if fval < 40:
                fval += 100.0
            fval = 0 - fval
            pts.append(checker(fval, partial, strdata))
            partial = None

    if not pts:
        return None
    if pts[0][0] != pts[-1][0] and pts[0][1] != pts[-1][1]:
        pts.append(pts[0])
    if len(pts) < 3:
        raise InvalidPolygon(f"Less than three points for polygon {pts}")
    return Polygon(pts)


def date_tokens2datetime(tokens):
    """Convert tokens from MND regex to a valid time, if possible.

    Returns:
      z (str): 3-4 char timezone string
      tz (datetime.timezone): of this product
      utcvalid (datetimetz): of this product
    """
    tokens = list(tokens)  # ensure mutable
    z = tokens[2].upper()
    tz = ZoneInfo(reference.name2pytz.get(z, "UTC"))
    hhmi = tokens[0]
    # False positive from regex
    if hhmi[0] == ":":
        hhmi = hhmi.replace(":", "")
    if hhmi.find(":") > -1:
        (hh, mi) = hhmi.split(":")
    elif len(hhmi) < 3:
        hh = hhmi
        mi = 0
    else:
        hh = hhmi[:-2]
        mi = hhmi[-2:]
    # Workaround 24 hour clock abuse
    if int(hh) > 12 and (
        tokens[1].upper() == "PM" or tokens[2] in ["UTC", "GMT"]
    ):
        # this is a hack to ensure this is PM when we are in UTC
        tokens[1] = "PM"
        hh = int(hh) - 12
    dstr = (
        f"{hh if int(hh) > 0 else 12}:{mi} "
        f"{tokens[1] if tokens[1] != '' else 'AM'} "
        f"{tokens[4]} {tokens[5]} {tokens[6]}"
    )
    # Careful here, need to go to UTC time first then come back!
    now = datetime.strptime(dstr, "%I:%M %p %b %d %Y")
    now += timedelta(hours=reference.offsets.get(z, 0))
    return z, tz, now.replace(tzinfo=timezone.utc)


def qc_is_emergency(seg):
    """Belt + Suspenders check that this segment is an emergency."""
    ffdt = seg.flood_tags.get("FLASH FLOOD DAMAGE THREAT")
    # NOOPS
    if (
        not seg.is_emergency
        and seg.damagetag != "CATASTROPHIC"
        and ffdt != "CATASTROPHIC"
    ):
        return
    # Auto qualifier
    tag_confirms = "CATASTROPHIC" in [seg.damagetag, ffdt]
    if tag_confirms:
        seg.is_emergency = True
        return
    # Oh, we have work to do
    has_tags = seg.damagetag is not None or ffdt is not None
    # tags do not confirm the emergency
    if seg.is_emergency and has_tags and not tag_confirms:
        seg.tp.warnings.append(
            "Segment indicated emergency, but tags negated it.\n"
            f"tag_confirms: {tag_confirms} damagetag: {seg.damagetag} "
            f"ffdt: {ffdt}"
        )
        seg.is_emergency = False
        return
    # this segment is a CAN, EXP VTEC sole action
    if seg.is_emergency and seg.vtec and seg.vtec[0].action in ["CAN", "EXP"]:
        seg.tp.warnings.append(
            "Segment indicated emergency, but VTEC action is expiring."
        )
        seg.is_emergency = False


class TextProductSegment:
    """A segment of a Text Product"""

    def __init__(self, text, tp):
        """Constructor"""
        self.unixtext = text
        self.tp = tp  # Reference to parent
        self.vtec = vtec.parse(text)
        self.ugcs, self.ugcexpire = ugc.parse(
            text,
            tp.valid,
            ugc_provider=tp.ugc_provider,
            is_firewx=any(v.phenomena == "FW" for v in self.vtec),
        )
        self.headlines = self.parse_headlines()
        self.hvtec = hvtec.parse(text, tp=tp)

        # TIME...MOT...LOC Stuff!
        self.tml_giswkt = None
        self.tml_valid = None
        self.tml_sknt = None
        self.tml_dir = None
        self.process_time_mot_loc()

        #
        self.giswkt = None
        try:
            self.sbw = self.process_latlon()
        except InvalidPolygon as exp:
            tp.warnings.append(str(exp))
            self.sbw = None

        # tags
        self.windtag = None
        self.windtagunits = None
        self.windthreat = None
        self.hailtag = None
        self.haildirtag = None
        self.hailthreat = None
        self.winddirtag = None
        self.tornadotag = None
        self.waterspouttag = None
        self.landspouttag = None
        self.damagetag = None
        # allows for deterministic testing of results
        self.flood_tags = OrderedDict()
        self.is_emergency = False
        self.is_pds = False
        self.process_tags()
        qc_is_emergency(self)
        self.bullets = self.process_bullets()

    def get_ugcs_tuple(self):
        """Helper to return a tuple useful for SQL."""
        return tuple([str(u) for u in self.ugcs])

    def get_hvtec_nwsli(self):
        """Return the first hvtec NWSLI entry, if it exists"""
        if not self.hvtec:
            return None
        return self.hvtec[0].nwsli.id

    def get_hvtec_cause(self):
        """Return the first hvtec cause entry, if it exists"""
        if not self.hvtec:
            return None
        return self.hvtec[0].cause

    def get_hvtec_severity(self):
        """Return the first hvtec severity entry, if it exists"""
        if not self.hvtec:
            return None
        return self.hvtec[0].severity

    def get_hvtec_record(self):
        """Return the first hvtec record entry, if it exists"""
        if not self.hvtec:
            return None
        return self.hvtec[0].record

    def svs_search(self):
        """Special search the product for special text"""
        sections = self.unixtext.split("\n\n")
        for section in sections:
            if TORNADO.findall(section):
                return " ".join(section.replace("\n", " ").split())
        return ""

    def process_bullets(self):
        """Figure out the bulleted segments"""
        parts = re.findall(r"^\*([^\*]*)", self.unixtext, re.M | re.DOTALL)
        bullets = []
        for part in parts:
            pos = part.find("\n\n")
            if pos > 0:
                part = part[:pos]
            # look for subheadings :/
            piece = ""
            for line in part.split("\n"):
                if line.strip().startswith("- "):
                    if piece != "":
                        bullets.append(piece)
                    piece = line.split("- ", 1)[1]
                    continue
                if piece != "":
                    piece += f" {line} "
            if piece != "":
                bullets.append(piece)
            bullets.append(" ".join(part.replace("\n", "").split()))
        # Cleanup
        bullets = [" ".join(b.split()) for b in bullets]
        return bullets

    def process_tags(self):
        """Find various tags in this segment"""
        nolf = self.unixtext.replace("\n", " ")
        res = EMERGENCY_RE.findall(nolf)
        if res:
            # We later double check this based on the found tags
            self.is_emergency = True
        res = PDS_RE.findall(nolf)
        if res:
            self.is_pds = True
        match = WINDHAIL.match(nolf)
        if match:
            gdict = match.groupdict()
            self.windtag = gdict["wind"]
            self.windtagunits = gdict["windunits"]
            self.haildirtag = gdict["haildir"]
            self.winddirtag = gdict["winddir"]
            self.hailtag = gdict["hail"]

        match = WINDTAG.match(nolf)
        if match:
            gdict = match.groupdict()
            self.winddirtag = gdict["winddir"]
            self.windtag = gdict["wind"]
            self.windtagunits = gdict["windunits"]

        match = HAILTAG.match(nolf)
        if match:
            gdict = match.groupdict()
            self.haildirtag = gdict["haildir"]
            self.hailtag = gdict["hail"]

        match = TORNADOTAG.match(nolf)
        if match:
            gdict = match.groupdict()
            self.tornadotag = gdict["tornado"]

        match = DAMAGETAG.match(nolf)
        if match:
            gdict = match.groupdict()
            self.damagetag = gdict["damage"]

        for (species, tag) in THREATTAG.findall(nolf):
            if species == "HAIL":
                self.hailthreat = tag
            elif species == "WIND":
                self.windthreat = tag

        match = SPOUTTAG.match(nolf)
        if match:
            gdict = match.groupdict()
            if gdict["species"] == "WATER":
                self.waterspouttag = gdict["spout"]
            else:
                self.landspouttag = gdict["spout"]

        for token in FLOOD_TAGS.findall(self.unixtext):
            self.flood_tags[token[0]] = token[1]

    def special_tags_to_text(self):
        """
        Convert the special tags into a nice text
        """
        if all(
            [
                self.windtag is None,
                self.tornadotag is None,
                self.hailtag is None,
                self.damagetag is None,
                self.waterspouttag is None,
                self.landspouttag is None,
                not self.flood_tags,
            ]
        ):
            return ""

        parts = []
        if self.tornadotag is not None:
            parts.append(f"tornado: {self.tornadotag}")
        if self.waterspouttag is not None:
            parts.append(f"waterspout: {self.waterspouttag}")
        if self.landspouttag is not None:
            parts.append(f"landspout: {self.landspouttag}")
        if self.damagetag is not None:
            parts.append(f"damage threat: {self.damagetag}")
        if self.windtag is not None:
            _p1 = self.winddirtag.replace(">", "&gt;").replace("<", "&lt;")
            _p2 = "" if self.windthreat is None else f" ({self.windthreat})"
            parts.append(f"wind: {_p1}{self.windtag} {self.windtagunits}{_p2}")
        if self.hailtag is not None:
            _p1 = self.haildirtag.replace(">", "&gt;").replace("<", "&lt;")
            _p2 = "" if self.hailthreat is None else f" ({self.hailthreat})"
            parts.append(f"hail: {_p1}{self.hailtag} IN{_p2}")
        for k, v in self.flood_tags.items():
            parts.append(f"{k.lower()}: {v.lower()}")
        return f" [{', '.join(parts)}] "

    def process_latlon(self):
        """Parse the segment looking for the 'standard' LAT...LON encoding"""
        data = self.unixtext.replace("\n", " ")
        search = LAT_LON_PREFIX.search(data)
        if search is None:
            return None
        pos = search.start()
        newdata = data[pos + 9 :]
        # Go find our next non-digit, non-space character, if we find it, we
        # should truncate our string, this could be improved, I suspect
        search = re.search(r"[^\s0-9]", newdata)
        if search is not None:
            pos2 = search.start()
            newdata = newdata[:pos2]

        poly = str2polygon(newdata)
        if poly is None:
            return None

        # check 0, PGUM polygons are east longitude akrherz/pyIEM#74
        if self.tp.source == "PGUM":
            newpts = [[0 - pt[0], pt[1]] for pt in poly.exterior.coords]
            poly = Polygon(newpts)

        # check 1, is the polygon valid?
        if not poly.is_valid:
            poly = poly.buffer(0)
            # Careful, this could return a multipolygon
            if isinstance(poly, MultiPolygon):
                self.tp.warnings.append(
                    "LAT...LON buffer(0) returned multipolygon, culling."
                )
                return None
            if not poly.is_valid:
                self.tp.warnings.append(
                    f"LAT...LON polygon is invalid twice!\n{poly.exterior.xy}"
                )
                return None
            self.tp.warnings.append(
                "LAT...LON polygon is invalid, but buffer(0) fixed it!"
            )
        # check 2, is the exterior ring of the polygon clockwise?
        if poly.exterior.is_ccw:
            # No longer a warning as it was too much noise
            LOG.warning(
                "LAT...LON polygon exterior is CCW, reversing\n%s",
                poly.exterior.xy,
            )
            poly = Polygon(
                zip(poly.exterior.xy[0][::-1], poly.exterior.xy[1][::-1])
            )
        self.giswkt = (
            f"SRID=4326;{dumps(MultiPolygon([poly]), rounding_precision=6)}"
        )
        return poly

    def process_time_mot_loc(self):
        """Try to parse the TIME...MOT...LOC"""
        pos = self.unixtext.find("TIME...MOT...LOC")
        if pos == -1:
            return
        if self.unixtext[pos - 1] != "\n":
            self.tp.warnings.append(
                "process_time_mot_loc segment likely has "
                "poorly formatted TIME...MOT...LOC"
            )
        search = TIME_MOT_LOC.search(self.unixtext)
        if not search:
            self.tp.warnings.append(
                "process_time_mot_loc segment find OK, but regex failed..."
            )
            return

        gdict = search.groupdict()
        if len(gdict["ztime"]) != 4 or self.ugcexpire is None:
            return
        hh = int(gdict["ztime"][:2])
        mi = int(gdict["ztime"][2:])
        self.tml_valid = self.ugcexpire.replace(hour=hh, minute=mi)
        if hh > self.ugcexpire.hour:
            self.tml_valid = self.tml_valid - timedelta(days=1)

        self.tml_valid = self.tml_valid.replace(tzinfo=timezone.utc)

        tokens = gdict["loc"].split()
        lats = []
        lons = []
        if len(tokens) % 2 != 0:
            tokens = tokens[:-1]
        if not tokens:
            return
        for i in range(0, len(tokens), 2):
            lats.append(float(tokens[i]) / 100.0)
            lons.append(0 - float(tokens[i + 1]) / 100.0)

        if len(lats) == 1:
            self.tml_giswkt = f"SRID=4326;POINT({lons[0]} {lats[0]})"
        else:
            pairs = []
            for lat, lon in zip(lats, lons):
                pairs.append(f"{lon} {lat}")
            self.tml_giswkt = f"SRID=4326;LINESTRING({','.join(pairs)})"
        self.tml_sknt = int(gdict["sknt"])
        self.tml_dir = int(gdict["dir"])

    def parse_headlines(self):
        """Find headlines in this segment"""
        headlines = re.findall(
            r"^\.\.\.(.*?)\.\.\.[ ]?\n\n", self.unixtext, re.M | re.S
        )
        headlines = [
            " ".join(h.replace("...", ", ").replace("\n", " ").split())
            for h in headlines
        ]
        return headlines

    def get_affected_wfos(self):
        """Based on the ugc_provider, figure out which WFOs are impacted by
        this product segment"""
        affected_wfos = []
        for _ugc in self.ugcs:
            for wfo in _ugc.wfos:
                if wfo not in affected_wfos:
                    affected_wfos.append(wfo)

        return affected_wfos


class TextProduct:
    """class representing a NWS Text Product"""

    def __init__(
        self,
        text,
        utcnow=None,
        ugc_provider=None,
        nwsli_provider=None,
        parse_segments=True,
    ):
        """
        Constructor
        @param text string single text product
        @param utcnow used to compute offsets for when this product my be valid
        @param ugc_provider a dictionary of UGC objects already setup
        @param parse_segments should the segments be parsed as well? True
        """
        self.warnings = []

        self.text = text
        if ugc_provider is None:
            ugc_provider = {}
        if nwsli_provider is None:
            nwsli_provider = {}
        self.ugc_provider = ugc_provider
        self.nwsli_provider = nwsli_provider
        self.unixtext = text.replace("\r", "")
        self.sections = self.unixtext.split("\n\n")
        self.afos = None
        # The "truth" timestamp
        self.valid = None
        # The WMO header based timestamp
        self.wmo_valid = None
        self.source = None
        self.wmo = None
        self.ddhhmm = None
        self.bbb = None
        self.utcnow = utcnow
        self.segments = []
        self.z = None
        self.tz = None
        self.geometry = None
        if utcnow is None:
            self.utcnow = datetime.utcnow().replace(tzinfo=timezone.utc)
        # make sure this is actualing in UTC
        self.utcnow = self.utcnow.astimezone(timezone.utc)

        self.parse_wmo()
        self.parse_afos()
        self._parse_valid(utcnow)
        if parse_segments:
            self.parse_segments()

    def suv_iter(self):
        """Yield [(segment, ugcs, vtec)] combos found in product."""
        for segment in self.segments:
            if not segment.ugcs or not segment.vtec:
                continue
            for _vtec in segment.vtec:
                if _vtec.status == "T" or _vtec.action == "ROU":
                    continue
                yield (segment, segment.ugcs, _vtec)

    def is_resent(self):
        """Check to see if this product is a ...RESENT product"""
        return self.unixtext.find("...RESENT") > 0

    def is_correction(self):
        """Is this product a correction?

        Sadly, this is not as easy as it should be.  It turns out that some
        products do not have a proper correction mechanism, so offices will
        just brute force in a note into the MND header.  So we have to do
        some further checking...

        Returns:
          bool: Is this product a correction?
        """
        # OK, go looking for RESENT style tags, assume it happens within first
        # 300 chars
        if RESENT.search(self.text[:300]):
            return True
        if self.bbb is None or not self.bbb:
            return False
        if self.bbb[0] in ["A", "C"]:
            return True
        return False

    def get_channels(self):
        """Return a list of channels"""
        res = [self.afos, f"{self.afos[:3]}..."]
        if self.afos[:3] in ["TCU", "TCD", "TCM", "TCP", "TWO"]:
            res.append(self.afos[:5])
        return res

    def get_nicedate(self):
        """Nicely format the issuance time of this product"""
        if self.valid is None:
            return "(unknown issuance time)"
        localts = self.valid
        fmt = "%b %-d, %H:%M UTC"
        if self.tz is not None:
            localts = self.valid.astimezone(self.tz)
            # A bit of complexity as offices may not implement daylight saving
            if self.z.endswith("ST") and localts.dst():
                localts -= timedelta(hours=1)
            fmt = "%b %-d, %-I:%M %p " + self.z
        return localts.strftime(fmt)

    def get_main_headline(self, default=""):
        """Return a string for the main headline, if it exists"""
        for segment in self.segments:
            if segment.headlines:
                return segment.headlines[0]
        return default

    def get_jabbers(self, uri, _uri2=None):
        """Return a tuple of jabber messages [(plain, html, xtra_dict)]

        Args:
          uri (str): the base URI to use to construct links

        Returns:
          [(str, str, dict)]
        """
        templates = [
            "%(source)s issues %(name)s (%(aaa)s) at %(stamp)s%(headline)s ",
            "%(source)s issues %(name)s (%(aaa)s) at %(stamp)s ",
        ]
        aaa = self.afos[:3]
        hdl = self.get_main_headline()
        data = {
            "headline": f" ...{hdl}..." if hdl != "" else "",
            "source": self.source[1:],
            "aaa": aaa,
            "name": reference.prodDefinitions.get(
                aaa, reference.prodDefinitions.get(self.afos, self.afos)
            ),
            "stamp": self.get_nicedate(),
            "url": f"{uri}?pid={self.get_product_id()}",
        }
        res = []
        plain = (templates[0] + "%(url)s") % data
        html = (
            '<p>%(source)s issues <a href="%(url)s">%(name)s (%(aaa)s)</a>'
            " at %(stamp)s</p>"
        ) % data
        tweet = templates[0] % data
        if (len(tweet) - 25) > reference.TWEET_CHARS:
            tweet = templates[1] % data
        tweet += data["url"]
        xtra = {
            "channels": ",".join(self.get_channels()),
            "product_id": self.get_product_id(),
            "twitter": tweet,
        }
        res.append((plain, html, xtra))
        return res

    def get_signature(self):
        """Find the signature at the bottom of the page"""
        return " ".join(
            self.segments[-1].unixtext.replace("\n", " ").strip().split()
        )

    def parse_segments(self):
        """Split the product by its $$"""
        segs = self.unixtext.split("$$")
        for seg in segs:
            self.segments.append(TextProductSegment(seg, self))

    def get_product_id(self):
        """Get an identifier of this product used by the IEM"""
        pid = f"{self.valid:%Y%m%d%H%M}-{self.source}-{self.wmo}-{self.afos}"
        if self.bbb:
            pid += f"-{self.bbb}"
        return pid.strip()

    def _parse_valid(self, provided_utcnow):
        """Figure out the timestamp of this product.

        Args:
          provided_utcnow (datetime): What our library was provided for the UTC
            timestamp, it could be None
        """
        # The MND header hopefully has a full timestamp that is the best
        # truth that we can have for this product.
        tokens = TIME_RE.findall(self.unixtext)
        if not tokens:
            tokens = TIME_EXT_RE.findall(self.unixtext)
            if not tokens:
                tokens = TIME_RE_ANYWHERE.findall(self.unixtext)
                if not tokens:
                    tokens = TIME_UTC_RE.findall(self.unixtext)
        if provided_utcnow is None and tokens:
            try:
                z, _tz, valid = date_tokens2datetime(tokens[0])
                if z not in reference.offsets:
                    self.warnings.append(f"product timezone '{z}' unknown")
            except ValueError as exp:
                msg = (
                    f"Invalid timestamp [{' '.join(tokens[0])}] found in "
                    f"product [{self.wmo} {self.source} {self.afos}] header"
                )
                raise TextProductException(self.source[1:], msg) from exp

            # Set the utcnow based on what we found by looking at the header
            self.utcnow = valid

        # Search out the WMO header, this had better always be there
        # We only care about the first hit in the file, searching from top
        # Take the first hit, ignore others
        wmo_day = int(self.ddhhmm[:2])
        wmo_hour = int(self.ddhhmm[2:4])
        wmo_minute = int(self.ddhhmm[4:])

        self.wmo_valid = self.utcnow.replace(
            hour=wmo_hour, minute=wmo_minute, second=0, microsecond=0
        )
        if wmo_day != self.utcnow.day:
            if wmo_day - self.utcnow.day == 1:  # Tomorrow
                self.wmo_valid = self.wmo_valid.replace(day=wmo_day)
            elif wmo_day > 25 and self.utcnow.day < 15:  # Previous month!
                self.wmo_valid = self.wmo_valid + timedelta(days=-10)
                self.wmo_valid = self.wmo_valid.replace(day=wmo_day)
            elif wmo_day < 5 and self.utcnow.day >= 15:  # next month
                self.wmo_valid = self.wmo_valid + timedelta(days=10)
                self.wmo_valid = self.wmo_valid.replace(day=wmo_day)
            else:
                self.wmo_valid = self.wmo_valid.replace(day=wmo_day)

        # we can do no better
        self.valid = self.wmo_valid

        # If we don't find anything, lets default to now, its the best
        if not tokens:
            return
        self.z, self.tz, self.valid = date_tokens2datetime(tokens[0])

    def parse_wmo(self):
        """Parse things related to the WMO header"""
        search = WMO_RE.search(self.unixtext[:100])
        if search is None:
            raise TextProductException(
                f"FATAL: Could not parse WMO header! '{self.text[:100]}'"
            )
        gdict = search.groupdict()
        self.wmo = gdict["ttaaii"]
        self.source = gdict["cccc"]
        self.ddhhmm = gdict["ddhhmm"]
        self.bbb = gdict["bbb"]
        if len(self.wmo) == 4:
            # Don't whine about known problems
            if (
                self.source not in KNOWN_BAD_TTAAII
                and not self.source.startswith("S")
            ):
                self.warnings.append(
                    f"WMO ttaaii found four chars: {self.wmo} {self.source} "
                    "adding 00"
                )
            self.wmo += "00"

    def get_affected_wfos(self):
        """Based on the ugc_provider, figure out which WFOs are impacted by
        this product"""
        affected_wfos = []
        for segment in self.segments:
            for ugcs in segment.ugcs:
                for wfo in ugcs.wfos:
                    if wfo not in affected_wfos:
                        affected_wfos.append(wfo)

        return affected_wfos

    def parse_afos(self):
        """Figure out what the AFOS PIL is"""
        # at most, only look at the top four lines, skipping the first
        data = "\n".join(
            [line.strip() for line in self.sections[0].split("\n")[1:4]]
        )
        tokens = AFOSRE.findall(data)
        if tokens:
            self.afos = tokens[0].strip()
