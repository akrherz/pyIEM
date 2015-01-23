"""Parser and object storage of information within NWS CLI Product. 
"""
import re
import datetime

from pyiem.nws.product import TextProduct

HEADLINE_RE = re.compile(r"\.\.\.THE ([A-Z_\.\-\(\)\/\,\s]+) CLIMATE SUMMARY FOR\s+([A-Z]+\s[0-9]+\s+[0-9]{4})( CORRECTION)?\.\.\.")

REGIMES = [
"WEATHER ITEM   OBSERVED TIME   RECORD YEAR NORMAL DEPARTURE LAST",
"WEATHER ITEM   OBSERVED TIME   NORMAL DEPARTURE LAST",
"WEATHER ITEM   OBSERVED TIME    RECORD YEAR NORMAL DEPARTURE LAST",
"WEATHER ITEM   OBSERVED RECORD YEAR NORMAL DEPARTURE LAST",
"WEATHER ITEM   OBSERVED TIME   RECORD YEAR",
"WEATHER ITEM   OBSERVED TIME   RECORD YEAR NORMAL DEPARTURE",
"WEATHER ITEM   OBSERVED RECORD YEAR NORMAL DEPARTURE",
"WEATHER ITEM   OBSERVED",
"WEATHER ITEM   OBSERVED RECORD YEAR NORMAL",
"WEATHER ITEM   OBSERVED TIME   RECORD YEAR NORMAL  LAST",
"WEATHER ITEM   OBSERVED TIME       LAST",
"WEATHER ITEM   OBSERVED NORMAL DEPARTURE LAST",
"WEATHER ITEM   OBSERVED TIME   NORMAL  LAST",
"WEATHER ITEM   OBSERVED TIME   RECORD YEAR     LAST",
"WEATHER ITEM   OBSERVED TIME",
"WEATHER ITEM   OBSERVED TIME   NORMAL DEPARTURE",
]
# label, value, time, record, year, normal, departure, last
COLS = [
[  16,     23,   30,   37,     42,   49,    56,         65],
[  16,     23,   30,   None,   None, 37,    44,         53],
[  16,     22,   31,   37,     43,   50,    58,         65],
[  16,     23,  None,  30,     35,   42,    49,         58],
[  16,     23,   25,   37,     42,   None,  None,      None],
[  16,     23,   30,   37,     42,   49,    56,        None],
[  16,     23,  None,  30,     35,   42,    49,        None],
[  16,     23,  None,  None,   None, None,  None,      None],
[  16,     23,  None,  30,     37,   None,  None,      None],
[  16,     23,   30,   37,     42,   49,    None,       57],
[  16,     23,   30,   None,   None,  None,    None,       39],
[  16,     23,   None,   None,   None,  30,    37,       46],
[  16,     23,   30,   None,   None,  37,    None,       45],
[  16,     23,   30,   37,   42,  None,    None,       51],
[  16,     23,   30,   None,   None,  None,    None,       None],
[  16,     23,   30,   None,   None,  37,    44,       None],
]

class CLIException(Exception):
    """ Exception """
    pass

def trace(val):
    """ This value could be T or M, account for it! """
    if val == 'M' or val == 'MM':
        return None
    if val == 'T':
        return 0.0001
    return float(val)

def trace_r(val):
    """ Convert our value back into meaningful string """
    if val == 0.0001:
        return 'Trace'
    return val

def get_number(s):
    """ Convert a string into a number, preferable a float! """
    if s is None:
        return None
    s = s.strip()
    if s == '':
        return None
    if s == 'MM':
        return None
    if s == 'T':
        return 0.0001
    number = re.findall("[\-\+]?\d*\.\d+|[\-\+]?\d+", s)
    if len(number) == 1:
        if s.find(".") > 0:
            return float(number[0])
        else:
            return int(number[0])
    print 'get_number() failed for |%s|' % (s,)
    return None

def convert_key(s):
    """ Convert a key value to something we store """
    if s == 'YESTERDAY':
        return 'today'
    if s == 'TODAY':
        return 'today'
    if s == 'MONTH TO DATE':
        return 'month'
    if s.startswith('SINCE '):
        return s.replace('SINCE ', '').replace(' ', "").lower()
    print 'convert_key() failed for |%s|' % (s,)
    return 'fail'

def make_tokens(regime, line):
    """ Turn a line into tokens based on a regime """
    mycols = COLS[regime]
    tokens = []
    pos = 0
    for e in mycols:
        if e is None:
            tokens.append(None)
            continue
        tokens.append(line[pos:e].strip() if line[pos:e].strip() != "" else None)
        pos = e
    return tokens

def parse_snowfall(regime, lines, data):
    """ Parse the snowfall data 
    """
    for linenum, line in enumerate(lines):
        # skipme
        if len(line.strip()) < 14:
            continue
        tokens = make_tokens(regime, line)
        key = tokens[0].strip()
        if key == 'SNOW DEPTH':
            continue
        key = convert_key(key)
        data['snow_%s' % (key,)] = get_number(tokens[1])
        data['snow_%s_record' % (key,)] = get_number(tokens[3])
        yeartest = get_number(tokens[4])
        if yeartest is not None:
            data['snow_%s_record_years' % (key,)] = [yeartest,]
        data['snow_%s_normal' % (key,)] = get_number(tokens[5])
        data['snow_%s_departure' % (key,)] = get_number(tokens[6])
        data['snow_%s_last' % (key,)] = get_number(tokens[7])
        if (key == 'today' and yeartest is not None and
            data['snow_%s_record_years' % (key,)][0] is not None):
                while ((linenum+1)<len(lines) and 
                       len(lines[linenum+1].strip()) == 4):
                    data['snow_today_record_years'].append(
                                                    int(lines[linenum+1]))
                    linenum += 1

def parse_precipitation(regime, lines, data):
    """ Parse the precipitation data """
    for linenum, line in enumerate(lines):
        if len(line.strip()) < 20:
            continue
        tokens = make_tokens(regime, line)
        key = convert_key(tokens[0])
        
        data['precip_%s' % (key,)] = get_number(tokens[1])
        data['precip_%s_record' % (key,)] = get_number(tokens[3])
        yeartest = get_number(tokens[4])
        if yeartest is not None:
            data['precip_%s_record_years' % (key,)] = [yeartest,]
        data['precip_%s_normal' % (key,)] = get_number(tokens[5])
        data['precip_%s_departure' % (key,)] = get_number(tokens[6])
        data['precip_%s_last' % (key,)] = get_number(tokens[7])
        if (key == 'today' and yeartest is not None and
            data['precip_%s_record_years' % (key,)][0] is not None):
                while ((linenum+1)<len(lines) and 
                       len(lines[linenum+1].strip()) == 4):
                    data['precip_today_record_years'].append(
                                                    int(lines[linenum+1]))
                    linenum += 1

def no99(val):
    """ Giveme int val of null! """
    if val == '-99':
        return None
    return int(val)

def parse_temperature(regime, lines, data):
    """ Here we parse a temperature section
    """
    for linenum, line in enumerate(lines):
        if len(line.strip()) < 18:
            continue
        tokens = make_tokens(regime, line)
        if tokens[0] is None:
            continue
        key = tokens[0].strip().lower()
        if key.upper() not in ["MAXIMUM", "MINIMUM", "AVERAGE"]:
            continue
        data['temperature_%s' % (key,)] = get_number(tokens[1])
        if tokens[2] is not None:
            data['temperature_%s_time' % (key,)] = tokens[2]
        if tokens[3] is not None:
            data['temperature_%s_record' % (key,)] = get_number(tokens[3])
        if tokens[4] is not None:
            n = get_number(tokens[4])
            if n is not None:
                data['temperature_%s_record_years' % (key,)] = [n,]
        if tokens[5] is not None:    
            data['temperature_%s_normal' % (key,)] = get_number(tokens[5])
            # Check next line(s) for more years
            while ((linenum+1)<len(lines) and 
                   len(lines[linenum+1].strip()) == 4):
                data['temperature_%s_record_years' % (key,)].append(
                                                int(lines[linenum+1]))
                linenum += 1

class CLIProduct(TextProduct):
    """
    Represents a CLI Daily Climate Report Product
    """

    def __init__(self, text):
        """ constructor """
        TextProduct.__init__(self, text)
        # Hold our parsing results as an array of dicts
        self.data = []
        self.regime = None
        # Sometimes, we get products that are not really in CLI format but 
        # are RER (record event reports) with a CLI AWIPS ID
        if self.wmo[:2] != 'CD':
            print 'Product %s skipped due to wrong header' % (
                                                    self.get_product_id(),)
            return
        for section in self.unixtext.split("&&"):
            if len(HEADLINE_RE.findall(section.replace("\n", " "))) == 0:
                continue
            # We have meat!
            self.compute_diction(section)
            valid, station = self.parse_cli_headline(section)
            data = self.parse_data(section)
            self.data.append(dict(cli_valid=valid,
                                  cli_station=station,
                                  data=data))

    def compute_diction(self, text):
        """ Try to determine what we have for a format """
        tokens = re.findall("^WEATHER ITEM.*$", text, re.M)
        if len(tokens) == 0:
            raise CLIException("Could not find 'WEATHER ITEM' within text")
        if len(tokens) > 1:
            raise CLIException("Found %s 'WEATHER ITEM' in text" % (
                                                                len(tokens),))
        diction = tokens[0].strip()
        if not diction in REGIMES:
            raise CLIException(("Unknown diction found in 'WEATHER ITEM'\n"
                                +"|%s|") % (diction,))
        
        self.regime = REGIMES.index(diction)
        
    def get_jabbers(self, uri, _=None):
        """ Override the jabber message formatter """
        url = "%s?pid=%s" % (uri, self.get_product_id())
        res = []
        for data in self.data:
            mess = "%s %s Climate Report: High: %s Low: %s Precip: %s Snow: %s %s" % (
                        data['cli_station'], 
                        data['cli_valid'].strftime("%b %-d"),
                        data['data'].get('temperature_maximum', 'M'),
                        data['data'].get('temperature_minimum', 'M'),
                        trace_r(data['data'].get('precip_today', 'M')),
                        trace_r(data['data'].get('snow_today', 'M')), url
                        )
            htmlmess = ("%s <a href=\"%s\">%s Climate Report</a>: High: %s "
                        +"Low: %s Precip: %s Snow: %s") % (
                        data['cli_station'], url, data['cli_valid'].strftime("%b %-d"),
                        data['data'].get('temperature_maximum', 'M'),
                        data['data'].get('temperature_minimum', 'M'),
                        trace_r(data['data'].get('precip_today', 'M')),
                        trace_r(data['data'].get('snow_today', 'M'))
                        )
            tweet = "%s %s Climate: Hi: %s Lo: %s Precip: %s Snow: %s %s" % (
                        data['cli_station'], data['cli_valid'].strftime("%b %-d"),
                        data['data'].get('temperature_maximum', 'M'),
                        data['data'].get('temperature_minimum', 'M'),
                        trace_r(data['data'].get('precip_today', 'M')),
                        trace_r(data['data'].get('snow_today', 'M')), url
                        )
            res.append([mess.replace("0.0001", "Trace"), 
                        htmlmess.replace("0.0001", "Trace"), {
                            'channels': self.afos,
                            'twitter': tweet
                    }])
        return res

    def parse_data(self, section):
        """ Actually do the parsing of this silly format """
        data = {}
        pos = section.find("TEMPERATURE")
        if pos == -1:
            raise CLIException('Failed to find TEMPERATURE, aborting')
        if self.regime is None:
            return data

        # Strip extraneous spaces
        meat = "\n".join([l.rstrip() for l in section[pos:].split("\n")])
        # Don't look into aux data for things we should not be parsing
        if meat.find("&&") > 0:
            meat = meat[:meat.find("&&")]
        sections = meat.split("\n\n")
        for section in sections:
            lines = section.split("\n")
            if lines[0] in ["TEMPERATURE (F)", 'TEMPERATURE']:
                parse_temperature(self.regime, lines, data)
            elif lines[0] in ['PRECIPITATION (IN)', 'PRECIPITATION']:
                parse_precipitation(self.regime, lines, data)
            elif lines[0] in ['SNOWFALL (IN)', 'SNOWFALL']:
                parse_snowfall(self.regime, lines, data)

        return data

    def parse_cli_headline(self, section):
        """ Figure out when this product is valid for """
        tokens = HEADLINE_RE.findall( section.replace("\n", " ") )
        if len(tokens) == 1:
            if len(tokens[0][1].split()[0]) == 3:
                myfmt = '%b %d %Y'
            else:
                myfmt = '%B %d %Y'
            cli_valid = datetime.datetime.strptime(tokens[0][1], myfmt)
            cli_station = (tokens[0][0]).strip()
            return cli_valid, cli_station  
        elif len(tokens) > 1:
            raise CLIException("Found two headers in product, unsupported!")
        else:
            # Known sources of bad data...
            if self.source in ['PKMR', 'NSTU', 'PTTP', 'PTKK', 'PTKR']:
                return None
            raise CLIException('Could not find date valid in %s' % (
                                                self.get_product_id(),))

def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    """ Provide back CLI objects based on the parsing of this text """
    # Careful here, see if we have two CLIs in one product!
    return CLIProduct( text )
