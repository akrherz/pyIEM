
import re
import datetime
from pyiem import iemtz
from pyiem.nws.nwsli import NWSLI

#         nwsli        sev         cause      
_re = "(/([A-Z0-9]{5})\.([N0123U])\.([A-Z]{2})\.([0-9TZ]+)\.([0-9TZ]+)\.([0-9TZ]+)\.([A-Z]{2})/)"

_statusDict = {'00': 'is not applicable',
               'NO': 'is not expected',
               'NR': 'may be expected',
               'UU': 'is not available'}

_causeDict = {'ER': 'Excessive Rainfall',
              'SM': 'Snowmelt',
              'RS': 'Rain and Snowmelt',
              'DM': 'Dam or Levee Failure',
              'GO': 'Glacier-Dammed Lake Outburst',
              'IJ': 'Ice Jam',
              'IC': 'Rain and/or Snowmelt and/or Ice Jam',
              'FS': 'Upstream Flooding plus Storm Surge',
              'FT': 'Upstream Flooding plus Tidal Effects',
              'ET': 'Elevated Upstream Flow plus Tidal Effects',
              'WT': 'Wind and/or Tidal Effects',
              'DR': 'Upstream Dam or Reservoir Release',
              'MC': 'Other Multiple Causes',
              'OT': 'Other Effects',
              'UU': 'Unknown'}

_severityDict = {'N': 'None',
                 '0': 'None',
                 '1': 'Minor',
                 '2': 'Moderate',
                 '3': 'Major',
                 'U': 'Unknown'}


def parse(text, nwsli_provider={}):
    """ I look for and return hvtec objects as I find them """
    hvtec = []
    tokens = re.findall(_re, text)
    for t in tokens:
        hvtec.append( HVTEC(t, nwsli_provider) )
    return hvtec

def contime(s):
    if ( len(re.findall("0000*T",s)) > 0 ):
        return None
    try:
        ts = datetime.datetime.strptime(s, '%y%m%dT%H%MZ')
        return ts.replace( tzinfo=iemtz.UTC() )
    except Exception, err:
        print err
        return None

class HVTEC:

    def __init__(self, tokens, nwsli_provider={}):
        ''' Constructor '''
        self.line    = tokens[0]
        self.nwsli   = nwsli_provider.get(tokens[1], NWSLI(tokens[1]))
        self.severity = tokens[2]
        self.cause = tokens[3]
        self.beginTS = contime( tokens[4] )
        self.crestTS = contime( tokens[5] )
        self.endTS   = contime( tokens[6] )
        self.record = tokens[7]
        

    def __str__(self):
        return self.raw
