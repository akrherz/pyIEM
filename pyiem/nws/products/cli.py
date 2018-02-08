"""Parser and object storage of information within NWS CLI Product.
"""
from __future__ import print_function
import re
import datetime

from pyiem.reference import TRACE_VALUE
from pyiem.nws.product import TextProduct

HEADLINE_RE = re.compile((r"\.\.\.THE ([A-Z_\.\-\(\)\/\,\s]+) "
                          r"CLIMATE SUMMARY FOR\s+"
                          r"([A-Z]+\s[0-9]+\s+[0-9]{4})( CORRECTION)?\.\.\."))

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
    "WEATHER ITEM   OBSERVED NORMAL DEPARTURE",
]
#   label, value, time, record, year, normal, departure, last
COLS = [
    [16,     23,   30,   37,     42,   49,     56,        65],
    [16,     23,   30,   None,   None, 37,     44,        53],
    [16,     22,   31,   37,     43,   50,     58,        65],
    [16,     23,  None,  30,     35,   42,     49,        58],
    [16,     23,   25,   37,     42,   None,   None,      None],
    [16,     23,   30,   37,     42,   49,     56,        None],
    [16,     23,  None,  30,     35,   42,     49,        None],
    [16,     23,  None,  None,   None, None,   None,      None],
    [16,     23,  None,  30,     37,   None,   None,      None],
    [16,     23,   30,   37,     42,   49,     None,      57],
    [16,     23,   30,   None,   None, None,   None,      39],
    [16,     23,   None, None,   None, 30,     37,        46],
    [16,     23,   30,   None,   None, 37,     None,      45],
    [16,     23,   30,   37,     42,   None,   None,      51],
    [16,     23,   30,   None,   None, None,   None,      None],
    [16,     23,   30,   None,   None, 37,     44,        None],
    [16,     23,   None, None,   None, 30,     37,        None],
    ]


class CLIException(Exception):
    """ Exception """
    pass


def trace(val):
    """ This value could be T or M, account for it! """
    if val == 'M' or val == 'MM':
        return None
    if val == 'T':
        return TRACE_VALUE
    return float(val)


def trace_r(val):
    """ Convert our value back into meaningful string """
    if val is None:
        return 'Missing'
    if val == TRACE_VALUE:
        return 'Trace'
    return val


def get_number(text):
    """ Convert a string into a number, preferable a float! """
    if text is None:
        return None
    text = text.strip()
    if text == '':
        retval = None
    elif text == 'MM':
        retval = None
    elif text == 'T':
        retval = TRACE_VALUE
    else:
        number = re.findall(r"[\-\+]?\d*\.\d+|[\-\+]?\d+", text)
        if len(number) == 1:
            if text.find(".") > 0:
                retval = float(number[0])
            else:
                retval = int(number[0])
        else:
            print('get_number() failed for |%s|' % (text,))
            retval = None
    return retval


def convert_key(text):
    """ Convert a key value to something we store """
    if text is None:
        return None
    if text == 'YESTERDAY':
        return 'today'
    if text == 'TODAY':
        return 'today'
    if text == 'MONTH TO DATE':
        return 'month'
    if text.startswith('SINCE '):
        return text.replace('SINCE ', '').replace(' ', "").lower()
    print('convert_key() failed for |%s|' % (text,))
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
        tokens.append(
            line[pos:e].strip() if line[pos:e].strip() != "" else None)
        pos = e
    for i, token in enumerate(tokens):
        if token is not None and token.startswith("R "):
            tokens[i] = token.replace("R ", "")
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
            data['snow_%s_record_years' % (key,)] = [yeartest, ]
        data['snow_%s_normal' % (key,)] = get_number(tokens[5])
        data['snow_%s_departure' % (key,)] = get_number(tokens[6])
        data['snow_%s_last' % (key,)] = get_number(tokens[7])
        if (key == 'today' and yeartest is not None and
                data['snow_%s_record_years' % (key, )][0] is not None):
            while ((linenum+1) < len(lines) and
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
        if key is None:
            continue

        data['precip_%s' % (key,)] = get_number(tokens[1])
        data['precip_%s_record' % (key,)] = get_number(tokens[3])
        yeartest = get_number(tokens[4])
        if yeartest is not None:
            data['precip_%s_record_years' % (key,)] = [yeartest, ]
        data['precip_%s_normal' % (key,)] = get_number(tokens[5])
        data['precip_%s_departure' % (key,)] = get_number(tokens[6])
        data['precip_%s_last' % (key,)] = get_number(tokens[7])
        if (key == 'today' and yeartest is not None and
                data['precip_%s_record_years' % (key,)][0] is not None):
            while ((linenum+1) < len(lines) and
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
                data['temperature_%s_record_years' % (key,)] = [n, ]
        if tokens[5] is not None:
            data['temperature_%s_normal' % (key,)] = get_number(tokens[5])
            # Check next line(s) for more years
            while ((linenum+1) < len(lines) and
                   len(lines[linenum+1].strip()) == 4):
                data['temperature_%s_record_years' % (key,)].append(
                                                int(lines[linenum+1]))
                linenum += 1


class CLIProduct(TextProduct):
    """
    Represents a CLI Daily Climate Report Product
    """

    def __init__(self, text, utcnow=None, ugc_provider=None,
                 nwsli_provider=None):
        """ constructor """
        TextProduct.__init__(self, text, utcnow, ugc_provider, nwsli_provider)
        # Hold our parsing results as an array of dicts
        self.data = []
        self.regime = None
        # Sometimes, we get products that are not really in CLI format but
        # are RER (record event reports) with a CLI AWIPS ID
        if self.wmo[:2] != 'CD':
            print(('Product %s skipped due to wrong header'
                   ) % (self.get_product_id(),))
            return
        for section in self.find_sections():
            if not HEADLINE_RE.findall(section.replace("\n", " ")):
                continue
            # We have meat!
            self.compute_diction(section)
            valid, station = self.parse_cli_headline(section)
            data = self.parse_data(section)
            self.data.append(dict(cli_valid=valid,
                                  cli_station=station,
                                  data=data))

    def find_sections(self):
        """Some trickery to figure out if we have multiple reports

        Returns:
          list of text sections
        """
        sections = []
        for section in self.unixtext.split("&&"):
            if not HEADLINE_RE.findall(section.replace("\n", " ")):
                continue
            tokens = re.findall("^WEATHER ITEM.*$", section, re.M)
            if not tokens:
                raise CLIException("Could not find 'WEATHER ITEM' within text")
            elif len(tokens) == 1:
                sections.append(section)
                continue
            # Uh oh, we need to do some manual splitting
            pos = []
            for match in re.finditer(HEADLINE_RE, section.replace("\n", " ")):
                pos.append(match.start())
            if len(pos) < 2:
                raise CLIException("find_sections logic failure!")
            pos.append(len(section))
            for i, p in enumerate(pos[:-1]):
                sections.append(section[max([0, p-10]):pos[i+1]])
        return sections

    def compute_diction(self, text):
        """ Try to determine what we have for a format """
        tokens = re.findall("^WEATHER ITEM.*$", text, re.M)
        if not tokens:
            raise CLIException("Could not find 'WEATHER ITEM' within text")
        if len(tokens) > 1:
            raise CLIException("Found %s 'WEATHER ITEM' in text" % (
                                                                len(tokens),))
        diction = tokens[0].strip()
        if diction not in REGIMES:
            raise CLIException(("Unknown diction found in 'WEATHER ITEM'\n"
                                "|%s|") % (diction,))

        self.regime = REGIMES.index(diction)

    def get_jabbers(self, uri, _=None):
        """ Override the jabber message formatter """
        url = "%s?pid=%s" % (uri, self.get_product_id())
        res = []
        for data in self.data:
            mess = ("%s %s Climate Report: High: %s Low: %s "
                    "Precip: %s Snow: %s %s"
                    ) % (data['cli_station'],
                         data['cli_valid'].strftime("%b %-d"),
                         data['data'].get('temperature_maximum', 'M'),
                         data['data'].get('temperature_minimum', 'M'),
                         trace_r(data['data'].get('precip_today', 'M')),
                         trace_r(data['data'].get('snow_today', 'M')), url)
            htmlmess = ("%s <a href=\"%s\">%s Climate Report</a>: High: %s "
                        "Low: %s Precip: %s Snow: %s"
                        ) % (data['cli_station'], url,
                             data['cli_valid'].strftime("%b %-d"),
                             data['data'].get('temperature_maximum', 'M'),
                             data['data'].get('temperature_minimum', 'M'),
                             trace_r(data['data'].get('precip_today', 'M')),
                             trace_r(data['data'].get('snow_today', 'M')))
            tweet = ("%s %s Climate: Hi: %s Lo: %s Precip: %s Snow: %s %s"
                     ) % (data['cli_station'],
                          data['cli_valid'].strftime("%b %-d"),
                          data['data'].get('temperature_maximum', 'M'),
                          data['data'].get('temperature_minimum', 'M'),
                          trace_r(data['data'].get('precip_today', 'M')),
                          trace_r(data['data'].get('snow_today', 'M')), url)
            res.append([mess.replace(str(TRACE_VALUE), "Trace"),
                        htmlmess.replace(str(TRACE_VALUE), "Trace"), {
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
        for _section in sections:
            lines = _section.split("\n")
            if lines[0] in ["TEMPERATURE (F)", 'TEMPERATURE']:
                parse_temperature(self.regime, lines, data)
            elif lines[0] in ['PRECIPITATION (IN)', 'PRECIPITATION']:
                parse_precipitation(self.regime, lines, data)
            elif lines[0] in ['SNOWFALL (IN)', 'SNOWFALL']:
                parse_snowfall(self.regime, lines, data)

        return data

    def parse_cli_headline(self, section):
        """ Figure out when this product is valid for """
        tokens = HEADLINE_RE.findall(section.replace("\n", " "))
        if len(tokens) == 1:
            if len(tokens[0][1].split()[0]) == 3:
                myfmt = '%b %d %Y'
            else:
                myfmt = '%B %d %Y'
            cli_valid = datetime.datetime.strptime(tokens[0][1], myfmt)
            cli_station = (tokens[0][0]).strip()
            return (cli_valid, cli_station)
        elif len(tokens) > 1:
            raise CLIException("Found two headers in product, unsupported!")
        else:
            # Known sources of bad data...
            if self.source in ['PKMR', 'NSTU', 'PTTP', 'PTKK', 'PTKR']:
                return (None, None)
            raise CLIException('Could not find date valid in %s' % (
                                                self.get_product_id(),))


def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    """ Provide back CLI objects based on the parsing of this text """
    # Careful here, see if we have two CLIs in one product!
    return CLIProduct(text, utcnow, ugc_provider, nwsli_provider)
