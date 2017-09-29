"""Support NWS VTEC encoding"""
from __future__ import print_function
import re
import datetime

import pytz

VTEC_RE = (r"(/([A-Z])\.([A-Z]+)\.([A-Z]+)\.([A-Z]+)\.([A-Z])\."
           r"([0-9]+)\.([0-9,T,Z]+)-([0-9,T,Z]+)/)")

VTEC_CLASS = {
    'O': 'Operational',
    'T': 'Test',
    'E': 'Experimental',
    'X': 'Experimental VTEC'}

VTEC_ACTION = {
    'NEW': 'issues',
    'CON': 'continues',
    'EXA': 'expands area to include',
    'EXT': 'extends time of',
    'EXB': 'extends time and expands area to include',
    'UPG': 'issues upgrade to',
    'CAN': 'cancels',
    'EXP': 'expires',
    'ROU': 'routine',
    'COR': 'corrects'}

VTEC_SIGNIFICANCE = {
    'W': 'Warning',
    'Y': 'Advisory',
    'A': 'Watch',
    'S': 'Statement',
    'O': 'Outlook',
    'N': 'Synopsis',
    'F': 'Forecast'}

VTEC_PHENOMENA = {
    'AF': 'Ashfall',
    'AS': 'Air Stagnation',
    'BH': 'Beach Hazard',
    'BS': 'Blowing Snow',
    'BW': 'Brisk Wind',
    'BZ': 'Blizzard',
    'CF': 'Coastal Flood',
    'DS': 'Dust Storm',
    'DU': 'Blowing Dust',
    'EC': 'Extreme Cold',
    'EH': 'Excessive Heat',
    'EW': 'Extreme Wind',
    'FA': 'Areal Flood',
    'FF': 'Flash Flood',
    'FG': 'Dense Fog',
    'FL': 'Flood',
    'FR': 'Frost',
    'FW': 'Red Flag',
    'FZ': 'Freeze',
    'GL': 'Gale',
    'HF': 'Hurricane Force Wind',
    'HI': 'Inland Hurricane',
    'HS': 'Heavy Snow',
    'HT': 'Heat',
    'HU': 'Hurricane',
    'HW': 'High Wind',
    'HY': 'Hydrologic',
    'HZ': 'Hard Freeze',
    'IP': 'Sleet',
    'IS': 'Ice Storm',
    'LB': 'Lake Effect Snow and Blowing Snow',
    'LE': 'Lake Effect Snow',
    'LO': 'Low Water',
    'LS': 'Lakeshore Flood',
    'LW': 'Lake Wind',
    'MA': 'Marine',
    'MF': 'Marine Dense Fog',
    'MS': 'Marine Dense Smoke',
    'MH': 'Marine Ashfall',
    'RB': 'Small Craft for Rough',
    'RP': 'Rip Currents',
    'SB': 'Snow and Blowing',
    'SC': 'Small Craft',
    'SE': 'Hazardous Seas',
    'SI': 'Small Craft for Winds',
    'SM': 'Dense Smoke',
    'SN': 'Snow',
    'SQ': 'Snow Squall',
    'SR': 'Storm',
    'SS': 'Storm Surge',
    'SU': 'High Surf',
    'SV': 'Severe Thunderstorm',
    'SW': 'Small Craft for Hazardous Seas',
    'TI': 'Inland Tropical Storm',
    'TO': 'Tornado',
    'TR': 'Tropical Storm',
    'TS': 'Tsunami',
    'TY': 'Typhoon',
    'UP': 'Ice Accretion',
    'WC': 'Wind Chill',
    'WI': 'Wind',
    'WS': 'Winter Storm',
    'WW': 'Winter Weather',
    'ZF': 'Freezing Fog',
    'ZR': 'Freezing Rain'}

# Taken from http://www.weather.gov/help-map
NWS_COLORS = {
    'AS.Y': '#808080',
    'AF.Y': '#696969',
    'AF.W': '#A9A9A9',
    'BH.S': '#40E0D0',
    'BZ.W': '#FF4500',
    'BZ.A': '#ADFF2F',
    'DU.Y': '#BDB76B',
    'BW.Y': '#D8BFD8',
    'CF.Y': '#7CFC00',
    'CF.S': '#6B8E23',
    'CF.W': '#228B22',
    'CF.A': '#66CDAA',
    'DS.W': '#FFE4C4',
    'FG.Y': '#708090',
    'SM.Y': '#F0E68C',
    'DU.W': '#FFE4C4',
    'EH.W': '#C71585',
    'EH.Y': '#800000',
    'EC.W': '#0000FF',
    'EC.A': '#0000FF',
    'EW.W': '#FF8C00',
    'FW.A': '#FFDEAD',
    'FF.S': '#8B0000',
    'FF.W': '#8B0000',
    'FF.A': '#2E8B57',
    'FL.Y': '#00FF7F',
    'FL.S': '#00FF00',
    'FL.W': '#00FF00',
    'FL.A': '#2E8B57',
    'FZ.W': '#483D8B',
    'FZ.A': '#00FFFF',
    'ZF.Y': '#008080',
    'ZR.Y': '#DA70D6',
    'FR.Y': '#6495ED',
    'GL.W': '#DDA0DD',
    'GL.A': '#FFC0CB',
    'HZ.W': '#9400D3',
    'HZ.A': '#4169E1',
    'SE.W': '#D8BFD8',
    'SE.A': '#483D8B',
    'HT.Y': '#FF7F50',
    'SU.Y': '#BA55D3',
    'SU.W': '#228B22',
    'HW.W': '#DAA520',
    'HW.A': '#B8860B',
    'HF.W': '#CD5C5C',
    'HF.A': '#9932CC',
    'HU.W': '#DC143C',
    'HU.A': '#FF00FF',
    'HY.Y': '#00FF7F',
    'IS.W': '#8B008B',
    'LE.Y': '#48D1CC',
    'LE.W': '#008B8B',
    'LE.A': '#87CEFA',
    'LW.Y': '#D2B48C',
    'LS.Y': '#7CFC00',
    'LS.S': '#6B8E23',
    'LS.W': '#228B22',
    'LS.A': '#66CDAA',
    'LO.Y': '#A52A2A',
    'MA.S': '#FFDAB9',
    'FW.W': '#FF1493',
    'RP.S': '#40E0D0',
    'SQ.W': '#C71585',
    'SV.W': '#FFA500',
    'SV.A': '#DB7093',
    'SC.Y': '#D8BFD8',
    'SW.Y': '#D8BFD8',
    'RB.Y': '#D8BFD8',
    'SI.Y': '#D8BFD8',
    'MA.W': '#FFA500',
    'TO.W': '#FF0000',
    'TO.A': '#FFFF00',
    'TR.S': '#FFE4B5',
    'TR.W': '#B22222',
    'TR.A': '#F08080',
    'TS.Y': '#D2691E',
    'TS.W': '#FD6347',
    'TS.A': '#FF00FF',
    'TY.W': '#DC143C',
    'TY.A': '#FF00FF',
    'WI.Y': '#D2B48C',
    'WC.Y': '#AFEEEE',
    'WC.W': '#B0C4DE',
    'WC.A': '#5F9EA0',
    'WS.W': '#FF69B4',
    'WS.A': '#4682B4',
    'WW.Y': '#7B68EE',
}


def parse(text):
    """ I look for and return vtec objects as I find them """
    vtec = []
    tokens = re.findall(VTEC_RE, text)
    for token in tokens:
        vtec.append(VTEC(token))
    return vtec


def contime(text):
    """Represent the fun that is 0000 time in VTEC"""
    if re.findall("0000*T", text):
        return None
    try:
        ts = datetime.datetime.strptime(text, '%y%m%dT%H%MZ')
        return ts.replace(tzinfo=pytz.utc)
    except Exception as err:
        print(err)
        return None


def get_ps_string(phenomena, significance):
    """Return the combination of Phenomena + Significance as string"""
    pstr = VTEC_PHENOMENA.get(phenomena, "Unknown %s" % (phenomena,))
    astr = VTEC_SIGNIFICANCE.get(significance, "Unknown %s" % (significance,))
    # Hack for special FW case
    if significance == 'A' and phenomena == 'FW':
        pstr = "Fire Weather"
    return "%s %s" % (pstr, astr)


def get_action_string(action):
    """Return the action string"""
    return VTEC_ACTION.get(action, "unknown %s" % (action,))


class VTEC(object):
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

    def get_end_string(self, prod):
        """ Return an appropriate end string for this VTEC """
        if self.action in ['CAN', 'EXP']:
            return ''
        if self.endts is None:
            return 'until further notice'
        fmt = "%b %-d, %-I:%M %p"
        if self.endts < (prod.valid + datetime.timedelta(hours=1)):
            fmt = '%-I:%M %p'
        localts = self.endts.astimezone(prod.tz)
        # A bit of complexity as offices may not implement daylight saving
        if prod.z.endswith("ST") and localts.dst():
            localts -= datetime.timedelta(hours=1)
        return "till %s %s" % (localts.strftime(fmt), prod.z)

    def get_begin_string(self, prod):
        """Return an appropriate beginning string for this VTEC"""
        if self.begints is None:
            return ''
        fmt = "%b %-d, %-I:%M %p"
        if self.begints < (prod.valid + datetime.timedelta(hours=1)):
            fmt = '%-I:%M %p'
        localts = self.begints.astimezone(prod.tz)
        # A bit of complexity as offices may not implement daylight saving
        if prod.z.endswith("ST") and localts.dst():
            localts -= datetime.timedelta(hours=1)
        return "valid at %s %s" % (localts.strftime(fmt), prod.z)

    def url(self, year):
        """ Generate a VTEC url string needed """
        return ("%s-%s-%s-%s-%s-%s-%04i"
                ) % (year, self.status, self.action,
                     self.office4, self.phenomena, self.significance, self.etn)

    def get_id(self, year):
        """Return a custom string identifier for this VTEC product

        This is used by the Live client
        """
        return "%s-%s-%s-%s-%04i" % (year, self.office4,
                                     self.phenomena, self.significance,
                                     self.etn)

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
