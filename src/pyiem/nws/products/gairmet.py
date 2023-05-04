"""Aviation Weather Center Graphical-AIRMET G-AIRMET.

Break-up the XML G-AIRMET into atomic pieces.
"""
from datetime import datetime, timezone
from xml.dom import minidom

import defusedxml.ElementTree as ET
from shapely.geometry import LineString, MultiLineString, Polygon

from pyiem.models.gairmet import (
    AIRMETRecord,
    FreezingLevelRecord,
    GAIRMETModel,
)
from pyiem.nws import product

GMET = {
    "LWGE86": "GMTIFR",
    "LWHE00": "GMTTRB",
    "LWIE00": "GMTICE",
}
NS = {
    "": "http://nws.weather.gov/schemas/USWX/1.0",
    "aixm": "http://www.aixm.aero/schema/5.1.1",
    "gml": "http://www.opengis.net/gml/3.2",
    "om": "http://www.opengis.net/om/2.0",
    "xlink": "http://www.w3.org/1999/xlink",
}


def parseUTC(s):
    """Parse an ISO-ish string into UTC timestamp"""
    return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").replace(
        tzinfo=timezone.utc
    )


def prettify(elem):
    """Return a pretty-printed XML string for the Element."""
    rough_string = ET.tostring(elem, "utf-8")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def process_airmet(prod, airmet):
    """Process an AIRMET element"""
    gml_id = airmet.attrib["{http://www.opengis.net/gml/3.2}id"]
    label = gml_id.split("-")[-2]  # sigh
    pts = airmet.find(".//gml:posList", NS).text.strip().split()
    valid_at = parseUTC(airmet.find(".//gml:timePosition", NS).text)
    elem = airmet.find("airmetRecordStatus", NS)
    status = elem.attrib["{http://www.w3.org/1999/xlink}title"]
    elem = airmet.find("hazardType", NS)
    hazardtype = elem.attrib["{http://www.w3.org/1999/xlink}title"]
    xy = [(float(x), float(y)) for x, y in zip(pts[1::2], pts[::2])]
    if gml_id.startswith("FZLVL") or gml_id.startswith("M_FZLVL"):
        ls = LineString(xy)
        ul = int(airmet.find(".//aixm:upperLimit", NS).text)
        ll = int(airmet.find(".//aixm:lowerLimit", NS).text)
        # Need to search for previous records to see if we have
        # a dupe
        found = False
        for fzl in prod.data.freezing_levels:
            if fzl.valid_at == valid_at and fzl.level == ul:
                fzl.geom = MultiLineString([*fzl.geom.geoms, ls])
                found = True
                break
        if not found:
            prod.data.freezing_levels.append(
                FreezingLevelRecord(
                    gml_id=gml_id,
                    level=None if ul != ll else ll,
                    lower_level=ll,
                    upper_level=ul,
                    valid_at=valid_at,
                    geom=MultiLineString([ls]),
                )
            )
        return

    # get the GML data
    poly = Polygon(xy)
    # Get the weather phenomena
    phenomena = []
    elem = airmet.find("clouds", NS)
    if elem is not None:
        if elem.text == "true":
            phenomena.append("clouds")
    for elem in airmet.findall(".//weatherPhenomenon", NS):
        phenomena.append(elem.attrib["{http://www.w3.org/1999/xlink}title"])
    # seems to be always hard coded.
    elem = airmet.find(".//windSpeedGreaterThan", NS)
    if elem is not None:
        phenomena.append(f"Surface Wind Speed Greater Than {elem.text}")
    # LLWS
    elem = airmet.find(".//lowlevelWindshear", NS)
    if elem is not None and elem.text == "true":
        phenomena.append("Low Level Wind Shear below 2000")

    # Turbulence
    elem = airmet.find(".//turbulence", NS)
    if elem is not None:
        vol = elem.find(".//aixm:AirspaceVolume", NS)
        if vol is not None:
            ul = vol.find(".//aixm:upperLimit", NS).text
            ll = vol.find(".//aixm:lowerLimit", NS).text
            tr = elem.find(".//turbRangeStart", NS)
            if tr is not None:
                tt = tr.attrib["{http://www.w3.org/1999/xlink}title"]
                phenomena.append(f"Turbulence {tt} from {ll} to {ul}")

    # Icing
    elem = airmet.find(".//icing", NS)
    if elem is not None:
        vol = elem.find(".//aixm:AirspaceVolume", NS)
        if vol is not None:
            ul = vol.find(".//aixm:upperLimit", NS).text
            ll = "--"
            llelem = airmet.find(".//aixm:lowerLimit", NS)
            if llelem is not None:
                ll = int(llelem.text)
            tr = elem.find(".//icingRangeStart", NS)
            if tr is not None:
                tt = tr.attrib["{http://www.w3.org/1999/xlink}title"]
                phenomena.append(f"Icing {tt} from {ll} to {ul}")

    prod.data.airmets.append(
        AIRMETRecord(
            gml_id=gml_id,
            label=label,
            status=status,
            hazard_type=hazardtype,
            valid_at=valid_at,
            geom=poly,
            weather_conditions=phenomena,
        )
    )


class GAIRMET(product.TextProduct):
    """Class for parsing the G-AIRMET product"""

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
            parse_segments=False,
        )
        # Fix the afos id
        self.afos = GMET[self.wmo]
        self.data = None
        self.parsing()

    def sql(self, cursor):
        """Persist this information to the database"""
        for airmet in self.data.airmets:
            cursor.execute(
                """
                INSERT into airmets (
                    gml_id, label, product_id, valid_from, valid_to, valid_at,
                    status, hazard_type, weather_conditions, issuetime, geom)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    ST_GeomFromText(%s, 4326))
                """,
                (
                    airmet.gml_id,
                    airmet.label,
                    self.get_product_id(),
                    self.data.valid_from,
                    self.data.valid_to,
                    airmet.valid_at,
                    airmet.status,
                    airmet.hazard_type,
                    airmet.weather_conditions,
                    self.data.issuetime,
                    airmet.geom.wkt,
                ),
            )
        for fzlvl in self.data.freezing_levels:
            cursor.execute(
                """
                INSERT into airmet_freezing_levels (gml_id, product_id,
                valid_at, level, lower_level, upper_level, geom)
                VALUES (%s, %s, %s, %s, %s, %s, ST_GeomFromText(%s, 4326))
                """,
                (
                    fzlvl.gml_id,
                    self.get_product_id(),
                    fzlvl.valid_at,
                    fzlvl.level,
                    fzlvl.lower_level,
                    fzlvl.upper_level,
                    fzlvl.geom.wkt,
                ),
            )

    def parsing(self):
        """Attempt to parse out what we have found"""
        pos = self.unixtext.find("<G-AIRMET")
        if pos == -1:
            raise Exception("Product is not a G-AIRMET")
        root = ET.fromstring(self.unixtext[pos:])
        e = root.find(".//gml:TimeInstant[@gml:id='G-AIRMETVALIDFROM']", NS)
        valid_from = parseUTC(e.find("gml:timePosition", NS).text)
        e = root.find(".//gml:TimeInstant[@gml:id='G-AIRMETVALIDTO']", NS)
        valid_to = parseUTC(e.find("gml:timePosition", NS).text)
        e = root.find(".//gml:TimeInstant[@gml:id='G-AIRMETISSUETIME']", NS)
        issuetime = parseUTC(e.find("gml:timePosition", NS).text)

        self.data = GAIRMETModel(
            valid_from=valid_from,
            valid_to=valid_to,
            issuetime=issuetime,
        )

        for airmet in root.findall(".//US-AIRMETRecord", NS):
            try:
                process_airmet(self, airmet)
            except Exception as exp:
                msg = (
                    f"{self.get_product_id()}\n"
                    f"Error parsing AIRMET: {exp}\n"
                    f"{prettify(airmet)}\n"
                )
                self.warnings.append(msg)


def parser(buf, utcnow=None, ugc_provider=None, nwsli_provider=None):
    """Parse a G-AIRMET product

    Args:
      buf (str): What we want to parse
    """
    return GAIRMET(buf, utcnow, ugc_provider, nwsli_provider)
