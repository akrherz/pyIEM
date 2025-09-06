"""Base Class encapsulating a NWS Text Product"""

import re
from collections import OrderedDict
from datetime import timedelta, timezone
from typing import Optional, Union

from shapely.geometry import MultiPolygon, Polygon
from shapely.wkt import dumps

from pyiem import reference
from pyiem.exceptions import InvalidPolygon, TextProductException
from pyiem.nws import hvtec, ugc
from pyiem.nws.vtec import VTEC
from pyiem.nws.vtec import parse as vtec_parse
from pyiem.util import LOG
from pyiem.wmo import WMOProduct

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
    r".*TORNADO\.\.\.(?P<tornado>RADAR INDICATED|OBSERVED|POSSIBLE)"
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
TORNADO = re.compile(r"^AT |^\* AT", re.I)
RESENT = re.compile(r"\.\.\.(RESENT|RETRANSMITTED|CORRECTED)")
EMERGENCY_RE = re.compile(r"(TORNADO|FLASH\s+FLOOD)\s+EMERGENCY", re.I)
PDS_RE = re.compile(
    r"THIS\s+IS\s+A\s+PARTICULARLY\s+DANGEROUS\s+SITUATION", re.I
)
SQUALLTAG = re.compile(
    r".*SNOW\s?SQUALL\.\.\.(?P<tag>RADAR INDICATED|OBSERVED)"
)
SQUALLIMPACTTAG = re.compile(
    r".*SNOW\s?SQUALL IMPACT\.\.\.(?P<tag>SIGNIFICANT|GENERAL)"
)
EF_RE = re.compile(r"^Rating:\s*EF\s?\-?(?P<num>\d)\s*$", re.M | re.I)
ATTN_WFO = re.compile(
    r"ATTN\.\.\.WFO\.\.\.([\.A-Z]*?)(?:LAT\.\.\.LON|ATTN\.\.\.RFC)"
)
ATTN_RFC = re.compile(r"ATTN\.\.\.RFC\.\.\.([\.A-Z]*)")


def damage_survey_pns(prod, data):
    """Glean out things, hopefully."""
    ffs = {}
    for token in EF_RE.findall(prod.unixtext):
        entry = ffs.setdefault(int(token), [])
        entry.append(1)
    data["maxf"] = ""
    if ffs:
        maxf = max(ffs.keys())
        # More for testing than anything
        if maxf > 5:
            raise ValueError(f"Bad EF of {maxf} found")
        data["maxf"] = f" (Max: EF{maxf})"
    # approx and headline has starting space already :/
    hdl = " " if len(data["headline"]) > 90 else f"{data['headline']} "
    plain = (
        f"{data['source']} issues Damage Survey PNS{data['maxf']} at "
        f"{data['stamp']}{hdl}{data['url']}"
    )
    html = (
        f'<p>{data["source"]} issues <a href="{data["url"]}">Damage Survey PNS'
        f"</a>{data['maxf']} at {data['stamp']}{hdl}</p>"
    )
    return plain, html


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

    # If the last character is a digit, we need to add a space (legacy prods)
    if strdata[-1].isdigit():
        strdata += " "

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
    # It is 2023, we need to be tag confirmed.
    if seg.is_emergency and not tag_confirms and seg.tp.valid.year >= 2023:
        seg.tp.warnings.append(
            "Segment indicated emergency, but tags did not confirm and "
            "product is >= 2023, so setting no emergency."
        )
        seg.is_emergency = False
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

    def __init__(self, text, tp: "TextProduct"):
        """Constructor"""
        # Poor name shadow to self.tp, but different
        self.unixtext = text
        self.tp = tp  # Reference to parent
        self.vtec: list[VTEC] = vtec_parse(text)
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
        self.squalltag = None
        # allows for deterministic testing of results
        self.flood_tags = OrderedDict()
        self.is_emergency = False
        self.is_pds = False
        self.process_tags()
        qc_is_emergency(self)
        self.bullets = self.process_bullets()

    def get_ugcs_tuple(self):
        """Helper to return a tuple useful for SQL."""
        return tuple(self.get_ugcs_list())

    def get_ugcs_list(self):
        """Helper to return a list useful for SQL."""
        return [str(u) for u in self.ugcs]

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
        return [" ".join(b.split()) for b in bullets]

    def process_tags(self):
        """Find various tags in this segment"""
        nolf = self.unixtext.replace("\n", " ")
        res = EMERGENCY_RE.findall(nolf)
        if res and self.vtec:
            # Ensure that the emergency RE matches the segment phenomena
            # We later double check this based on the found tags
            if (
                res[0].upper() == "FLASH FLOOD"
                and self.vtec[0].phenomena == "FF"
            ):
                self.is_emergency = True
            if res[0].upper() == "TORNADO" and self.vtec[0].phenomena == "TO":
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

        for species, tag in THREATTAG.findall(nolf):
            if species == "HAIL":
                self.hailthreat = tag
            elif species == "WIND":
                self.windthreat = tag

        match = SQUALLTAG.match(nolf)
        if match:
            gdict = match.groupdict()
            self.squalltag = gdict["tag"]
            match = SQUALLIMPACTTAG.match(nolf)
            if match:
                gdict = match.groupdict()
                self.damagetag = gdict["tag"]

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
                self.squalltag is None,
                not self.flood_tags,
            ]
        ):
            return ""

        parts = []
        if self.squalltag is not None:
            parts.append(f"snow squall: {self.squalltag}")
        if self.tornadotag is not None:
            parts.append(f"tornado: {self.tornadotag}")
        if self.waterspouttag is not None:
            parts.append(f"waterspout: {self.waterspouttag}")
        if self.landspouttag is not None:
            parts.append(f"landspout: {self.landspouttag}")
        if self.damagetag is not None:
            if self.vtec and self.vtec[0].phenomena == "SQ":
                parts.append(f"impact threat: {self.damagetag}")
            else:
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
                if len(poly.geoms) > 2:
                    self.tp.warnings.append(
                        "LAT...LON buffer(0) returned 3+ polygon, culling."
                    )
                    return None
                # Life choices here, if we have a bowtie and the one side is
                # very small, we should cull it and just use the larger side
                polys = list(poly.geoms)
                polys = sorted(polys, key=lambda x: x.area)
                if (
                    polys[0].is_valid
                    and polys[1].is_valid
                    and polys[0].area * 10 < polys[1].area
                ):
                    self.tp.warnings.append(
                        "LAT...LON buffer(0) made 2 polys, taking biggest."
                    )
                    poly = polys[1]
                else:
                    self.tp.warnings.append(
                        "LAT...LON buffer(0) made 2 polys with invalids."
                    )
                    return None
            else:
                self.tp.warnings.append(
                    "LAT...LON polygon is invalid, but buffer(0) fixed it!"
                )
        # check 2, is the exterior ring of the polygon clockwise?
        if poly.exterior.is_ccw:
            # No longer a warning as it was too much noise
            LOG.debug(
                "LAT...LON polygon exterior is CCW, reversing\n%s",
                poly.exterior.xy,
            )
            poly = Polygon(
                zip(
                    poly.exterior.xy[0][::-1],
                    poly.exterior.xy[1][::-1],
                    strict=False,
                )
            )
        # NB: the encoding parsed above should always have just two decimals
        self.giswkt = (
            f"SRID=4326;{dumps(MultiPolygon([poly]), rounding_precision=2)}"
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
            for lat, lon in zip(lats, lons, strict=False):
                pairs.append(f"{lon} {lat}")
            self.tml_giswkt = f"SRID=4326;LINESTRING({','.join(pairs)})"
        self.tml_sknt = int(gdict["sknt"])
        self.tml_dir = int(gdict["dir"])

    def parse_headlines(self):
        """Find headlines in this segment"""
        res = []
        candidate = ""
        for line in [s.strip() for s in self.unixtext.split("\n")]:
            if line.startswith("..."):
                candidate = line
            elif candidate != "":
                candidate += " " + line
            if line.endswith("..."):
                if 6 < len(candidate) < 160:  # arb
                    res.append(candidate.replace("...", ""))
                candidate = ""
        return res

    def get_affected_wfos(self) -> list[str]:
        """Based on the ugc_provider, figure out which WFOs are impacted by
        this product segment"""
        affected_wfos = []
        for _ugc in self.ugcs:
            affected_wfos.extend(_ugc.wfos)

        return list(set(affected_wfos))


class TextProduct(WMOProduct):
    """class representing a NWS Text Product"""

    def __init__(
        self,
        text,
        utcnow=None,
        ugc_provider: Optional[Union[ugc.UGCProvider, dict]] = None,
        nwsli_provider=None,
        parse_segments=True,
    ):
        """
        Constructor
        @param text string single text product
        @param utcnow used to compute offsets for when this product my be valid
        @param ugc_provider dict or UGCProvider instance
        @param parse_segments should the segments be parsed as well? True
        """
        super().__init__(text, utcnow=utcnow)
        if isinstance(ugc_provider, dict):
            ugc_provider = ugc.UGCProvider(legacy_dict=ugc_provider)
        if ugc_provider is None:
            ugc_provider = ugc.UGCProvider()
        if nwsli_provider is None:
            nwsli_provider = {}
        self.ugc_provider = ugc_provider
        self.nwsli_provider = nwsli_provider
        self.sections = self.unixtext.split("\n\n")
        self.segments: list[TextProductSegment] = []
        self.geometry = None

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

    def parse_attn_rfc(self):
        """Figure out which RFCs this product is seeking attention"""
        tokens = ATTN_RFC.findall(self.unixtext.replace("\n", ""))
        if not tokens:
            return []
        rfcs = re.findall("([A-Z]{3,5})", tokens[0])
        # le sigh
        if "LAT" in rfcs:
            rfcs = rfcs[: rfcs.index("LAT")]
        return rfcs

    def parse_attn_wfo(self):
        """Figure out which WFOs this product is seeking attention"""
        tokens = ATTN_WFO.findall(self.unixtext.replace("\n", ""))
        if not tokens:
            return []
        return re.findall("([A-Z]{3})", tokens[0])

    def get_channels(self):
        """Return a list of channels"""
        res = [self.afos, f"{self.afos[:3]}..."]
        if self.afos[:3] in ["TCU", "TCD", "TCM", "TCP", "TWO"]:
            res.append(self.afos[:5])
        elif self.afos == "AHDNWC":
            # Get the ATTN
            res.extend(self.parse_attn_wfo())
            res.extend(self.parse_attn_rfc())
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
        aaa = "" if self.afos is None else self.afos[:3]
        hdl = self.get_main_headline()
        data = {
            "headline": f" ...{hdl}..." if hdl != "" else "",
            "source": self.source[1:],
            "aaa": aaa,
            "name": reference.prodDefinitions.get(
                self.afos, reference.prodDefinitions.get(aaa, self.afos)
            ),
            "stamp": self.get_nicedate(),
            "url": f"{uri}?pid={self.get_product_id()}",
        }
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
            "twitter": f"#{tweet}",
        }
        if self.segments and self.segments[0].sbw:
            # Generic product has a polygon, so we add special twitter message
            xtra["twitter_media"] = (
                "https://mesonet.agron.iastate.edu/plotting/auto/plot/227/"
                f"pid:{self.get_product_id()}::segnum:0.png"
            )
        if (
            self.afos is not None
            and self.afos[:3] == "PNS"
            and self.unixtext.upper().find("DAMAGE SURVEY") > -1
        ):
            try:
                plain, html = damage_survey_pns(self, data)
                xtra["twitter"] = plain
                xtra["channels"] += ",DAMAGEPNS"
            except Exception as exp:
                self.warnings.append(f"Hit exception {exp} in damage_survey")
        return [(plain, html, xtra)]

    def get_signature(self) -> Optional[str]:
        """Attempt to glean the free form text that is a signature."""
        lines = [x.strip() for x in self.unixtext.split("\n") if x.strip()]
        res = None
        for line in lines[::-1][:3]:
            # We found something that should have come before the signature
            if line in ["$$", "&&"] or len(line) > 24:
                break
            if line not in ["$", "&"]:
                res = line
                break
        return res

    def parse_segments(self):
        """Split the product by its $$"""
        segs = self.unixtext.split("$$")
        for seg in segs:
            self.segments.append(TextProductSegment(seg, self))

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
