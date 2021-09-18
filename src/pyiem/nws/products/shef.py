"""Standard Hydrological Exchange Format (SHEF).

https://www.weather.gov/media/mdl/SHEF_CodeManual_5July2012.pdf

Formats
-------
.A - single station, multiple parameter
.B - multiple station, multiple parameter, header driven
.E - single station, single parameter, evenly spaced time series

"""
try:
    from zoneinfo import ZoneInfo  # type: ignore
except ImportError:
    from backports.zoneinfo import ZoneInfo
from datetime import date, timezone, datetime, timedelta
import re

from pyiem.models.shef import SHEFElement
from pyiem.nws.product import TextProduct

TYPE_RE = re.compile(r"^\.(?P<type>[ABE])", re.M)
TIMEZONES = {
    "C": "America/Chicago",
    "CD": "America/Chicago",
    "CS": "America/Chicago",
}

"""
N Newfoundland local time UTC - 3:30 or 2:30
NS Newfoundland standard time UTC - 2:30
A Atlantic local time UTC - 4:00 or 3:00
AD Atlantic daylight time UTC - 3:00
AS Atlantic standard time UTC - 4:00
E Eastern local time UTC - 5:00 or 4:00
ED Eastern daylight time UTC - 4:00
ES Eastern standard time UTC - 5:00
J China UTC +8
M Mountain local time UTC - 7:00 or 6:00
MD Mountain daylight time UTC - 6:00
MS Mountain standard time UTC - 7:00
P Pacific local time UTC - 8:00 or 7:00
PD Pacific daylight time UTC - 7:00
PS Pacific standard time UTC - 8:00
Y Yukon local time UTC - 8:00 or 7:00
YD Yukon daylight time UTC - 7:00
YS Yukon standard time UTC - 8:00
H Hawaiian local time UTC - 10:00
HS Hawaiian standard time UTC - 10:00
L Alaskan local time UTC - 9:00 or 8:00
LD Alaskan daylight time UTC - 8:00
LS Alaskan standard time UTC - 9:00
B Bering local time UTC - 10:00 or 9:00
BD Bering daylight time UTC - 9:00
BS Bering standard time UTC - 10:00
Z Zulu time, also Universal Time Code (UTC), formerly Greenwich Mean Time (GMT)
"""


def make_date(text, now):
    """Make the text date unambiguous!"""
    # “mmdd” or “yymmdd” or “ccyymmdd”
    if len(text) == 8:
        return date(int(text[:4]), int(text[4:6]), int(text[6:]))
    if len(text) == 6:
        base = 2000 if now.year >= 2000 else 1900
        return date(base + int(text[:2]), int(text[2:4]), int(text[4:]))
    month = int(text[:2])
    day = int(text[2:])
    if now.month < 6 and month > 6:
        # Last year
        return date(now.year - 1, month, day)
    return date(now.year, month, day)


def parse_station_valid(text, utcnow):
    """Get what we can get from this cryptic string."""
    tokens = text.split()
    station = tokens[1]
    valid = make_date(tokens[2], utcnow)
    # 4.1.4 Timezone is optional, default to Z
    if len(tokens) > 4 and tokens[3] in TIMEZONES:
        tzinfo = ZoneInfo(TIMEZONES[tokens[3]])
    else:
        tzinfo = timezone.utc
    # Take a swing that the last element is DH
    if tokens[-1].startswith("DH"):
        meat = tokens[-1][2:]
        if len(meat) == 4:
            valid = datetime(
                valid.year,
                valid.month,
                valid.day,
                int(meat[:2]),
                int(meat[2:]),
                tzinfo=tzinfo,
            )
    return station, valid


def process_message_e(prod, message):
    """Convert the message into an object."""
    tokens = message.split("/")
    station, basevalid = parse_station_valid(tokens[0], prod.utcnow)
    elements = []
    # Iterate through the next tokens and hopefully find DI
    interval = None
    datastart = None
    physical_element = None
    for i, token in enumerate(tokens[1:], 1):
        if token.startswith("DC"):
            # TODO
            continue
        if token.startswith("DI"):
            if token[2] == "H":
                interval = timedelta(hours=int(token[3:]))
            elif token[2] == "D":
                interval = timedelta(days=int(token[3:]))
            elif token[2] == "M":
                interval = timedelta(minutes=int(token[3:]))
            datastart = i + 1
            break
        if token[0].isalpha():
            physical_element = token[:2]

    valid = basevalid
    for token in tokens[datastart:]:
        for tokens2 in token.strip().split():
            elements.append(
                SHEFElement(
                    station=station,
                    valid=valid,
                    physical_element=physical_element,
                    str_value=tokens2,
                )
            )
            valid += interval

    return elements


def process_message_b(prod, message):
    """Convert the message into an object."""
    # line one has the magic
    lines = message.split("\n")
    tokens = lines[0].split("/")
    _center, valid = parse_station_valid(tokens[0], prod.utcnow)
    # second token should have the PE
    physical_element = tokens[1][:2]
    elements = []
    for line in lines[1:]:
        if line.startswith(":") or line.find("/") == -1:
            continue
        print(line)
        elements.append(
            SHEFElement(
                station=line.split()[0],
                valid=valid,
                physical_element=physical_element,
            )
        )
    return elements


def process_message_a(prod, message):
    """Convert the message into an object."""
    tokens = message.split("/")
    # First tokens should have some mandatory stuff
    station, valid = parse_station_valid(tokens[0], prod.utcnow)
    elements = []
    for text in tokens[1:]:
        text = text.strip()
        elements.append(
            SHEFElement(
                station=station, valid=valid, physical_element=text[:2]
            )
        )

    return elements


def parse_A(prod):
    """Parse A format SHEF data."""
    # Line by Line collecting up what we find!
    messages = []
    for line in prod.unixtext.split("\n"):
        # New Message!
        if line.startswith(".AR ") or line.startswith(".A "):
            messages.append(line)
            continue
        if line.startswith(".A"):  # continuation
            messages[-1] += f"/{line.split(maxsplit=1)[1]}"
    # We have messages to parse into objects
    for message in messages:
        res = process_message_a(prod, message)
        if res:
            prod.data.extend(res)


def parse_B(prod):
    """Parse B format SHEF data."""
    # Messages here are a bit special as it starts with .B and ends with .END
    messages = []

    inmessage = False
    for line in prod.unixtext.split("\n"):
        # New Message!
        if line.startswith(".BR ") or line.startswith(".B "):
            messages.append(line + "\n")
            inmessage = True
            continue
        if line.startswith(".END"):
            inmessage = False
            continue
        if inmessage:
            messages[-1] += line + "\n"

    # We have messages to parse into objects
    for message in messages:
        res = process_message_b(prod, message)
        if res:
            prod.data.extend(res)


def parse_E(prod):
    """Parse E format SHEF data."""
    messages = []
    for line in prod.unixtext.split("\n"):
        # New Message!
        if line.startswith(".ER ") or line.startswith(".E "):
            messages.append(line)
            continue
        if line.startswith(".E"):  # continuation
            messages[-1] += f" {line.split(maxsplit=1)[1]}"
    # We have messages to parse into objects
    for message in messages:
        res = process_message_e(prod, message)
        if res:
            prod.data.extend(res)


def _parse(prod):
    """Do what is necessary to get this product parsed."""
    # Assumption, product has only one SHEF data type per file
    m = TYPE_RE.search(prod.unixtext)
    if not m:
        prod.warnings.append("No SHEF encoding types found, abort!")
        return
    typ = m.groupdict()["type"]
    if typ == "A":
        parse_A(prod)
    elif typ == "B":
        parse_B(prod)
    elif typ == "E":
        parse_E(prod)


class SHEFProduct(TextProduct):
    """A single text product containing SHEF encoded data."""

    def __init__(
        self, text, utcnow=None, ugc_provider=None, nwsli_provider=None
    ):
        """constructor"""
        TextProduct.__init__(self, text, utcnow, ugc_provider, nwsli_provider)
        # Storage of parsed results.
        self.data = []
        _parse(self)


def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    """The SPS Parser"""
    return SHEFProduct(
        text, utcnow, ugc_provider=ugc_provider, nwsli_provider=nwsli_provider
    )
