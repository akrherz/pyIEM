"""Very light weight WMO header parser."""

# Be frugal with the imports to keep speed and memory down!
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from pyiem.exceptions import TextProductException
from pyiem.reference import name2pytz, offsets
from pyiem.util import LOG, ddhhmm2datetime

TIME_FMT = (
    "([0-9:]+) (AM|PM) ([A-Z][A-Z][A-Z]?T) ([A-Z][A-Z][A-Z]) "
    "([A-Z][A-Z][A-Z]) ([0-9]+) ([1-2][0-9][0-9][0-9])"
)
TIME_RE = re.compile(f"^{TIME_FMT}$", re.M | re.IGNORECASE)
TIME_UTC_RE = re.compile(
    TIME_FMT.replace("(AM|PM) ([A-Z][A-Z][A-Z]?T)", r"(AM|PM)?\s?(UTC)"),
    re.M | re.I,
)
# Sometimes products have a duplicated timestamp in another tz
TIME_EXT_RE = re.compile(
    rf"^{TIME_FMT}\s?/\s?{TIME_FMT}\s?/$", re.M | re.IGNORECASE
)
# Without the line start and end requirement
TIME_RE_ANYWHERE = re.compile(f"{TIME_FMT}", re.IGNORECASE)
TIME_STARTS_LINE = re.compile(r"^([0-9:]+) (AM|PM)")

# It is supposed to have a blank space, but alas
LDM_SEQUENCE_RE = re.compile(r"^\d\d\d\s?")

# Note that bbb of RTD is supported here, but does not appear to be allowed
WMO_RE = re.compile(
    "^(?P<ttaaii>[A-Z0-9]{4,6}) (?P<cccc>[A-Z]{4}) "
    r"(?P<ddhhmm>[0-3][0-9][0-2][0-9][0-5][0-9])\s*"
    r"(?P<bbb>[ACR][ACMORT][A-Z])?\s*$",
    re.M,
)
# The AWIPS Product Identifier is supposed to be 6chars as per directive,
# but in practice it is sometimes something between 4 and 6 chars
# We need to be careful this does not match the LDM sequence identifier
AFOSRE = re.compile(r"^([A-Z0-9]{4,6})\s*\t*$", re.M)

KNOWN_BAD_TTAAII = ["KAWN"]


def date_tokens2datetime(tokens):
    """Convert tokens from MND regex to a valid time, if possible.

    Returns:
      z (str): 3-4 char timezone string
      tz (datetime.timezone): of this product
      utcvalid (datetimetz): of this product
    """
    tokens = list(tokens)  # ensure mutable
    z = tokens[2].upper()
    tz = ZoneInfo(name2pytz.get(z, "UTC"))
    hhmi = tokens[0]
    # False positive from regex
    if hhmi[0] == ":":
        hhmi = hhmi.replace(":", "")
    if hhmi.find(":") > -1:
        (hh, mi) = hhmi.split(":")
    elif len(hhmi) < 3:
        hh = hhmi
        mi = 0
    else:
        hh = hhmi[:-2]
        mi = hhmi[-2:]
    # Workaround another 24 hour clock issue
    if (
        tokens[2] in ["UTC", "GMT"]
        and tokens[1].upper() == "AM"
        and int(hh) == 12
    ):
        hh = 0
    # Workaround 24 hour clock abuse
    if int(hh) >= 12 and (
        tokens[1].upper() == "PM" or tokens[2] in ["UTC", "GMT"]
    ):
        # this is a hack to ensure this is PM when we are in UTC
        tokens[1] = "PM"
        hh = int(hh) - 12
    dstr = (
        f"{hh if int(hh) > 0 else 12}:{mi} "
        f"{tokens[1] if tokens[1] != '' else 'AM'} "
        f"{tokens[4]} {tokens[5]} {tokens[6]}"
    )
    # Careful here, need to go to UTC time first then come back!
    now = datetime.strptime(dstr, "%I:%M %p %b %d %Y")
    now += timedelta(hours=offsets.get(z, 0))
    return z, tz, now.replace(tzinfo=timezone.utc)


def _condition_text(text: str) -> str:
    """Condition the text to better match expections on what this should be.

    Args:
      text (str): The text to condition

    Returns:
      str: The conditioned text
    """
    # Remove all Carriage Returns
    text = text.replace("\r", "")
    # Remove all leading and trailing whitespace
    text = text.strip()
    # Remove the line if it starts with a start of product marker
    if text.startswith("\001"):
        text = text.split("\n", 1)[1]
    # Now the first line should be the LDM sequence number
    if not LDM_SEQUENCE_RE.match(text):
        # If not, add it
        text = f"000 \n{text}"
    # The second line should match the WMO header, this is FATAL
    line2 = text.split("\n")[1]
    if not WMO_RE.match(line2):
        msg = f"FATAL: Could not parse WMO header! `{line2}`"
        raise TextProductException(msg)
    # Remove the end of product marker
    text = text.rstrip("\003")
    # Ensure we have a newline at the end
    if not text.endswith("\n"):
        text = text + "\n"
    # Profit
    return text


class WMOProduct:
    """Base class for Products with a WMO Header."""

    def __init__(self, text: str, utcnow: Optional[datetime] = None):
        """Constructor."""
        self.warnings = []
        # Maintain the original text minus the null byte
        self.text = text.replace("\x00", "")
        # This is where opinionated things happen
        self.unixtext = _condition_text(self.text)
        self.source = None
        self.wmo = None
        self.ddhhmm = None
        self.bbb = None
        self.afos = None
        # A potentially localized timestamp
        self.valid = None
        # The WMO header based timestamp
        self.wmo_valid = None
        self.utcnow = utcnow
        if utcnow is None:
            self.utcnow = datetime.now(timezone.utc)
        else:
            # make sure this is actualing in UTC
            self.utcnow = self.utcnow.astimezone(timezone.utc)
        self.z = None
        self.tz = None
        self.parse_wmo()
        self.parse_afos()
        # Here lies dragons
        # We sometimes need the MND header to figure out the timestamp
        # of the WMO header.
        self._parse_valid(utcnow)

    def parse_afos(self):
        """Figure out what the AFOS PIL is"""
        # We have one shot to get this right
        line3 = self.unixtext.split("\n")[2]
        tokens = AFOSRE.findall(line3)
        if tokens:
            self.afos = tokens[0].strip()

    def get_product_id(self):
        """Get an identifier of this product used by the IEM"""
        pid = f"{self.valid:%Y%m%d%H%M}-{self.source}-{self.wmo}-{self.afos}"
        if self.bbb:
            pid += f"-{self.bbb}"
        return pid.strip()

    def parse_wmo(self):
        """Parse things related to the WMO header"""
        # The conditioning step in init should ensure this works
        search = WMO_RE.search(self.unixtext[:100])
        gdict = search.groupdict()
        self.wmo = gdict["ttaaii"]
        self.source = gdict["cccc"]
        self.ddhhmm = gdict["ddhhmm"]
        self.bbb = gdict["bbb"]
        if len(self.wmo) == 4:
            # Don't whine about known problems
            if (
                self.source not in KNOWN_BAD_TTAAII
                and not self.source.startswith("S")
            ):
                self.warnings.append(
                    f"WMO ttaaii found four chars: {self.wmo} {self.source} "
                    "adding 00"
                )
            self.wmo += "00"

    def _parse_valid(self, provided_utcnow: datetime):
        """Figure out the timestamp of this product.

        Args:
          provided_utcnow (datetime): What our library was provided for the UTC
            timestamp, it could be None
        """
        # The MND header hopefully has a full timestamp that is the best
        # truth that we can have for this product.
        subject = self.text.replace("\r", "")[:1000]  # Likely too much
        tokens = TIME_RE.findall(subject)
        if not tokens:
            tokens = TIME_EXT_RE.findall(subject)
            if not tokens:
                tokens = TIME_RE_ANYWHERE.findall(subject)
                if not tokens:
                    tokens = TIME_UTC_RE.findall(subject)
                    if not tokens:
                        # We are very desperate at this point, evasive action
                        for line in subject.split("\n")[:15]:
                            if TIME_STARTS_LINE.match(line):
                                # Remove anything inside of () or //
                                line = re.sub(r" \(.*?\)", "", line)
                                line = re.sub(r" /.*?/", "", line)
                                tokens = TIME_RE.findall(line)
                                break
        if provided_utcnow is None and tokens:
            try:
                z, _tz, valid = date_tokens2datetime(tokens[0])
                if z not in offsets:
                    self.warnings.append(f"product timezone '{z}' unknown")
            except ValueError as exp:
                msg = (
                    f"Invalid timestamp [{' '.join(tokens[0])}] found in "
                    f"product [{self.wmo} {self.source}] header"
                )
                raise TextProductException(self.source[1:], msg) from exp

            # Set the utcnow based on what we found by looking at the header
            self.utcnow = valid

        # Search out the WMO header, this had better always be there
        # We only care about the first hit in the file, searching from top
        # Take the first hit, ignore others
        self.wmo_valid = ddhhmm2datetime(self.ddhhmm, self.utcnow)

        # we can do no better
        self.valid = self.wmo_valid

        # If we don't find anything, lets default to now, its the best
        if not tokens:
            return
        self.z, self.tz, self.valid = date_tokens2datetime(tokens[0])
        # We want to forgive two easy situations
        offset = (self.valid - self.wmo_valid).total_seconds()
        # 1. self.valid is off from WMO by approximately 12 hours (am/pm flip)
        if 42900 <= offset <= 43800:
            LOG.info(
                "Auto correcting AM/PM typo, %s -> %s",
                self.valid,
                self.wmo_valid,
            )
            self.warnings.append(
                "Detected AM/PM flip, adjusting product timestamp - 12 hours"
            )
            self.valid = self.valid - timedelta(hours=12)
        # 2. self.valid is off by approximate 1 year (year typo)
        if -367 * 86400 < offset < -364 * 86400:
            LOG.info(
                "Auto correcting year typo, %s -> %s",
                self.valid,
                self.wmo_valid,
            )
            self.warnings.append(
                "Detected year typo, adjusting product timestamp + 1 year"
            )
            self.valid = self.valid.replace(year=self.valid.year + 1)
