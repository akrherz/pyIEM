"""Parse SIGMETs"""

import math
import re
from datetime import timedelta

from metpy.units import units
from shapely.geometry import Point, Polygon

from pyiem.exceptions import SIGMETException
from pyiem.nws.product import TextProduct

O_LINE1 = re.compile(
    "SIGMET (?P<name>[A-Z]*) (?P<num>[0-9]*) "
    "VALID (?P<sts>[0-9]{6})/(?P<ets>[0-9]{6})"
)

O_PAIRS = re.compile(r"(?P<lat>[NS][0-9]{2,4})\s?(?P<lon>[EW][0-9]{3,5})")

CS_RE = re.compile(
    r"""CONVECTIVE\sSIGMET\s(?P<label>[0-9A-Z]+)\s
VALID\sUNTIL\s(?P<hour>[0-2][0-9])(?P<minute>[0-5][0-9])Z\s
(?P<states>[A-Z ]+)\s
(?P<from>FROM)?\s?(?P<locs>[0-9A-Z \-]+?)\s
(?P<dmshg>DMSHG|DVLPG|INTSF)?\s?(?P<geotype>AREA|LINE|ISOL)?\s?
(?P<cutype>EMBD|SEV|SEV\sEMBD|EMBD\sSEV)?\s?TS\s(?P<width>[0-9]+\sNM\sWIDE)?
(?P<diameter>D[0-9]+)?
""",
    re.VERBOSE,
)

FROM_RE = re.compile(
    r"""
(?P<offset>[0-9]+)?
(?P<drct>N|NE|NNE|ENE|E|ESE|SE|SSE|S|SSW|SW|WSW|W|WNW|NW|NNW)?\s?
(?P<loc>[A-Z0-9]{3})
""",
    re.VERBOSE,
)

OL_RE = re.compile(
    r"OUTLOOK\sVALID\s(?P<begin>[0-9]{6})-(?P<end>[0-9]{6})\n", re.VERBOSE
)

AREA_RE = re.compile(
    r"AREA\s(?P<areanum>[0-9]+)\.\.\.FROM\s(?P<locs>[0-9A-Z \-]+)\n",
    re.VERBOSE,
)

LINE_RE = re.compile(
    r"(?P<distance>[0-9]*)NM\s+EITHER\s+SIDE\s+OF\s+LINE\s+", re.VERBOSE
)

CIRCLE_RE = re.compile(r"WI\s+(?P<distance>[0-9]*)NM\s+OF\s+", re.VERBOSE)


dirs = {
    "NNE": 22.5,
    "ENE": 67.5,
    "NE": 45.0,
    "E": 90.0,
    "ESE": 112.5,
    "SSE": 157.5,
    "SE": 135.0,
    "S": 180.0,
    "SSW": 202.5,
    "WSW": 247.5,
    "SW": 225.0,
    "W": 270.0,
    "WNW": 292.5,
    "NW": 315.0,
    "NNW": 337.5,
    "N": 0,
    "": 0,
}


class SIGMET:
    """Data Structure."""

    def __init__(self):
        """Constructor"""
        self.sts = None
        self.ets = None
        self.geom = None
        self.label = None
        self.areatext = ""
        self.centers = []
        self.raw = None


def figure_expire(ptime, hour, minute):
    """
    Convert something like 0255Z into a full blown time
    """
    expire = ptime
    if hour < ptime.hour:
        expire += timedelta(days=1)
    return expire.replace(hour=hour, minute=minute)


def go2lonlat(lon0, lat0, direction, displacement):
    """http://stackoverflow.com/questions/7222382"""
    # Radius of the Earth
    R = 6378.1
    # Bearing is 90 degrees converted to radians.
    brng = math.radians(dirs.get(direction, 0))
    # Convert nautical miles to km
    d = (units("nautical_mile") * displacement).to("km").magnitude

    # Current lat point converted to radians
    lat1 = math.radians(lat0)
    # Current long point converted to radians
    lon1 = math.radians(lon0)

    lat2 = math.asin(
        math.sin(lat1) * math.cos(d / R)
        + math.cos(lat1) * math.sin(d / R) * math.cos(brng)
    )

    lon2 = lon1 + math.atan2(
        math.sin(brng) * math.sin(d / R) * math.cos(lat1),
        math.cos(d / R) - math.sin(lat1) * math.sin(lat2),
    )

    lat2 = math.degrees(lat2)
    lon2 = math.degrees(lon2)

    return lon2, lat2


def locs2lonslats(loc_provider, locstr, geotype, _widthstr, diameterstr):
    """
    Convert a locstring into a lon lat arrays
    """
    lats = []
    lons = []
    for loc in locstr.split("-"):
        s = FROM_RE.search(loc)
        if s:
            d = s.groupdict()
            if d["offset"] is not None:
                (lon1, lat1) = go2lonlat(
                    loc_provider[d["loc"]]["lon"],
                    loc_provider[d["loc"]]["lat"],
                    d["drct"],
                    float(d["offset"]),
                )
            else:
                (lon1, lat1) = (
                    loc_provider[d["loc"]]["lon"],
                    loc_provider[d["loc"]]["lat"],
                )
            lats.append(lat1)
            lons.append(lon1)
    if geotype == "ISOL" or diameterstr is not None:
        lats2 = []
        lons2 = []
        diameter = float(diameterstr.replace("D", ""))
        # Approximation
        diameterdeg = diameter / 110.0
        # UR
        lons2.append(lons[0] - diameterdeg)
        lats2.append(lats[0] + diameterdeg)
        # UL
        lons2.append(lons[0] + diameterdeg)
        lats2.append(lats[0] + diameterdeg)
        # LL
        lons2.append(lons[0] + diameterdeg)
        lats2.append(lats[0] - diameterdeg)
        # LR
        lons2.append(lons[0] - diameterdeg)
        lats2.append(lats[0] - diameterdeg)
        lons = lons2
        lats = lats2

    if geotype == "LINE":
        lats2 = []
        lons2 = []
        # Figure out left hand points
        for i in range(0, len(lats) - 1):
            deltax = lons[i + 1] - lons[i]
            deltay = lats[i + 1] - lats[i]
            if deltax == 0:
                deltax = 0.001
            angle = math.atan(deltay / deltax)
            runx = 0.1 * math.cos(angle)
            runy = 0.1 * math.sin(angle)
            # UR
            lons2.append(lons[i] - runy)
            lats2.append(lats[i] + runx)
            # UL
            lons2.append(lons[i + 1] - runy)
            lats2.append(lats[i + 1] + runx)

        for i in range(0, len(lats) - 1):
            deltax = lons[i + 1] - lons[i]
            deltay = lats[i + 1] - lats[i]
            if deltax == 0:
                deltax = 0.001
            angle = math.atan(deltay / deltax)
            runx = 0.1 * math.cos(angle)
            runy = 0.1 * math.sin(angle)
            # LL
            lons2.append(lons[i + 1] + runy)
            lats2.append(lats[i + 1] - runx)
            # LR
            lons2.append(lons[i] + runy)
            lats2.append(lats[i] - runx)

        lons = lons2
        lats = lats2

    return lons, lats


def compute_esol(pts, distance):
    """Figure out the box points given the two points and the distance"""
    newpts = []
    deltax = pts[1][0] - pts[0][0]
    deltay = pts[1][1] - pts[0][1]
    # Compute unit vector
    linedistance = (deltax**2 + deltay**2) ** 0.5
    deltax = deltax / linedistance
    deltay = deltay / linedistance
    N = distance / 111.0  # approx
    newpts.append([pts[0][0] - N * deltay, pts[0][1] + N * deltax])
    newpts.append([pts[1][0] - N * deltay, pts[1][1] + N * deltax])
    newpts.append([pts[1][0] + N * deltay, pts[1][1] - N * deltax])
    newpts.append([pts[0][0] + N * deltay, pts[0][1] - N * deltax])
    newpts.append([newpts[0][0], newpts[0][1]])

    return newpts


def _parse_sections(text: str) -> list[str]:
    """Build list of sections with gleaned text."""
    # text is conditioned, so LDM, WMO and AFOS
    text = "\n".join(text.split("\n")[3:])
    sections = []
    for section in text.split("\n\n"):
        section = section.strip()
        if section:
            sections.append(section)
    return sections


class SIGMETProduct(TextProduct):
    """
    Represents a Storm Prediction Center Mesoscale Convective Discussion
    """

    def __init__(
        self, text, utcnow=None, ugc_provider=None, nwsli_provider=None
    ):
        """constructor"""
        super().__init__(text, utcnow, ugc_provider, nwsli_provider)
        self.sections = _parse_sections(self.unixtext)
        self.sigmets: list[SIGMET] = []
        if self.afos in ["SIGC", "SIGW", "SIGE", "SIGAK1", "SIGAK2"]:
            self.process_SIGC()
        elif self.afos[:2] == "WS":
            pass
        else:
            self.process_ocean()

    def sql(self, txn):
        """Do SQL related stuff that is required"""
        for sigmet in self.sigmets:
            sqlwkt = f"SRID=4326;{sigmet.geom.wkt}"
            table = f"sigmets_{self.valid:%Y}"
            sql = f"DELETE from {table} where label = %s and expire = %s"
            args = (sigmet.label, sigmet.ets)
            txn.execute(sql, args)
            sql = (
                f"INSERT into {table} (sigmet_type, label, issue, "
                "expire, product_id, geom, narrative) "
                "VALUES ('C', %s, %s, %s, %s, %s, %s)"
            )
            args = (
                sigmet.label,
                self.valid,
                sigmet.ets,
                self.get_product_id(),
                sqlwkt,
                sigmet.raw,
            )
            txn.execute(sql, args)
            # Compute who is impacted by this SIGMET
            txn.execute(
                "SELECT distinct id from cwsu WHERE "
                f"st_overlaps(geomFromEWKT('{sqlwkt}'), geom) or "
                f"st_contains(geomFromEWKT('{sqlwkt}'), geom) "
            )
            for row in txn.fetchall():
                sigmet.centers.append(row["id"])

    def compute_time(self, ddhhmi):
        """Convert this string into a proper date time"""
        day = int(ddhhmi[:2])
        hour = int(ddhhmi[2:4])
        minute = int(ddhhmi[4:6])
        ts = self.valid
        if self.valid.day > 25 and day < 5:  # next month
            ts += timedelta(days=15)

        return ts.replace(day=day, hour=hour, minute=minute)

    def process_ocean(self):
        """Process oceananic"""
        meat = self.unixtext.replace("\n", " ")
        m = O_LINE1.search(meat)
        d = m.groupdict()
        s = SIGMET()
        s.label = "%s %s" % (d["name"], d["num"])
        s.sts = self.compute_time(d["sts"])
        s.ets = self.compute_time(d["ets"])
        m = re.findall(O_PAIRS, meat)
        if not m:
            # TODO: resolve what SIGMET cancels are
            if meat.find("CNL SIGMET") > 0 or meat.find("CANCEL SIGMET") > 0:
                return
            raise SIGMETException("Failed to parse 0_PAIRS: %s" % (meat,))
        pts = []
        for pair in m:
            if len(pair[0][1:]) == 2:
                lat = float(pair[0][1:])
            else:
                lat = float(pair[0][1:]) / 100.0
            if pair[0][0] == "S":
                lat = 0 - lat
            if len(pair[1][1:]) == 3:
                lon = float(pair[1][1:])
            else:
                lon = float(pair[1][1:]) / 100.0
            if pair[1][0] == "W":
                lon = 0 - lon
            pts.append((lon, lat))
        m = LINE_RE.search(meat)
        if m is not None:
            d = m.groupdict()
            pts = compute_esol(pts, int(d["distance"]))
        m = CIRCLE_RE.search(meat)
        if m is not None and len(pts) == 1:
            d = m.groupdict()
            # buffer a point, approximate 1 deg as 100 km :/
            buffer = (
                (units("nautical_mile") * float(d["distance"]))
                .to("km")
                .magnitude
            )
            s.geom = Point(pts[0]).buffer(buffer / 100.0)
        else:
            s.geom = Polygon(pts)

        s.raw = self.unixtext
        self.sigmets.append(s)

    def process_SIGC(self):
        """Process this type of SIGMET"""
        for section in self.sections:
            s = CS_RE.search(section.replace("\n", " "))
            if s is None:
                continue
            data = s.groupdict()
            sig = SIGMET()
            sig.label = data["label"]
            sig.areatext = data["states"].replace(" FROM", "")
            sig.ets = figure_expire(
                self.valid, int(data["hour"]), int(data["minute"])
            )
            lons, lats = locs2lonslats(
                self.nwsli_provider,
                data["locs"],
                data["geotype"],
                data["width"],
                data["diameter"],
            )

            if len(lons) <= 2:
                continue
            pts = []
            for lon, lat in zip(lons, lats, strict=False):
                pts.append((lon, lat))
            if lats[0] != lats[-1] or lons[0] != lons[-1]:
                pts.append((lons[0], lats[0]))
            sig.geom = Polygon(pts)
            pos = section.find("CONVECTIVE")
            sig.raw = section[pos:]

            self.sigmets.append(sig)

    def get_jabbers(self, uri, _uri2=None):
        """Return the Jabber for this sigmet"""
        j = []
        for sig in self.sigmets:
            area = " for " + sig.areatext if sig.areatext != "" else ""
            txt = ("%s issues SIGMET %s%s till %s UTC") % (
                self.source,
                sig.label,
                area,
                sig.ets.strftime("%H%M"),
            )
            html = ("<p>%s issues SIGMET %s%s till %s UTC</p>") % (
                self.source,
                sig.label,
                area,
                sig.ets.strftime("%H%M"),
            )
            channels = ["SIGMET.%s" % (i,) for i in sig.centers]
            channels.append("SIGMET.%s" % (self.source[1:],))
            xtra = {"channels": ",".join(channels), "twitter": txt}

            j.append([txt, html, xtra])
        return j


def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    """Helper function"""
    return SIGMETProduct(text, utcnow, ugc_provider, nwsli_provider)
