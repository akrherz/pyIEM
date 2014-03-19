
import re
import datetime
import pytz

_re = "(/([A-Z])\.([A-Z]+)\.([A-Z]+)\.([A-Z]+)\.([A-Z])\.([0-9]+)\.([0-9,T,Z]+)-([0-9,T,Z]+)/)"

_classDict = {'O': 'Operational',
              'T': 'Test',
              'E': 'Experimental',
              'X': 'Experimental VTEC'}

_actionDict = {'NEW': 'issues',
               'CON': 'continues',
               'EXA': 'extends area of',
               'EXT': 'extends time of',
               'EXB': 'extends area+time of',
               'UPG': 'issues upgrade to',
               'CAN': 'cancels',
               'EXP': 'expires',
               'ROU': 'routine',
               'COR': 'corrects'}

_sigDict = {'W': 'Warning',
            'Y': 'Advisory',
            'A': 'Watch',
            'S': 'Statement',
            'O': 'Outlook',
            'N': 'Synopsis',
            'F': 'Forecast'}

_phenDict = {
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
'SR': 'Storm',
'SU': 'High Surf',
'SV': 'Severe Thunderstorm',
'SW': 'Small Craft for Hazardous',
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
'ZR': 'Freezing Rain',
}

def parse(text):
    """ I look for and return vtec objects as I find them """
    vtec = []
    tokens = re.findall(_re, text)
    for t in tokens:
        vtec.append( VTEC(t) )
    return vtec

def contime(s):
    if ( len(re.findall("0000*T",s)) > 0 ):
        return None
    try:
        ts = datetime.datetime.strptime(s, '%y%m%dT%H%MZ')
        return ts.replace( tzinfo=pytz.timezone('UTC') )
    except Exception, err:
        print err
        return None
    
class VTEC:

    def __init__(self, tokens):
        self.line   = tokens[0]
        self.status = tokens[1]
        self.action = tokens[2]
        self.office = tokens[3][1:]
        self.office4 = tokens[3]
        self.phenomena = tokens[4]
        self.significance = tokens[5]
        self.ETN = int(tokens[6])
        self.begints = contime( tokens[7] )
        self.endts   = contime( tokens[8] )

    def get_end_string(self, prod):
        ''' Return an appropriate end string for this VTEC '''
        if self.endts is None:
            return 'until further notice'
        fmt = "%b %-d, %-I:%M %p %Z"
        utcnow = datetime.datetime.utcnow().replace(tzinfo=pytz.timezone("UTC"))
        utcnow += datetime.timedelta(hours=1)
        if self.endts < utcnow:
            fmt = '%-I:%M %p %Z'
        localts = self.endts.astimezone( prod.tz )
        return "till %s" % (localts.strftime(fmt),)

    def get_begin_string(self, prod):
        ''' Return an appropriate beginning string for this VTEC '''
        if self.begints is None:
            return ''
        fmt = "%b %-d, %-I:%M %p %Z"
        utcnow = datetime.datetime.utcnow().replace(tzinfo=pytz.timezone("UTC"))
        utcnow += datetime.timedelta(hours=1)
        if self.begints < utcnow:
            fmt = '%-I:%M %p %Z'
        localts = self.begints.astimezone( prod.z )
        return "valid at %s" % (localts.strftime(fmt),)

    def url(self, year):
        """ Generate a VTEC url string needed """
        return "%s-%s-%s-%s-%s-%s-%04i" % (year, self.status, self.action,
               self.office4, self.phenomena, self.significance, self.ETN)

    def getID(self, year):
        ''' Return a custom string identifier for this VTEC product 
        This is used by the Live client '''
        return '%s-%s-%s-%s-%04i' % (year, self.office4,
                                     self.phenomena, self.significance, 
                                     self.ETN)

    def __str__(self):
        return self.line

    def product_string(self):

        q = _actionDict.get( self.action , "unknown %s" % (self.action,))
        p = _phenDict.get(self.phenomena, "Unknown %s" % (self.phenomena,))
        a = _sigDict.get(self.significance, "Unknown %s" % (self.significance,))
        # Hack for special FW case
        if self.significance == 'A' and self.phenomena == 'FW':
            p = "Fire Weather"
        return "%s %s %s" % (q, p,a)

