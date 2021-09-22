"""Standard Hydrological Exchange Format (SHEF).

https://www.weather.gov/media/mdl/SHEF_CodeManual_5July2012.pdf

Formats
-------
.A - single station, multiple parameter
.B - multiple station, multiple parameter, header driven
.E - single station, single parameter, evenly spaced time series

Implementation Notes
--------------------

- The IEM uses a nomenclature of 0.0001 float value to represent Trace values,
not the 0.001 that SHEF does.

TODO List
---------
 - Table 7 has defaults for PEDTSEP
 - Table 2 has the two character send-codes used for PE starting with S
 - 4.1.2 the four codes to handle what lat/lon mean in the encoding
 - 4.4.4 DIE special end-of-month specifier
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
from io import StringIO
import traceback
from typing import List

from pyiem.exceptions import InvalidSHEFEncoding
from pyiem.models.shef import SHEFElement
from pyiem.nws.product import TextProduct
from pyiem.reference import TRACE_VALUE
from pyiem.util import LOG

# Table 8
TIMEZONES = {
    "C": "America/Chicago",
    "CD": "Etc/GMT+5",
    "CS": "Etc/GMT+6",
    "N": "Canada/Newfoundland",
    # "NS": "Unsupported +2.5",
    "A": "Canada/Atlantic",
    "AD": "Etc/GMT+3",
    "AS": "Etc/GMT+4",
    "E": "America/New_York",
    "ED": "Etc/GMT+4",
    "ES": "Etc/GMT+5",
    "J": "Etc/GMT-8",
    "M": "America/Denver",
    "MD": "Etc/GMT+6",
    "MS": "Etc/GMT+7",
    "P": "America/Los_Angeles",
    "PD": "Etc/GMT+7",
    "PS": "Etc/GMT+8",
    "Y": "Canada/Yukon",
    "YD": "Etc/GMT+7",
    "YS": "Etc/GMT+8",
    "H": "US/Hawaii",
    "HS": "Etc/GMT+10",
    "L": "US/Alaska",
    "LD": "Etc/GMT+8",
    "LS": "Etc/GMT+9",
    "B": "Asia/Anadyr",
    "BD": "Etc/GMT+9",
    "BS": "Etc/GMT+10",
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
    # TODO better handle year and century here, add tests around 1 Jan
    valid = basevalid.replace(
        month=int(text[-8:-6]),
        day=int(text[-6:-4]),
        hour=int(text[-4:-2]),
        minute=int(text[-2:]),
    )
    return valid


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
    """Parse the first token found in a SHEF observation.

    Args:
      text (str): the first part of the string
      utcnow (datetime): The default time.

    Returns:
      str, datetime, list
    """
    tokens = text.split()
    station = tokens[1]
    # Ensure that station is not all digits as we are likely missing station
    if all(x.isdigit() for x in station):
        raise InvalidSHEFEncoding(f"3.1 No station in '{text}'")
    timestamp = tokens[2]
    if all(x.isalpha() for x in timestamp):
        raise InvalidSHEFEncoding(f"3.2 No timestamp in '{text}'")
    # Ensure that the timestamp is all numbers
    valid = make_date(timestamp, utcnow)
    # 4.1.4 Timezone is optional, default to Z
    if len(tokens) >= 4 and tokens[3] in TIMEZONES:
        tzinfo = ZoneInfo(TIMEZONES[tokens[3]])
        startidx = 4
    else:
        tzinfo = timezone.utc
        startidx = 3
    extra = []
    # Look to see what we have here, saving off extra things we can not parse
    if len(tokens) == startidx:
        replacements = {"tzinfo": tzinfo}
        replacements["hour"] = 12 if tzinfo == timezone.utc else 0
        valid = datetime24(valid, replacements)
        return station, valid, extra
    workdone = False
    for token in tokens[startidx:]:
        pe = token[:2]
        # Default replacement from above
        replacements = {"tzinfo": tzinfo}
        if pe.startswith("DH"):
            meat = token[2:]
            if len(meat) == 4:
                replacements["hour"] = int(meat[:2])
                replacements["minute"] = int(meat[2:])
            elif len(meat) == 2:
                replacements["hour"] = int(meat[:2])
                replacements["minute"] = 0
            else:
                replacements["hour"] = int(meat[:2])
                replacements["minute"] = int(meat[2:4])
                replacements["second"] = int(meat[4:6])
            valid = datetime24(valid, replacements)
            workdone = True
        elif pe.startswith("DM"):
            meat = token[2:]
            if len(meat) == 6:
                replacements["month"] = int(meat[:2])
                replacements["day"] = int(meat[2:4])
                replacements["hour"] = int(meat[4:6])
            valid = datetime24(valid, replacements)
            workdone = True
        else:
            extra.append(token)
    if not workdone:
        # SHEF MANUAL SEZ
        replacements = {"tzinfo": tzinfo}
        replacements["hour"] = 12 if tzinfo == timezone.utc else 0
        valid = datetime24(valid, replacements)
    return station, valid, extra


def process_di(text):
    """Convert a DI value into an interval."""
    parts = text.strip().split()
    if text[2] == "H":
        args = {"hours": int(parts[0][3:])}
    elif text[2] == "D":
        args = {"days": int(parts[0][3:])}
    elif text[2] == "N":
        args = {"minutes": int(parts[0][3:])}
    else:
        raise ValueError(f"Unhandled DI of '{text}")
    return timedelta(**args)


def process_modifiers(text, diction, basevalid):
    """Apply modifications based on what the token is telling us.

    Args:
      text (str): Potential new information.
      diction (SHEFElement): our current elemenet definition
      basevalid (datetime): the base valid in case of relative time.

    Returns:
      bool for if this text was handled.
    """
    if text.startswith("DI"):
        # Handled by process_message_e code
        return False
    if not text.startswith("D"):
        return False
    if text.startswith("DC"):
        diction.data_created = parse_datetime(text[2:], diction.valid)
    elif text.startswith("DD"):
        # Updating the timestamp as we go here
        replacements = {
            "day": int(text[2:4]),
        }
        if len(text) >= 6:
            replacements["hour"] = int(text[4:6])
        if len(text) >= 8:
            replacements["minute"] = int(text[6:8])
        diction.valid = datetime24(diction.valid, replacements)

    elif text.startswith("DH"):
        replacements = {"hour": int(text[2:4])}
        if len(text) == 6:
            replacements["minute"] = int(text[4:6])
        diction.valid = datetime24(diction.valid, replacements)
    elif text.startswith("DM"):
        # Updating the timestamp as we go here
        replacements = {
            "month": int(text[2:4]),
            "day": int(text[4:6]),
        }
        if len(text) >= 8:
            replacements["hour"] = int(text[6:8])
        if len(text) >= 10:
            replacements["minute"] = int(text[8:10])
        diction.valid = datetime24(diction.valid, replacements)
    elif text.startswith("DQ"):
        diction.qualifier = text[2]
    elif text.startswith("DU"):
        diction.unit_convention = text[2]
    elif text.startswith("DV"):
        # Table 11a
        val = text[2]
        reps = {
            "S": "seconds",
            "N": "minutes",
            "H": "hours",
            "D": "days",
            "M": "months",
            "Y": "years",
        }
        if val in reps:
            replace = {reps[val]: int(text[3:])}
            diction.dv_interval = timedelta(**replace)
        else:
            raise ValueError(f"Unsupported DV code {text}")
    elif text.startswith("DR"):
        if text[2] == "H":
            diction.valid = basevalid + timedelta(hours=int(text[3:]))
        elif text[2] == "D":
            diction.valid = basevalid + timedelta(days=int(text[3:]))
    else:
        raise ValueError(f"Unhandled D variable {text}")
    return True


def process_message_e(message, utcnow=None) -> List[SHEFElement]:
    """Process a text string in E SHEF format.

    Args:
      message (str): The string to parse.
      utcnow (datetime): The best guess (product.utcnow) at current timestamp.

    Returns:
      List[SHEFElement]
    """
    tokens = message.split("/")
    # In the first token, we should find some information about the station
    # and timing.  Otherstuff could be here as well
    station, valid, extra = parse_station_valid(tokens[0], utcnow)
    tokens = tokens[1:]
    if extra:
        extra.extend(tokens)
        tokens = extra
    elements = []
    # Iterate through the next tokens and hopefully find DI
    interval = timedelta(seconds=0)
    # Create element object to track as we parse through the message
    diction = SHEFElement(station=station, valid=valid)
    for token in tokens:
        token = token.lstrip()
        if process_modifiers(token, diction, valid):
            continue
        if token.startswith("DI"):
            interval = process_di(token)
            continue
        # There can only be one physical element for E messages
        if diction.physical_element is None and token[0].isalpha():
            diction.consume_code(token)
            continue
        # We should be dealing with data now?
        res = token.strip().split()
        if not res:
            res = [""]
        for tokens2 in res:
            elem = diction.copy()
            elem.str_value = tokens2
            compute_num_value(elem)
            elements.append(elem)
            diction.valid += interval
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
    _center, valid, extra = parse_station_valid(tokens[0], utcnow)
    tokens = tokens[1:]
    if extra:
        extra.extend(tokens)
        tokens = extra
    # Keep track of our dictions.
    dictions = []
    current_diction = SHEFElement(station="NA", valid=valid)
    for token in tokens:
        token = token.strip()
        if token == "":
            continue
        if process_modifiers(token, current_diction, valid):
            continue
        # Else, we have a new diction!
        current_diction.consume_code(token)
        # Set it into our dictions
        dictions.append(current_diction.copy())
    # Add silly one to prevent an off-by-one
    dictions.append(None)
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
            dictioni = 0
            diction = dictions[dictioni]
            for i, text in enumerate(tokens):
                if i == 0:
                    text = text.replace(station, "").strip()
                # 5.2.2 Observational time change via DM nomenclature
                if text.startswith("D"):
                    # Uh oh, local diction modifier, sigh
                    diction = diction.copy()
                    process_modifiers(text, diction, valid)
                    continue
                # Extra trailing garbage
                if text == "" and diction is None:
                    continue
                elem = diction.copy()
                elem.station = station
                elem.str_value = text.strip()
                compute_num_value(elem)
                elements.append(elem)
                dictioni += 1
                diction = dictions[dictioni]
    return elements


def process_message_a(message, utcnow=None):
    """Convert the message into an object."""
    tokens = message.split("/")
    # Too short
    if len(tokens) == 1:
        return []
    # First tokens should have some mandatory stuff
    station, valid, extra = parse_station_valid(tokens[0], utcnow)
    tokens = tokens[1:]
    if extra:
        extra.extend(tokens)
        tokens = extra
    elements = []
    diction = SHEFElement(station=station, valid=valid)
    for text in tokens:
        text = text.strip()
        if text == "":
            continue
        if process_modifiers(text, diction, valid):
            continue
        parts = text.split()
        elem = diction.copy()
        elem.consume_code(text)
        elem.str_value = "" if len(parts) == 1 else parts[1]
        compute_num_value(elem)
        elements.append(elem)

    # Back-assign DC if it was found.
    if diction.data_created is not None:
        for elem in elements:
            elem.data_created = diction.data_created

    return elements


def process_messages(func, prod, messages) -> int:
    """Safe frontend to do message processing."""
    errors = 0
    for message in messages:
        if errors > 5:
            prod.warnings.append("Aborting processing with too many errors")
            break
        try:
            res = func(message, prod.utcnow)
            if res:
                prod.data.extend(res)
        except InvalidSHEFEncoding as exp:
            # Swallow these generally :/
            errors += 1
            LOG.info("%s for '%s' %s", exp, message, prod.get_product_id())
        except Exception as exp:
            errors += 1
            cstr = StringIO()
            cstr.write(f"Processing '{message}' traceback:\n")
            traceback.print_exc(file=cstr)
            LOG.error(exp)
            cstr.seek(0)
            prod.warnings.append(cstr.getvalue())
    return len(prod.data)


def parse_A(prod):
    """Parse A format SHEF data."""
    # Line by Line collecting up what we find!
    messages = []
    for line in prod.unixtext.split("\n"):
        # New Message!
        if line.startswith(".AR ") or line.startswith(".A "):
            messages.append(strip_comments(line))
            continue
        if line.startswith(".A"):  # continuation
            messages[-1] += f"/{strip_comments(line).split(maxsplit=1)[1]}"

    process_messages(process_message_a, prod, messages)


def parse_B(prod):
    """Parse B format SHEF data."""
    # Messages here are a bit special as it starts with .B and ends with .END
    messages = []

    inmessage = False
    for line in prod.unixtext.split("\n"):
        # New Message!
        if line.startswith(".BR ") or line.startswith(".B "):
            messages.append(line.strip())
            inmessage = True
            continue
        if inmessage and line.startswith(".B"):
            meat = line.split(maxsplit=1)[1].strip()
            if not messages[-1].endswith("/") and not meat.startswith("/"):
                messages[-1] += "/"
            # We have more headers, gasp
            messages[-1] += meat
            continue
        if line.startswith(".END"):
            inmessage = False
            continue
        if inmessage:
            messages[-1] += "\n" + line

    process_messages(process_message_b, prod, messages)


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

    process_messages(process_message_e, prod, messages)


def compute_num_value(element):
    """Attempt to make this into a float."""
    # 5.1.1
    if element.str_value in ["-9999", "M", "MM", ""]:
        return
    # Can trace
    if element.str_value == "T":
        element.num_value = TRACE_VALUE
        return
    # 4.4.7 Data Elements
    if element.str_value[-1].isalpha():
        element.qualifier = element.str_value[-1]
        element.str_value = element.str_value[:-1]
    # 7.4.6 Paired Element!
    if element.physical_element in PAIRED_PHYSICAL_CODES:
        tokens = element.str_value.split(".")
        if len(tokens) == 1:
            element.depth = int(tokens[0])
            return
        # <depth>.<value>
        value = int(tokens[1])
        depth = int(tokens[0])
        if depth < 0:
            value *= -1
            depth *= -1
        element.depth = depth
        # Missing is -9999
        if value > -9998:
            element.num_value = value
        return
    element.num_value = float(element.str_value)
    # 5.1.2 Precip Trace
    if (
        element.physical_element in ["PC", "PP", "PY"]
        and element.num_value
        and abs(element.num_value - 0.001) < 0.0001
    ):
        element.num_value = TRACE_VALUE


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
