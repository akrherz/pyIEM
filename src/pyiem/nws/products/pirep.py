"""Pilot Reports (PIREP)

This module attempts to process and store atomic data from PIREPs.  These are
encoded products that look like so:

  UBUS01 KMSC 221700
  EAU UA /OV EAU360030/TM 1715/FL350/TP B737/TB CONT LGT-MOD CHOP =
  EHY UA /OV MBW253036 /TM 1729 /FL105 /TP C206 /SK FEW250 /TA M06
  /TB NEG /RM SMTH=

Unfortunately, there is not much documentation of this format and the feed of
this data contains a bunch of formatting errors.

"""
# stdlib
from enum import Enum
import datetime
import re
import math

# Third Party
from metpy.units import units
from pydantic import BaseModel

# Local
import pyiem.nws.product as product
from pyiem.util import html_escape, LOG

OV_LATLON = re.compile(
    (
        r"\s?(?P<lat>[0-9]{2,4})(?P<latsign>[NS])"
        r"\s?(?P<lon>[0-9]{2,5})(?P<lonsign>[EW])"
    )
)
OV_LOCDIR = re.compile(
    r".*?(?P<loc>[A-Z0-9]{3,4})\s?(?P<dir>[0-9]{3})(?P<dist>[0-9]{3})"
)
OV_TWOLOC = re.compile(
    r"(?P<loc1>[A-Z0-9]{3,4})\s?-\s?(?P<loc2>[A-Z0-9]{3,4})"
)
OV_OFFSET = re.compile(
    (
        r"(?P<dist>[0-9]{1,3})\s?"
        "(?P<dir>NORTH|EAST|SOUTH|WEST|N|NNE|NE|ENE|E|ESE|"
        r"SE|SSE|S|SSW|SW|WSW|W|WNW|NW|NNW)\s+(OF )?(?P<loc>[A-Z0-9]{3,4})"
    )
)

DRCT2DIR = {
    "N": 0,
    "NNE": 22.5,
    "NE": 45,
    "ENE": 67.5,
    "E": 90,
    "ESE": 112.5,
    "SE": 135,
    "SSE": 157.5,
    "S": 180,
    "SSW": 202.5,
    "SW": 225,
    "WSW": 247.5,
    "W": 270,
    "WNW": 292.5,
    "NW": 305,
    "NNW": 327.5,
    "NORTH": 0,
    "EAST": 90,
    "SOUTH": 180,
    "WEST": 270,
}


class Priority(str, Enum):
    """Types of reports."""

    def __str__(self):
        """When we want the str repr."""
        return str(self.value)

    UA = "UA"
    UUA = "UUA"


class PilotReport(BaseModel):
    """A Pilot Report."""

    base_loc: str = None
    text: str = None
    priority: Priority = None
    latitude: float = None
    longitude: float = None
    valid: datetime.datetime = None
    cwsu: str = None
    aircraft_type: str = None
    is_duplicate: bool = False


def _rectify_identifier(station, textprod):
    """Rectify the station identifer to IEM Nomenclature."""
    station = station.strip()
    if len(station) == 4 and station.startswith("K"):
        return station[1:]
    if len(station) == 3 and not textprod.source.startswith("K"):
        return textprod.source[0] + station
    return station


def _parse_lonlat(text):
    """Convert string into lon, lat values"""
    # 2500N07000W
    # -or- 25N070W -or- 25N70W
    # FMH-12 says this is in degrees and minutes!
    d = re.match(OV_LATLON, text).groupdict()

    if len(d["lat"]) == 2 and len(d["lon"]) <= 3:
        # We have integer values :/
        lat = int(d["lat"])
        lon = int(d["lon"])
    else:
        # We have Degrees and minutes
        _d = int(float(d["lat"][-2:]) / 60.0 * 10000.0)
        lat = float(f"{d['lat'][:-2]}.{_d:.0f}")
        _d = int(float(d["lon"][-2:]) / 60.0 * 10000.0)
        lon = float(f"{d['lon'][:-2]}.{_d:.0f}")
    if d["latsign"] == "S":
        lat *= -1
    if d["lonsign"] == "W":
        lon *= -1
    return lon, lat


class Pirep(product.TextProduct):
    """Class for parsing and representing Space Wx Products."""

    def __init__(
        self, text, utcnow=None, ugc_provider=None, nwsli_provider=None
    ):
        """constructor"""
        product.TextProduct.__init__(
            self,
            text,
            utcnow=utcnow,
            ugc_provider=ugc_provider,
            nwsli_provider=nwsli_provider,
        )
        self.reports = []
        self.parse_reports()

    def parse_reports(self):
        """Actually do the parsing of the product that generates the reports
        stored within the self.reports list"""
        txt = (
            self.unixtext
            if self.unixtext[:2] != "\001\n"
            else self.unixtext[2:]
        )

        lines = txt.split("\n")
        # There may be an AWIPSID in line 3 or silly aviation control char
        pos = 3 if len(lines[2]) < 10 or lines[2].startswith("\x1e") else 2
        meat = "".join(lines[pos:])
        for report in meat.split("="):
            if report.strip() == "":
                continue
            res = self.process_pirep(" ".join(report.strip().split()))
            if res is not None and res.valid is not None:
                self.reports.append(res)

    def process_pirep(self, report):
        """Convert this report text into an actual PIREP object"""
        _pr = PilotReport()
        _pr.text = report

        for i, token in enumerate(report.split("/")):
            token = token.strip()
            # First token is always priority
            if i == 0:
                if len(token) > 10:
                    LOG.warning("Aborting as not-PIREP? |%s|", report)
                    return None
                if token.find(" UUA") > 0:
                    _pr.priority = Priority.UUA
                else:
                    _pr.priority = Priority.UA
                parts = token.split()
                if len(parts) == 2:
                    _pr.base_loc = parts[0]
                    if len(_pr.base_loc) == 4 and _pr.base_loc[0] == "K":
                        _pr.base_loc = _pr.base_loc[1:]
                continue
            # Aircraft Type
            if token.startswith("TP "):
                _pr.aircraft_type = token[3:]

            # Location
            if token.startswith("OV "):
                dist = 0
                bearing = 0
                therest = token[3:]
                if len(therest) == 3:
                    loc = _rectify_identifier(therest, self)
                elif therest.startswith("FINAL RWY"):
                    loc = _rectify_identifier(report[:8].split()[0], self)
                elif len(therest) == 4:
                    loc = _rectify_identifier(therest, self)
                elif re.match(OV_OFFSET, therest):
                    d = re.match(OV_OFFSET, therest).groupdict()
                    loc = _rectify_identifier(d["loc"], self)
                    dist = int(d["dist"])
                    bearing = DRCT2DIR[d["dir"]]
                elif therest.find("-") > 0 and re.match(OV_TWOLOC, therest):
                    d = re.match(OV_TWOLOC, therest).groupdict()
                    numbers = re.findall("[0-9]{6}", therest)
                    if numbers:
                        bearing = int(numbers[0][:3])
                        dist = int(numbers[0][3:])
                        loc = _rectify_identifier(d["loc2"], self)
                    else:
                        # Split the distance between the two points
                        lats = []
                        lons = []
                        for loc in [d["loc1"], d["loc2"]]:
                            loc = _rectify_identifier(loc, self)
                            if loc not in self.nwsli_provider:
                                self.warnings.append(
                                    f"Unknown location: {loc} '{report}'"
                                )
                            else:
                                lats.append(self.nwsli_provider[loc]["lat"])
                                lons.append(self.nwsli_provider[loc]["lon"])
                        if len(lats) == 2:
                            _pr.latitude = sum(lats) / 2.0
                            _pr.longitude = sum(lons) / 2.0
                        continue
                elif re.match(OV_LOCDIR, therest):
                    # KFAR330008
                    d = re.match(OV_LOCDIR, therest).groupdict()
                    loc = _rectify_identifier(d["loc"], self)
                    bearing = int(d["dir"])
                    dist = int(d["dist"])
                elif re.match(OV_LATLON, therest):
                    _pr.longitude, _pr.latitude = _parse_lonlat(therest)
                    continue
                elif therest == "O":
                    # Use the first part of the report in this case
                    loc = _rectify_identifier(report[:3], self)
                else:
                    loc = _rectify_identifier(therest[:3], self)

                if loc not in self.nwsli_provider:
                    if _pr.base_loc is None:
                        self.warnings.append(
                            f"Unknown location: {loc} '{report}'"
                        )
                    else:
                        loc = _pr.base_loc
                        if loc not in self.nwsli_provider:
                            self.warnings.append(
                                f"Double-unknown location: {report}"
                            )
                    # So we discard the offset when we go back to the base
                    dist = 0
                    bearing = 0
                _pr.longitude, _pr.latitude = self.compute_loc(
                    loc, dist, bearing
                )
                continue

            # Time
            if token.startswith("TM "):
                numbers = re.findall("[0-9]{4}", token)
                if len(numbers) != 1:
                    self.warnings.append(f"TM parse failed {report}")
                    return None
                hour = int(numbers[0][:2])
                minute = int(numbers[0][2:])
                _pr.valid = self.compute_pirep_valid(hour, minute)
                continue

        return _pr

    def compute_loc(self, loc, dist, bearing):
        """Figure out the lon/lat for this location"""
        if loc is None or loc not in self.nwsli_provider:
            return None, None
        lat = self.nwsli_provider[loc]["lat"]
        lon = self.nwsli_provider[loc]["lon"]
        # shortcut
        if dist == 0:
            return lon, lat
        # Air distances in PIREPs are in nautical miles!
        meters = (units("nautical_mile") * float(dist)).to(units("meter")).m
        northing = meters * math.cos(math.radians(bearing)) / 111111.0
        easting = (
            meters
            * math.sin(math.radians(bearing))
            / math.cos(math.radians(lat))
            / 111111.0
        )
        return lon + easting, lat + northing

    def compute_pirep_valid(self, hour, minute):
        """Based on what utcnow is set to, compute when this is valid"""
        res = self.utcnow.replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        if hour > self.utcnow.hour:
            res -= datetime.timedelta(hours=24)
        return res

    def sql(self, txn):
        """Save the reports to the database via the transaction"""
        for report in self.reports:
            if report.is_duplicate:
                continue
            if report.longitude is None:
                geom = "POINT EMPTY"
            else:
                geom = f"SRID=4326;POINT({report.longitude} {report.latitude})"
            txn.execute(
                "INSERT into pireps(valid, geom, is_urgent, "
                "aircraft_type, report) VALUES (%s, "
                "ST_GeographyFromText(%s), %s, %s, %s)",
                (
                    report.valid,
                    geom,
                    report.priority == Priority.UUA,
                    report.aircraft_type,
                    report.text,
                ),
            )

    def assign_cwsu(self, txn):
        """Use this transaction object to assign CWSUs for the pireps"""
        for report in self.reports:
            if report.latitude is None:
                continue
            txn.execute(
                "select id from cwsu WHERE "
                "st_contains(geom, geomFromEWKT('SRID=4326;POINT(%s %s)'))",
                (report.longitude, report.latitude),
            )
            if txn.rowcount > 0:
                report.cwsu = txn.fetchone()["id"]

    def get_jabbers(self, _uri, _uri2=None):
        """get jabber messages"""
        res = []
        for report in self.reports:
            if report.is_duplicate:
                continue
            jmsg = {
                "priority": "Urgent"
                if report.priority == Priority.UUA
                else "Routine",
                "ts": report.valid.strftime("%H%M"),
                "report": html_escape(report.text),
                "color": (
                    "#ff0000" if report.priority == Priority.UUA else "#00ff00"
                ),
            }
            plain = "%(priority)s pilot report at %(ts)sZ: %(report)s" % jmsg
            html = (
                "<span style='color:%(color)s;'>%(priority)s pilot "
                "report</span> at %(ts)sZ: %(report)s"
            ) % jmsg
            xtra = {
                "channels": (
                    f"{report.priority}.{report.cwsu},{report.priority}.PIREP"
                ),
                "ptype": report.priority,
                "category": "PIREP",
                "twitter": plain[:140],
                "valid": report.valid.strftime("%Y%m%dT%H:%M:00"),
            }
            if report.latitude is not None:
                xtra[
                    "geometry"
                ] = f"POINT({report.longitude} {report.latitude})"
            res.append([plain, html, xtra])
        return res


def parser(buf, utcnow=None, ugc_provider=None, nwsli_provider=None):
    """A parser implementation"""
    return Pirep(
        buf,
        utcnow=utcnow,
        ugc_provider=ugc_provider,
        nwsli_provider=nwsli_provider,
    )
