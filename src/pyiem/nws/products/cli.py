"""Parser and object storage of information within NWS CLI Product.
"""
import re
import datetime

from pyiem.reference import TRACE_VALUE
from pyiem.nws.product import TextProduct
from pyiem.util import LOG
from pyiem.observation import Observation
from pyiem.exceptions import CLIException

AMPM_COLON = re.compile(r"\s\d?\d:\d\d\s[AP]M")
HEADLINE_RE = re.compile(
    (
        r"\.\.\.THE ([A-Z_\.\-\(\)\/\,\s]+) "
        r"CLIMATE SUMMARY FOR\s+"
        r"([A-Z]+\s[0-9]+\s+[0-9]{4})( CORRECTION)?\.\.\."
    )
)
WIND_RE = re.compile(
    r"(HIGHEST|AVERAGE|RESULTANT)\s(WIND|GUST)\s(SPEED|DIRECTION)"
)

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
    "WEATHER ITEM   OBSERVED TIME   RECORD NORMAL DEPARTURE LAST",
]
# label, value, time, record, year, normal, departure, last
COLS = [
    [16, 23, 30, 37, 42, 49, 56, 65],
    [16, 23, 30, None, None, 37, 44, 53],
    [16, 22, 31, 37, 43, 50, 58, 65],
    [16, 23, None, 30, 35, 42, 49, 58],
    [16, 23, 25, 37, 42, None, None, None],
    [16, 23, 30, 37, 42, 49, 56, None],
    [16, 23, None, 30, 35, 42, 49, None],
    [16, 23, None, None, None, None, None, None],
    [16, 23, None, 30, 37, None, None, None],
    [16, 23, 30, 37, 42, 49, None, 57],
    [16, 23, 30, None, None, None, None, 39],
    [16, 23, None, None, None, 30, 37, 46],
    [16, 23, 30, None, None, 37, None, 45],
    [16, 23, 30, 37, 42, None, None, 51],
    [16, 23, 30, None, None, None, None, None],
    [16, 23, 30, None, None, 37, 44, None],
    [16, 23, None, None, None, 30, 37, None],
    [16, 23, 30, 37, None, 44, 51, 60],
]
# Allow manual provision of IDS
HARDCODED = {}


def update_iemaccess(txn, entry):
    """Update the IEM Access Database."""
    if entry["access_network"] is None:
        return False
    ob = Observation(
        entry["access_station"], entry["access_network"], entry["cli_valid"]
    )
    ob.load(txn)
    current = ob.data
    data = entry["data"]
    logmsg = []
    if data.get("temperature_maximum") is not None:
        climax = int(data["temperature_maximum"])
        if climax != current["max_tmpf"]:
            logmsg.append("MaxT O:%s N:%s" % (current["max_tmpf"], climax))
            current["max_tmpf"] = climax

    if data.get("temperature_minimum") is not None:
        climin = int(data["temperature_minimum"])
        if climin != current["min_tmpf"]:
            logmsg.append("MinT O:%s N:%s" % (current["min_tmpf"], climin))
            current["min_tmpf"] = climin

    if data.get("precip_month") is not None:
        val = data["precip_month"]
        if val != current["pmonth"]:
            logmsg.append("PMonth O:%s N:%s" % (current["pmonth"], val))
            current["pmonth"] = val

    if data.get("precip_today") is not None:
        val = data["precip_today"]
        if val != current["pday"]:
            logmsg.append("PDay O:%s N:%s" % (current["pday"], val))
            current["pday"] = val

    if data.get("snow_today") is not None:
        val = data["snow_today"]
        if current["snow"] is None or val != current["snow"]:
            logmsg.append("Snow O:%s N:%s" % (current["snow"], val))
            current["snow"] = val

    if not logmsg:
        return True
    res = ob.save(txn, skip_current=True)
    LOG.info(
        "%s (%s) %s ob.save: %s",
        entry["access_station"],
        entry["cli_valid"].strftime("%y%m%d"),
        ",".join(logmsg),
        res,
    )
    return res


def trace_r(val):
    """ Convert our value back into meaningful string """
    if val is None:
        return "Missing"
    if val == TRACE_VALUE:
        return "Trace"
    return val


def get_number(text):
    """ Convert a string into a number, preferable a float! """
    if text is None:
        return None
    text = text.strip()
    if text == "":
        retval = None
    elif text == "MM":
        retval = None
    elif text == "T":
        retval = TRACE_VALUE
    else:
        number = re.findall(r"[\-\+]?\d*\.\d+|[\-\+]?\d+", text)
        if len(number) == 1:
            if text.find(".") > 0:
                retval = float(number[0])
            else:
                retval = int(number[0])
        else:
            LOG.info("get_number() failed for |%s|", text)
            retval = None
    return retval


def convert_key(text):
    """ Convert a key value to something we store """
    if text is None:
        return None
    if text == "YESTERDAY":
        return "today"
    if text == "TODAY":
        return "today"
    if text == "MONTH TO DATE":
        return "month"
    if text.startswith("SINCE "):
        return text.replace("SINCE ", "").replace(" ", "").lower()
    LOG.info("convert_key() failed for |%s|", text)
    return "fail"


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
            line[pos:e].strip() if line[pos:e].strip() != "" else None
        )
        pos = e
    for i, token in enumerate(tokens):
        if token is not None and token.startswith("R "):
            tokens[i] = token.replace("R ", "")
    return tokens


def parse_snowfall(regime, lines, data):
    """Parse the snowfall data"""
    for linenum, line in enumerate(lines):
        # skipme
        if len(line.strip()) < 14:
            continue
        tokens = make_tokens(regime, line)
        key = tokens[0].strip()
        if key == "SNOW DEPTH":
            continue
        key = convert_key(key)
        data["snow_%s" % (key,)] = get_number(tokens[1])
        data["snow_%s_record" % (key,)] = get_number(tokens[3])
        yeartest = get_number(tokens[4])
        if yeartest is not None:
            data["snow_%s_record_years" % (key,)] = [yeartest]
        data["snow_%s_normal" % (key,)] = get_number(tokens[5])
        data["snow_%s_departure" % (key,)] = get_number(tokens[6])
        data["snow_%s_last" % (key,)] = get_number(tokens[7])
        if (
            key == "today"
            and yeartest is not None
            and data["snow_%s_record_years" % (key,)][0] is not None
        ):
            while (linenum + 1) < len(lines) and len(
                lines[linenum + 1].strip()
            ) == 4:
                data["snow_today_record_years"].append(int(lines[linenum + 1]))
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

        data["precip_%s" % (key,)] = get_number(tokens[1])
        data["precip_%s_record" % (key,)] = get_number(tokens[3])
        yeartest = get_number(tokens[4])
        if yeartest is not None:
            data["precip_%s_record_years" % (key,)] = [yeartest]
        data["precip_%s_normal" % (key,)] = get_number(tokens[5])
        data["precip_%s_departure" % (key,)] = get_number(tokens[6])
        data["precip_%s_last" % (key,)] = get_number(tokens[7])
        if (
            key == "today"
            and yeartest is not None
            and data["precip_%s_record_years" % (key,)][0] is not None
        ):
            while (linenum + 1) < len(lines) and len(
                lines[linenum + 1].strip()
            ) == 4:
                data["precip_today_record_years"].append(
                    int(lines[linenum + 1])
                )
                linenum += 1


def parse_temperature(regime, lines, data):
    """Here we parse a temperature section"""
    for linenum, line in enumerate(lines):
        if len(line.strip()) < 18:
            continue
        tokens = make_tokens(regime, line)
        key = tokens[0].strip().lower()
        if key.upper() not in ["MAXIMUM", "MINIMUM", "AVERAGE"]:
            continue
        data["temperature_%s" % (key,)] = get_number(tokens[1])
        if tokens[2] is not None:
            data["temperature_%s_time" % (key,)] = tokens[2]
        if tokens[3] is not None:
            data["temperature_%s_record" % (key,)] = get_number(tokens[3])
        if tokens[4] is not None:
            n = get_number(tokens[4])
            if n is not None:
                data["temperature_%s_record_years" % (key,)] = [n]
        if tokens[5] is not None:
            data["temperature_%s_normal" % (key,)] = get_number(tokens[5])
            # Check next line(s) for more years
            while (linenum + 1) < len(lines) and len(
                lines[linenum + 1].strip()
            ) == 4:
                data["temperature_%s_record_years" % (key,)].append(
                    int(lines[linenum + 1])
                )
                linenum += 1


def parse_sky_coverage(lines, data):
    """Turn section into data."""
    asc = "AVERAGE SKY COVER"
    for line in lines:
        if line.strip().startswith(asc):
            try:
                data["average_sky_cover"] = float(line.replace(asc, ""))
            except ValueError:
                pass


def parse_wind(lines, data):
    """Parse any wind information."""
    # hold your nose here
    # make everything space seperated
    content = " ".join((" ".join(lines[1:])).strip().split())
    tokens = WIND_RE.findall(content)
    for token in tokens:
        content = content.replace(" ".join(token), ";")
    vals = content[1:].split(";")
    for token, val in zip(tokens, vals):
        data[("_".join(token)).lower()] = get_number(val)


def _compute_station_ids(prod, cli_station_name, is_multi):
    """Compute needed station IDs."""
    # Can't always use the AFOS as the station ID :(
    if is_multi:
        station = None
        for st in prod.nwsli_provider:
            if prod.nwsli_provider[st]["name"].upper() == cli_station_name:
                station = st
                break
        if station is None:
            raise CLIException(
                "Unknown CLI Station Text: |%s|" % (cli_station_name,)
            )
    else:
        station = prod.source[0] + prod.afos[3:]
    # We have computed a four character station ID, is it known?
    if station not in prod.nwsli_provider:
        prod.warnings.append(
            "Station not known to NWSCLI Network |%s|" % (station,)
        )
        return station, None, None

    access_station = None
    access_network = None
    # See if our network table provides an attribute that maps us to an ASOS
    val = prod.nwsli_provider[station].get("attributes", dict()).get("MAPS_TO")
    if val is not None:
        tokens = val.split("|")
        if len(tokens) == 2:
            access_station, access_network = tokens
    if access_station is None:
        # Our default mapping
        access_station = station[1:] if station.startswith("K") else station
        access_network = "%s_ASOS" % (
            prod.nwsli_provider[station].get("state"),
        )

    return station, access_station, access_network


class CLIProduct(TextProduct):
    """
    Represents a CLI Daily Climate Report Product
    """

    def __init__(
        self, text, utcnow=None, ugc_provider=None, nwsli_provider=None
    ):
        """ constructor """
        TextProduct.__init__(self, text, utcnow, ugc_provider, nwsli_provider)
        # Hold our parsing results as an array of dicts
        self.data = []
        self.regime = None
        # Sometimes, we get products that are not really in CLI format but
        # are RER (record event reports) with a CLI AWIPS ID
        if self.wmo[:2] != "CD":
            LOG.info(
                "Product %s skipped due to wrong header", self.get_product_id()
            )
            return
        sections = self.find_sections()
        for section in sections:
            # We have meat!
            self.compute_diction(section)
            entry = {}
            entry["cli_valid"], entry["cli_station"] = self.parse_cli_headline(
                section
            )
            (
                entry["db_station"],
                entry["access_station"],
                entry["access_network"],
            ) = _compute_station_ids(
                self, entry["cli_station"], len(sections) > 1
            )
            entry["data"] = self.parse_data(section)
            self.data.append(entry)

    def find_sections(self):
        """Some trickery to figure out if we have multiple reports

        Returns:
          list of text sections
        """
        sections = []
        text = self.unixtext
        # Correct bad encoding of colons due to new NWS software
        for token in AMPM_COLON.findall(text):
            text = text.replace(token, " " + token.replace(":", ""))
        for section in text.split("&&"):
            if not HEADLINE_RE.findall(section.replace("\n", " ")):
                continue
            tokens = re.findall("^WEATHER ITEM.*$", section, re.M)
            if not tokens:
                raise CLIException("Could not find 'WEATHER ITEM' within text")
            if len(tokens) == 1:
                sections.append(section)
                continue
            # Uh oh, we need to do some manual splitting
            pos = []
            for match in re.finditer(HEADLINE_RE, section.replace("\n", " ")):
                pos.append(match.start())
            pos.append(len(section))
            for i, p in enumerate(pos[:-1]):
                sections.append(section[max([0, p - 10]) : pos[i + 1]])
        return sections

    def compute_diction(self, text):
        """ Try to determine what we have for a format """
        tokens = re.findall("^WEATHER ITEM.*$", text, re.M)
        diction = tokens[0].strip()
        if diction not in REGIMES:
            raise CLIException(
                "Unknown diction found in 'WEATHER ITEM'\n|%s|" % (diction,)
            )

        self.regime = REGIMES.index(diction)

    def get_jabbers(self, uri, _=None):
        """ Override the jabber message formatter """
        url = "%s?pid=%s" % (uri, self.get_product_id())
        res = []
        for data in self.data:
            mess = (
                "%s %s Climate Report: High: %s Low: %s "
                "Precip: %s Snow: %s %s"
            ) % (
                data["cli_station"],
                data["cli_valid"].strftime("%b %-d"),
                data["data"].get("temperature_maximum", "M"),
                data["data"].get("temperature_minimum", "M"),
                trace_r(data["data"].get("precip_today", "M")),
                trace_r(data["data"].get("snow_today", "M")),
                url,
            )
            htmlmess = (
                '%s <a href="%s">%s Climate Report</a>: High: %s '
                "Low: %s Precip: %s Snow: %s"
            ) % (
                data["cli_station"],
                url,
                data["cli_valid"].strftime("%b %-d"),
                data["data"].get("temperature_maximum", "M"),
                data["data"].get("temperature_minimum", "M"),
                trace_r(data["data"].get("precip_today", "M")),
                trace_r(data["data"].get("snow_today", "M")),
            )
            tweet = ("%s %s Climate: Hi: %s Lo: %s Precip: %s Snow: %s %s") % (
                data["cli_station"],
                data["cli_valid"].strftime("%b %-d"),
                data["data"].get("temperature_maximum", "M"),
                data["data"].get("temperature_minimum", "M"),
                trace_r(data["data"].get("precip_today", "M")),
                trace_r(data["data"].get("snow_today", "M")),
                url,
            )
            res.append(
                [
                    mess.replace(str(TRACE_VALUE), "Trace"),
                    htmlmess.replace(str(TRACE_VALUE), "Trace"),
                    {
                        "channels": self.get_channels(),
                        "product_id": self.get_product_id(),
                        "twitter": tweet,
                    },
                ]
            )
        return res

    def parse_data(self, section):
        """ Actually do the parsing of this silly format """
        data = {}
        pos = section.find("TEMPERATURE")
        if pos == -1:
            raise CLIException("Failed to find TEMPERATURE, aborting")

        # Strip extraneous spaces
        meat = "\n".join([s.rstrip() for s in section[pos:].split("\n")])
        # replace any 2+ \n with just two
        meat = re.sub(r"\n{2,}", "\n\n", meat)
        sections = meat.split("\n\n")
        for _section in sections:
            lines = _section.split("\n")
            if lines[0] in ["TEMPERATURE (F)", "TEMPERATURE"]:
                parse_temperature(self.regime, lines, data)
            elif lines[0] in ["PRECIPITATION (IN)", "PRECIPITATION"]:
                parse_precipitation(self.regime, lines, data)
            elif lines[0] in ["SNOWFALL (IN)", "SNOWFALL"]:
                parse_snowfall(self.regime, lines, data)
            elif lines[0] in ["SKY COVER"]:
                parse_sky_coverage(lines, data)
            elif lines[0] in ["WIND (MPH)"] and len(lines) > 1:
                parse_wind(lines, data)

        return data

    def parse_cli_headline(self, section):
        """ Figure out when this product is valid for """
        tokens = HEADLINE_RE.findall(section.replace("\n", " "))
        if len(tokens[0][1].split()[0]) == 3:
            myfmt = "%b %d %Y"
        else:
            myfmt = "%B %d %Y"
        cli_valid = datetime.datetime.strptime(tokens[0][1], myfmt).date()
        cli_station = (tokens[0][0]).strip().upper()
        return (cli_valid, cli_station)

    def _sql_data(self, cursor, data):
        """Do an individual data entry."""
        # See what we currently have stored.
        cursor.execute(
            "SELECT product from cli_data where station = %s and valid = %s",
            (data["db_station"], data["cli_valid"]),
        )
        if cursor.rowcount == 1:
            row = cursor.fetchone()
            if self.get_product_id() < row["product"]:
                return
            cursor.execute(
                "DELETE from cli_data WHERE station = %s and valid = %s",
                (data["db_station"], data["cli_valid"]),
            )
        cursor.execute(
            """INSERT into cli_data(
        station, product, valid, high, high_normal, high_record,
        high_record_years, low, low_normal, low_record, low_record_years,
        precip, precip_month, precip_jan1, precip_jul1, precip_normal,
        precip_record,
        precip_record_years, precip_month_normal, snow, snow_month,
        snow_jun1, snow_jul1,
        snow_dec1, precip_dec1, precip_dec1_normal, precip_jan1_normal,
        high_time, low_time, snow_record_years, snow_record,
        snow_jun1_normal, snow_jul1_normal, snow_dec1_normal,
        snow_month_normal, precip_jun1, precip_jun1_normal,
        average_sky_cover,
        resultant_wind_speed, resultant_wind_direction,
        highest_wind_speed, highest_wind_direction,
        highest_gust_speed, highest_gust_direction,
        average_wind_speed)
        VALUES (
        %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s,
        %s,
        %s, %s, %s, %s,
        %s, %s,
        %s, %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s,
        %s,
        %s, %s,
        %s, %s,
        %s, %s,
        %s
        )
        """,
            (
                data["db_station"],
                self.get_product_id(),
                data["cli_valid"],
                data["data"].get("temperature_maximum"),
                data["data"].get("temperature_maximum_normal"),
                data["data"].get("temperature_maximum_record"),
                data["data"].get("temperature_maximum_record_years", []),
                data["data"].get("temperature_minimum"),
                data["data"].get("temperature_minimum_normal"),
                data["data"].get("temperature_minimum_record"),
                data["data"].get("temperature_minimum_record_years", []),
                data["data"].get("precip_today"),
                data["data"].get("precip_month"),
                data["data"].get("precip_jan1"),
                data["data"].get("precip_jul1"),
                data["data"].get("precip_today_normal"),
                data["data"].get("precip_today_record"),
                data["data"].get("precip_today_record_years", []),
                data["data"].get("precip_month_normal"),
                data["data"].get("snow_today"),
                data["data"].get("snow_month"),
                data["data"].get("snow_jun1"),
                data["data"].get("snow_jul1"),
                data["data"].get("snow_dec1"),
                data["data"].get("precip_dec1"),
                data["data"].get("precip_dec1_normal"),
                data["data"].get("precip_jan1_normal"),
                data["data"].get("temperature_maximum_time"),
                data["data"].get("temperature_minimum_time"),
                data["data"].get("snow_today_record_years", []),
                data["data"].get("snow_today_record"),
                data["data"].get("snow_jun1_normal"),
                data["data"].get("snow_jul1_normal"),
                data["data"].get("snow_dec1_normal"),
                data["data"].get("snow_month_normal"),
                data["data"].get("precip_jun1"),
                data["data"].get("precip_jun1_normal"),
                data["data"].get("average_sky_cover"),
                data["data"].get("resultant_wind_speed"),
                data["data"].get("resultant_wind_direction"),
                data["data"].get("highest_wind_speed"),
                data["data"].get("highest_wind_direction"),
                data["data"].get("highest_gust_speed"),
                data["data"].get("highest_gust_direction"),
                data["data"].get("average_wind_speed"),
            ),
        )

    def sql(self, cursor):
        """Do the database update!"""
        for entry in self.data:
            self._sql_data(cursor, entry)
            if not update_iemaccess(cursor, entry):
                self.warnings.append(
                    "IEMAccess Update failed %s %s %s"
                    % (
                        entry["access_network"],
                        entry["access_station"],
                        entry["cli_valid"],
                    )
                )


def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    """Parse CLI Text Products.

    Args:
      nwsli_provider (dict): This dictionary provider in the form of the
        `pyiem.network.Table` object should contain additional attributes of
        `access_station` and `access_network` to map back to IEMAccess.
    """
    # Careful here, see if we have two CLIs in one product!
    return CLIProduct(text, utcnow, ugc_provider, nwsli_provider)
