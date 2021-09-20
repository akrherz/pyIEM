"""Standard Hydrological Exchange Format (SHEF).

https://www.weather.gov/media/mdl/SHEF_CodeManual_5July2012.pdf

Formats
-------
.A - single station, multiple parameter
.B - multiple station, multiple parameter, header driven
.E - single station, single parameter, evenly spaced time series

TODO List
---------
 - Table 7 has defaults for PEDTSEP
 - Table 2 has the two character send-codes used for PE starting with S
 - 4.4.3 data duration values DV*
 - 4.1.2 the four codes to handle what lat/lon mean in the encoding
 - 4.4.4 DIE special end-of-month specifier
 - 4.4.5 DU data units
 - 4.4.6 DQ data qualifier code  Table 10
 - Table 10 qualifier codes
 - 5.1.2 Precipitation Data !important
 - 5.1.4 how to handle repeated data
 - Handle when R is being specified
 - 5.1.6 revision of a missing value
 - 5.2.1 DR codes, DRE end of month
 - 5.2.6 evolving time
 - Table 9a D codes


"""
try:
    from zoneinfo import ZoneInfo  # type: ignore
except ImportError:
    from backports.zoneinfo import ZoneInfo
from datetime import date, timezone, datetime, timedelta
import re
from typing import List

from pyiem.exceptions import InvalidSHEFEncoding
from pyiem.models.shef import SHEFElement
from pyiem.nws.product import TextProduct
from pyiem.util import LOG

INLINE_COMMENT_RE = re.compile(":.*:")
# TODO 4.1.5/5.2.5 the two character fields likely define fixed offsets
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
PAIRED_PHYSICAL_CODES = "HQ MD MN MS MV NO ST TB TE TV".split()


def make_date(text, now):
    """Make the text date unambiguous!"""
    if now is None:
        now = date.today()
    if len(text) < 4:
        raise InvalidSHEFEncoding(f"D* text too short '{text}'")
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
    if len(text) == 6:
        return basevalid.replace(
            month=int(text[:2]),
            day=int(text[2:4]),
            hour=int(text[4:]),
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


def datetime24(dt, replacements):
    """Handle the junkiness that is a `24` hour."""
    # dt could be a date
    if dt.__class__.__name__ == "date":
        dt = datetime(dt.year, dt.month, dt.day)
    if int(replacements.get("hour", 0)) == 24:
        dt = dt + timedelta(days=1)
        replacements["hour"] = 0
    return datetime(
        replacements.get("year", dt.year),
        replacements.get("month", dt.month),
        replacements.get("day", dt.day),
        replacements.get("hour", dt.hour),
        replacements.get("minute", dt.minute),
        replacements.get("second", dt.second),
        replacements.get("microsecond", dt.microsecond),
        replacements.get("tzinfo", dt.tzinfo),
    )


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
    replacements = {"tzinfo": tzinfo}
    if tokens[-1].startswith("DH"):
        meat = tokens[-1][2:]
        if len(meat) == 4:
            replacements["hour"] = int(meat[:2])
            replacements["minute"] = int(meat[2:])
        elif len(meat) == 2:
            replacements["hour"] = int(meat[:2])
            replacements["minute"] = 0
        elif len(meat) == 6:
            replacements["hour"] = int(meat[:2])
            replacements["minute"] = int(meat[2:4])
            replacements["second"] = int(meat[4:6])
        else:
            raise ValueError(f"No logic to parse '{meat}'")
    else:
        # SHEF MANUAL SEZ
        replacements["hour"] = 12 if tzinfo == timezone.utc else 0
    valid = datetime24(valid, replacements)
    return station, valid


def process_message_e(message, utcnow=None) -> List[SHEFElement]:
    """Process a text string in E SHEF format.

    Args:
      message (str): The string to parse.
      utcnow (datetime): The best guess (product.utcnow) at current timestamp.

    Returns:
      List(SHEFElement)
    """
    tokens = message.split("/")
    station, basevalid = parse_station_valid(tokens[0], utcnow)
    elements = []
    # Iterate through the next tokens and hopefully find DI
    interval = timedelta(seconds=0)
    datastart = None
    physical_element = None
    data_created = None
    for i, token in enumerate(tokens[1:], 1):
        if token.startswith("DC"):
            data_created = parse_datetime(token[2:], basevalid)
            continue
        if token.startswith("DH"):
            replacements = {"hour": int(token[2:4])}
            if len(token) == 6:
                replacements["minute"] = int(token[4:6])
            basevalid = datetime24(basevalid, replacements)
        elif token.startswith("DI"):
            parts = token.strip().split()
            if token[2] == "H":
                interval = timedelta(hours=int(parts[0][3:]))
            elif token[2] == "D":
                interval = timedelta(days=int(parts[0][3:]))
            elif token[2] == "N":
                interval = timedelta(minutes=int(parts[0][3:]))
            else:
                raise ValueError(f"Unhandled DI of '{token[2]}")
            datastart = i + 1
            if len(parts) > 1:
                # Insert second value back into tokens
                tokens.insert(i + 1, parts[1])
            break
        if token[0].isalpha():
            physical_element = token[:2]
    valid = basevalid
    for token in tokens[datastart:]:
        res = token.strip().split()
        if not res:
            res = [""]
        for tokens2 in res:
            elem = SHEFElement(
                station=station,
                valid=valid,
                physical_element=physical_element,
                str_value=tokens2,
                data_created=data_created,
            )
            compute_num_value(elem)
            elements.append(elem)
            valid += interval

    return elements


def strip_comments(line):
    """Remove comments."""
    # Cull inline comments using ON/OFF nomenclature
    pos = line.find(":")
    while pos > -1:
        pos2 = line[pos + 1 :].find(":")
        if pos2 > -1:
            line = line[:pos] + line[pos + pos2 + 2 :]
        else:
            # Unbalanced
            line = line[:pos]
        pos = line.find(":")
    return line


def clean_b_headerline(text):
    """Account for invalid encoding. SIGH."""
    tokens = text.split("/")
    firstparts = tokens[0].strip().split()
    # Inspect the last element and see if it is alpha, but not start with D
    if firstparts[-1][0].isalpha() and firstparts[-1][0] != "D":
        # Missing /
        tokens[0] = " ".join(firstparts[:-1]) + "/" + firstparts[-1]
    return "/".join(tokens)


def process_message_b(message, utcnow=None):
    """Convert the message into an object."""
    # line one has the magic
    lines = message.split("\n")
    headerline = clean_b_headerline(lines[0])
    tokens = headerline.split("/")
    _center, valid = parse_station_valid(tokens[0], utcnow)
    # valid time could be modified as we progress with the header
    physical_elements = []
    valids = []
    unit_convention = "E"
    unit_conventions = []
    data_created = None
    for token in tokens[1:]:
        token = token.strip()
        if token == "":
            continue
        pe = token[:2]
        if pe[0] == "D":
            # Modifying time as we go here
            if pe == "DM":
                # Updating the timestamp as we go here
                replacements = {
                    "month": int(token[2:4]),
                    "day": int(token[4:6]),
                }
                if len(token) == 8:
                    replacements["hour"] = int(token[6:8])
                valid = datetime24(valid, replacements)
            elif pe == "DH":
                # Updating the timestamp as we go here
                replacements = {
                    "hour": int(token[2:4]),
                }
                valid = datetime24(valid, replacements)
            elif pe == "DR":
                if token[2] == "H":
                    valid += timedelta(hours=int(token[3:]))
                elif token[2] == "N":
                    valid += timedelta(minutes=int(token[3:]))
            elif pe == "DU":
                unit_convention = token[2]
            elif pe == "DC":
                data_created = parse_datetime(token[2:], valid)
            else:
                raise ValueError(f"Unhandled D code {pe} for B format")
            continue
        unit_conventions.append(unit_convention)
        physical_elements.append(token.strip()[:2])
        valids.append(valid)
    elements = []
    for line in lines[1:]:
        line = strip_comments(line)
        if line.strip() == "" or line.startswith(".END"):
            continue
        # packed B format, LE SIGH
        for section in line.split(","):
            # Account for // oddity
            section = section.strip()
            # Hack around a tough edge case
            if section.endswith("//"):
                section = section[:-2] + "/ "
            tokens = section.strip().replace("//", "/ /").split("/")
            station = tokens[0].split()[0]
            vals = []
            for token in tokens:
                text = token.replace(station, "").strip()
                # 5.2.2 Observational time change via DM nomenclature
                if text.startswith("D"):
                    if text.startswith("DM"):
                        valids[0] = parse_datetime(text[2:], valids[0])
                    elif text.startswith("DH"):
                        replacements = {"hour": int(text[2:4])}
                        if len(text) == 6:
                            replacements["minute"] = int(text[4:6])
                        valids[0] = datetime24(valids[0], replacements)
                else:
                    vals.append(text)
            for i, text in enumerate(vals):
                # Ignore vague case with trailing /
                if i == len(valids) and text.strip() == "":
                    continue
                elem = SHEFElement(
                    station=station,
                    valid=valids[i],
                    physical_element=physical_elements[i],
                    unit_convention=unit_conventions[i],
                    str_value=text.strip(),
                    data_created=data_created,
                )
                compute_num_value(elem)
                elements.append(elem)
    return elements


def process_message_a(message, utcnow=None):
    """Convert the message into an object."""
    tokens = message.split("/")
    # Too short
    if len(tokens) == 1:
        return []
    # First tokens should have some mandatory stuff
    station, valid = parse_station_valid(tokens[0], utcnow)
    elements = []
    data_created = None
    unit_convention = "E"
    for text in tokens[1:]:
        text = text.strip()
        if text == "":
            continue
        pe = text[:2]
        if pe[0] == "D":
            # Modififers not to be explicitly stored as elements
            if pe == "DC":
                data_created = parse_datetime(text[2:], valid)
                for elem in elements:
                    elem.data_created = data_created
            elif pe == "DM":
                # Updating the timestamp as we go here
                replacements = {
                    "month": int(text[2:4]),
                    "day": int(text[4:6]),
                }
                if len(text) == 8:
                    replacements["hour"] = int(text[6:8])
                valid = datetime24(valid, replacements)
            elif pe == "DD":
                # Updating the timestamp as we go here
                replacements = {
                    "day": int(text[2:4]),
                }
                if len(text) >= 6:
                    replacements["hour"] = int(text[4:6])
                if len(text) >= 8:
                    replacements["minute"] = int(text[6:8])
                valid = datetime24(valid, replacements)
            elif pe == "DH":
                # Updating the timestamp as we go here
                replacements = {
                    "hour": int(text[2:4]),
                }
                if len(text) >= 6:
                    replacements["minute"] = int(text[4:6])
                valid = datetime24(valid, replacements)
            elif pe == "DU":
                unit_convention = text[2]
            else:
                raise ValueError(f"Unhandled D code {pe[0]}")
            continue

        elem = SHEFElement(
            station=station,
            valid=valid,
            physical_element=pe,
            data_created=data_created,
            str_value=text.split()[1],
            unit_convention=unit_convention,
        )
        compute_num_value(elem)
        elements.append(elem)

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
        res = process_message_a(message, prod.utcnow)
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
        res = process_message_b(message, prod.utcnow)
        if res:
            prod.data.extend(res)


def parse_E(prod):
    """Parse E format SHEF data."""
    messages = []
    for line in prod.unixtext.split("\n"):
        # New Message!
        if line.startswith(".ER ") or line.startswith(".E "):
            messages.append(strip_comments(line))
            continue
        if messages and line.startswith(".E"):  # continuation
            if not messages[-1].endswith("/"):
                messages[-1] += "/"
            messages[-1] += f" {strip_comments(line.split(maxsplit=1)[1])}"
    # We have messages to parse into objects
    for message in messages:
        res = process_message_e(message, prod.utcnow)
        if res:
            prod.data.extend(res)


def compute_num_value(element):
    """Attempt to make this into a float."""
    # 5.1.1
    if element.str_value in ["-9999", "M", "MM", ""]:
        return
    if element.str_value.endswith("E"):
        element.estimated = True
        element.str_value = element.str_value[:-1]
    # 7.4.6 Paired Element!
    if element.physical_element in PAIRED_PHYSICAL_CODES:
        # <depth>.<value>
        value = int(element.str_value.split(".")[1])
        depth = int(element.str_value.split(".")[0])
        if depth < 0:
            value *= -1
            depth *= -1
        element.depth = depth
        # Missing is -9999
        if value > -9998:
            element.num_value = value
        return
    try:
        element.num_value = float(element.str_value)
    except ValueError:
        LOG.info("Converting '%s' to float failed", element.str_value)


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
