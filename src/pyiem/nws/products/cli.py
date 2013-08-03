'''
Parser for NWS Climate Report text format
'''
import re
import datetime

from pyiem.nws.product import TextProduct

TEMP_RE = re.compile(r"""TEMPERATURE \(F\)\s+
.*
\s+MAXIMUM\s+([\-0-9]+).*
\s+MINIMUM\s+([\-0-9]+)""", re.M )

PRECIP_RE = re.compile(r"""PRECIPITATION \(IN\)\s+
\s+(?:YESTERDAY|TODAY)\s+([0-9\.]+).*
\s+MONTH TO DATE\s+([0-9\.]+)""", re.M )

DATE_RE = re.compile(r"CLIMATE SUMMARY FOR ([A-Z]+\s[0-9]+\s[0-9]{4})\.\.\.")

class CLIException(Exception):
    ''' Exception '''
    pass

class CLIProduct( TextProduct ):
    '''
    Represents a Storm Prediction Center Mesoscale Convective Discussion
    '''
    def __init__(self, text):
        ''' constructor '''
        TextProduct.__init__(self, text)
        self.valid = self.parse_valid()
        self.data = self.parse_data()
        
    def parse_data(self):
        ''' Actually do the parsing of this silly format '''
        data = {}
        tokens = TEMP_RE.findall( self.unixtext )
        if len(tokens) == 1:
            data['temperature_maximum'] = float(tokens[0][0])
            data['temperature_minimum'] = float(tokens[0][1])
        tokens = PRECIP_RE.findall( self.unixtext )
        if len(tokens) == 1:
            data['precip_today'] = float(tokens[0][0])
            data['precip_month'] = float(tokens[0][1])

        return data

    def parse_valid(self):
        ''' Figure out when this product is valid for '''
        tokens = DATE_RE.findall( self.unixtext )
        if len(tokens) == 1:
            return datetime.datetime.strptime(tokens[0], '%B %d %Y')
        raise CLIException("Could not find valid date in product")

def parser(text):
    ''' Provide back CLI objects based on the parsing of this text '''
    return CLIProduct( text )