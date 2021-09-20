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
from typing import List

from pyiem.models.shef import SHEFElement
from pyiem.nws.product import TextProduct
from pyiem.util import LOG

DM_RE = re.compile(r" DM(\d+)")
INLINE_COMMENT_RE = re.compile(":.*:")
TIMEZONES = {
    "C": "America/Chicago",
    "CD": "America/Chicago",
    "CS": "America/Chicago",
    "N": "Canada/Newfoundland",
    "NS": "Canada/Newfoundland",
    "A": "Canada/Atlantic",  # Unsure
    "AD": "Canada/Atlantic",  # Unsure
    "AS": "Canada/Atlantic",  # Unsure
    "E": "America/New_York",
    "ED": "America/New_York",
    "ES": "America/New_York",
    "J": "UTC+8",  # TODO China UTC +8
    "M": "America/Denver",
    "MD": "America/Denver",
    "MS": "America/Denver",
    "P": "America/Los_Angeles",
    "PD": "America/Los_Angeles",
    "PS": "America/Los_Angeles",
    "Y": "Canada/Yukon",
    "YD": "Canada/Yukon",
    "YS": "Canada/Yukon",
    "H": "US/Hawaii",
    "HS": "US/Hawaii",
    "L": "US/Alaska",
    "LD": "US/Alaska",
    "LS": "US/Alaska",
    "B": "Asia/Anadyr",
    "BD": "Asia/Anadyr",
    "BS": "Asia/Anadyr",
    "Z": "Etc/UTC",
}


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
    if now.month < 6 < month:
        # Last year
        return date(now.year - 1, month, day)
    return date(now.year, month, day)


def parse_datetime(text, basevalid):
    """Convert the DC/DM element into a timestamp."""
    # 4.4.2 If the hour number is NOT given, the default is hour 24 if a
    # time zone was given previously, else it is 12 if the time zone was
    # given as Zulu time. This allows for an end-of-day value for mean or
    # accumulated data types.
    text = text.strip()
    # If length is 4, only one option
    if len(text) == 4:
        return basevalid.replace(
            month=int(text[:2]),
            day=int(text[2:]),
        )
    if len(text) >= 8:
        # TODO better handle year and century here, add tests around 1 Jan
        valid = basevalid.replace(
            month=int(text[-8:-6]),
            day=int(text[-6:-4]),
            hour=int(text[-4:-2]),
            minute=int(text[-2:]),
        )
        return valid
    raise ValueError(f"Unable to parse DC '{text}'")


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
        elif len(meat) == 2:
            valid = datetime(
                valid.year,
                valid.month,
                valid.day,
                int(meat[:2]),
                0,
                tzinfo=tzinfo,
            )
        elif len(meat) == 6:
            valid = datetime(
                valid.year,
                valid.month,
                valid.day,
                int(meat[:2]),
                int(meat[2:4]),
                int(meat[4:6]),
                tzinfo=tzinfo,
            )
        else:
            raise ValueError(f"No logic to parse '{meat}'")
    return station, valid


def process_message_e(prod, message) -> List[SHEFElement]:
    """Process a text string in E SHEF format.

    Args:
      prod (TextProduct): TextProduct that contains this message.
      message (str): The string to parse.

    Returns:
      List(SHEFElement)
    """
    tokens = message.split("/")
    station, basevalid = parse_station_valid(tokens[0], prod.utcnow)
    elements = []
    # Iterate through the next tokens and hopefully find DI
    interval = None
    datastart = None
    physical_element = None
    data_created = None
    for i, token in enumerate(tokens[1:], 1):
        if token.startswith("DC"):
            data_created = parse_datetime(token[2:], basevalid)
            continue
        if token.startswith("DI"):
            if token[2] == "H":
                interval = timedelta(hours=int(token[3:]))
            elif token[2] == "D":
                interval = timedelta(days=int(token[3:]))
            elif token[2] == "N":
                interval = timedelta(minutes=int(token[3:]))
            else:
                raise ValueError(f"Unhandled DI of '{token[2]}")
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
                    data_created=data_created,
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
    physical_elements = []
    for token in tokens[1:]:
        physical_elements.append(token.strip()[:2])
    elements = []
    for line in lines[1:]:
        if line.startswith(":") or line.find("/") == -1:
            continue
        # Cull inline comments
        m = INLINE_COMMENT_RE.search(line)
        if m:
            line = line.replace(m.group(), "/")  # this may be too cute
        tokens = line.split("/")
        # 5.2.2 Observational time change via DM nomenclature
        m = DM_RE.search(tokens[0])
        if m:
            res = m.group()
            localvalid = parse_datetime(res.strip()[2:], valid)
        else:
            localvalid = valid
        for i, token in enumerate(tokens[1:]):
            elements.append(
                SHEFElement(
                    station=tokens[0].split()[0],
                    valid=localvalid,
                    physical_element=physical_elements[i],
                    str_value=token.strip(),
                )
            )
    return elements


def process_message_a(prod, message):
    """Convert the message into an object."""
    tokens = message.split("/")
    # First tokens should have some mandatory stuff
    station, valid = parse_station_valid(tokens[0], prod.utcnow)
    elements = []
    data_created = None
    for text in tokens[1:]:
        text = text.strip()
        pe = text[:2]
        if pe == "DC":
            data_created = parse_datetime(text[2:], valid)
            for elem in elements:
                elem.data_created = data_created
            continue
        elements.append(
            SHEFElement(
                station=station,
                valid=valid,
                physical_element=pe,
                data_created=data_created,
                str_value=text.split()[1],
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
        if messages and line.startswith(".E"):  # continuation
            messages[-1] += f" {line.split(maxsplit=1)[1]}"
    # We have messages to parse into objects
    for message in messages:
        res = process_message_e(prod, message)
        if res:
            prod.data.extend(res)


def str_convert(text):
    """Attempt to make this into a float."""
    try:
        return float(text)
    except ValueError:
        LOG.info("Converting '%s' to float failed", text)
        return None


def _parse(prod):
    """Do what is necessary to get this product parsed."""
    # Products could have multiple types, so conditionally run each parser
    if prod.unixtext.find(".A") > -1:
        parse_A(prod)
    if prod.unixtext.find(".B") > -1:
        parse_B(prod)
    # NOTE The .END from .B Format is a false positive here...
    if prod.unixtext.find(".E") > -1:
        parse_E(prod)
    # Safely do numeric conversions
    for element in prod.data:
        element.num_value = str_convert(element.str_value)


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
