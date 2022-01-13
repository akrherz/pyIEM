"""Support NWS VTEC encoding"""
import re
from datetime import timezone, timedelta, datetime

from pyiem.util import LOG

VTEC_RE = (
    r"(/([A-Z])\.([A-Z]+)\.([A-Z]+)\.([A-Z]+)\.([A-Z])\."
    r"([0-9]+)\.([0-9TZ]+)-([0-9TZ]+)/)"
)

VTEC_CLASS = {
    "O": "Operational",
    "T": "Test",
    "E": "Experimental",
    "X": "Experimental VTEC",
}

VTEC_ACTION = {
    "NEW": "issues",
    "CON": "continues",
    "EXA": "expands area to include",
    "EXT": "extends time of",
    "EXB": "extends time and expands area to include",
    "UPG": "issues upgrade to",
    "CAN": "cancels",
    "EXP": "expires",
    "ROU": "routine",
    "COR": "corrects",
}

VTEC_SIGNIFICANCE = {
    "W": "Warning",
    "Y": "Advisory",
    "A": "Watch",
    "S": "Statement",
    "O": "Outlook",
    "N": "Synopsis",
    "F": "Forecast",
}

# https://www.nws.noaa.gov/directives/sym/pd01017003curr.pdf
VTEC_PHENOMENA = {
    "AF": "Ashfall",
    "AS": "Air Stagnation",
    "BH": "Beach Hazard",
    "BS": "Blowing Snow",
    "BW": "Brisk Wind",
    "BZ": "Blizzard",
    "CF": "Coastal Flood",
    "DF": "Debris Flow",
    "DS": "Dust Storm",
    "DU": "Blowing Dust",
    "EC": "Extreme Cold",
    "EH": "Excessive Heat",
    "EW": "Extreme Wind",
    "FA": "Flood",
    "FF": "Flash Flood",
    "FG": "Dense Fog",
    "FL": "Flood",
    "FR": "Frost",
    "FW": "Red Flag",
    "FZ": "Freeze",
    "GL": "Gale",
    "HF": "Hurricane Force Wind",
    "HI": "Inland Hurricane",
    "HS": "Heavy Snow",
    "HT": "Heat",
    "HU": "Hurricane",
    "HW": "High Wind",
    "HY": "Hydrologic",
    "HZ": "Hard Freeze",
    "IP": "Sleet",
    "IS": "Ice Storm",
    "LB": "Lake Effect Snow and Blowing Snow",
    "LE": "Lake Effect Snow",
    "LO": "Low Water",
    "LS": "Lakeshore Flood",
    "LW": "Lake Wind",
    "MA": "Marine",
    "MF": "Marine Dense Fog",
    "MH": "Marine Ashfall",
    "MS": "Marine Dense Smoke",
    "RB": "Small Craft for Rough",
    "RP": "Rip Currents",
    "SB": "Snow and Blowing",
    "SC": "Small Craft",
    "SE": "Hazardous Seas",
    "SI": "Small Craft for Winds",
    "SM": "Dense Smoke",
    "SN": "Snow",
    "SQ": "Snow Squall",
    "SR": "Storm",
    "SS": "Storm Surge",
    "SU": "High Surf",
    "SV": "Severe Thunderstorm",
    "SW": "Small Craft for Hazardous Seas",
    "TI": "Inland Tropical Storm",
    "TO": "Tornado",
    "TR": "Tropical Storm",
    "TS": "Tsunami",
    "TY": "Typhoon",
    "UP": "Ice Accretion",
    "WC": "Wind Chill",
    "WI": "Wind",
    "WS": "Winter Storm",
    "WW": "Winter Weather",
    "ZF": "Freezing Fog",
    "ZR": "Freezing Rain",
    "ZY": "Freezing Spray",
}

# Taken from http://www.weather.gov/help-map
# Not all of these are an exact match.
NWS_COLORS = {
    "AF.W": "#A9A9A9",
    "AF.Y": "#696969",
    "AS.Y": "#808080",
    "BH.S": "#40E0D0",
    "BW.Y": "#D8BFD8",
    "BZ.A": "#ADFF2F",
    "BZ.W": "#FF4500",
    "CF.A": "#66CDAA",
    "CF.S": "#6B8E23",
    "CF.W": "#228B22",
    "CF.Y": "#7CFC00",
    "DS.W": "#FFE4C4",
    "DS.Y": "#BDB76B",
    "DU.W": "#FFE4C4",
    "DU.Y": "#BDB76B",
    "EC.A": "#0000FF",
    "EC.W": "#0000FF",
    "EH.A": "#800000",
    "EH.W": "#C71585",
    "EH.Y": "#800000",
    "EW.W": "#FF8C00",
    "FA.A": "#2E8B57",
    "FA.W": "#00FF00",
    "FA.Y": "#00FF7F",
    "FF.A": "#2E8B57",
    "FF.S": "#8B0000",
    "FF.W": "#8B0000",
    "FG.Y": "#708090",
    "FL.A": "#2E8B57",
    "FL.S": "#00FF00",
    "FL.W": "#00FF00",
    "FL.Y": "#00FF7F",
    "FR.Y": "#6495ED",
    "FW.A": "#FFDEAD",
    "FW.W": "#FF1493",
    "FZ.A": "#00FFFF",
    "FZ.W": "#483D8B",
    "GL.A": "#FFC0CB",
    "GL.W": "#DDA0DD",
    "HF.A": "#9932CC",
    "HF.W": "#CD5C5C",
    "HT.Y": "#FF7F50",
    "HU.A": "#FF00FF",
    "HU.S": "#FFE4B5",
    "HU.W": "#DC143C",
    "HW.A": "#B8860B",
    "HW.W": "#DAA520",
    "HY.Y": "#00FF7F",
    "HZ.A": "#4169E1",
    "HZ.W": "#9400D3",
    "IS.W": "#8B008B",
    "LE.A": "#87CEFA",
    "LE.W": "#008B8B",
    "LE.Y": "#48D1CC",
    "LO.Y": "#A52A2A",
    "LS.A": "#66CDAA",
    "LS.S": "#6B8E23",
    "LS.W": "#228B22",
    "LS.Y": "#7CFC00",
    "LW.Y": "#D2B48C",
    "MA.S": "#FFDAB9",
    "MA.W": "#FFA500",
    "MF.Y": "#708090",
    "RB.Y": "#D8BFD8",
    "RP.S": "#40E0D0",
    "SC.Y": "#D8BFD8",
    "SE.A": "#483D8B",
    "SE.W": "#D8BFD8",
    "SI.Y": "#D8BFD8",
    "SM.Y": "#F0E68C",
    "SQ.W": "#C71585",
    "SR.A": "#FFE4B5",
    "SR.W": "#9400D3",
    "SS.A": "#DB7FF7",
    "SS.W": "#C0C0C0",
    "SU.W": "#228B22",
    "SU.Y": "#BA55D3",
    "SV.A": "#DB7093",
    "SV.W": "#FFA500",
    "SW.Y": "#D8BFD8",
    "TO.A": "#FFFF00",
    "TO.W": "#FF0000",
    "TR.A": "#F08080",
    "TR.S": "#FFE4B5",
    "TR.W": "#B22222",
    "TS.A": "#FF00FF",
    "TS.W": "#FD6347",
    "TS.Y": "#D2691E",
    "TY.A": "#FF00FF",
    "TY.W": "#DC143C",
    "UP.A": "#4682B4",
    "UP.W": "#8B008B",
    "UP.Y": "#8B008B",
    "WC.A": "#5F9EA0",
    "WC.W": "#B0C4DE",
    "WC.Y": "#AFEEEE",
    "WI.Y": "#D2B48C",
    "WS.A": "#4682B4",
    "WS.W": "#FF69B4",
    "WW.Y": "#7B68EE",
    "ZF.Y": "#008080",
    "ZR.Y": "#DA70D6",
}


def parse(text):
    """I look for and return vtec objects as I find them"""
    vtec = []
    tokens = re.findall(VTEC_RE, text)
    for token in tokens:
        vtec.append(VTEC(token))
    return vtec


def contime(text):
    """Convert text into a UTC datetime."""
    # The 0000 is the standard VTEC undefined time
    if text.startswith("0000"):
        return None
    try:
        ts = datetime.strptime(text, "%y%m%dT%H%MZ")
    except Exception as err:
        LOG.exception(err)
        return None
    # NWS has a bug sometimes whereby 1969 or 1970s timestamps are emitted
    if ts.year < 1971:
        return None
    return ts.replace(tzinfo=timezone.utc)


def get_ps_string(phenomena, significance):
    """Return the combination of Phenomena + Significance as string"""
    pstr = VTEC_PHENOMENA.get(phenomena, f"Unknown {phenomena}")
    astr = VTEC_SIGNIFICANCE.get(significance, f"Unknown {significance}")
    # Hack for special FW case
    if significance == "A" and phenomena == "FW":
        pstr = "Fire Weather"
    return f"{pstr} {astr}"


def get_action_string(action):
    """Return the action string"""
    return VTEC_ACTION.get(action, f"unknown {action}")


class VTEC:
    """A single VTEC encoding instance"""

    def __init__(self, tokens):
        self.line = tokens[0]
        self.status = tokens[1]
        self.action = tokens[2]
        self.office = tokens[3][1:]
        self.office4 = tokens[3]
        self.phenomena = tokens[4]
        self.significance = tokens[5]
        self.etn = int(tokens[6])
        self.begints = contime(tokens[7])
        self.endts = contime(tokens[8])
        # Not explicitly defined, but set later by product parsing logic
        self.year = None

    def s3(self):
        """Return a commonly used string representation."""
        return f"{self.phenomena}.{self.significance}.{self.etn}"

    def s2(self):
        """Return a commonly used string representation."""
        return f"{self.phenomena}.{self.significance}"

    def get_end_string(self, prod):
        """Return an appropriate end string for this VTEC"""
        if self.action in ["CAN", "EXP"]:
            return ""
        if self.endts is None:
            return "until further notice"
        fmt = "%b %-d, %-I:%M %p"
        if self.endts < (prod.valid + timedelta(hours=1)):
            fmt = "%-I:%M %p"
        if prod.tz is None:
            fmt = "%b %-d, %-H:%M"
        localts = self.endts
        if prod.tz is not None:
            localts = self.endts.astimezone(prod.tz)
        # A bit of complexity as offices may not implement daylight saving
        if prod.z is not None and prod.z.endswith("ST") and localts.dst():
            localts -= timedelta(hours=1)
        return "till %s %s" % (
            localts.strftime(fmt),
            prod.z if prod.z is not None else "UTC",
        )

    def get_begin_string(self, prod):
        """Return an appropriate beginning string for this VTEC"""
        if self.begints is None:
            return ""
        fmt = "%b %-d, %-I:%M %p"
        if self.begints < (prod.valid + timedelta(hours=1)):
            fmt = "%-I:%M %p"
        localts = self.begints.astimezone(prod.tz)
        # A bit of complexity as offices may not implement daylight saving
        if prod.z.endswith("ST") and localts.dst():
            localts -= timedelta(hours=1)
        return "valid at %s %s" % (localts.strftime(fmt), prod.z)

    def url(self, year):
        """Generate a VTEC url string needed"""
        return ("%s-%s-%s-%s-%s-%s-%04i") % (
            year if self.year is None else self.year,
            self.status,
            self.action,
            self.office4,
            self.phenomena,
            self.significance,
            self.etn,
        )

    def get_id(self, year):
        """Return a custom string identifier for this VTEC product

        This is used by the Live client
        """
        return "%s-%s-%s-%s-%04i" % (
            year if self.year is None else self.year,
            self.office4,
            self.phenomena,
            self.significance,
            self.etn,
        )

    def __str__(self):
        """Return string representation"""
        return self.line

    def get_ps_string(self):
        """Return the combination of Phenomena + Significance as string"""
        return get_ps_string(self.phenomena, self.significance)

    def get_action_string(self):
        """Return the action string"""
        return get_action_string(self.action)

    def product_string(self):
        """Return the combination of action and phenomena+significance"""
        return "%s %s" % (self.get_action_string(), self.get_ps_string())
