"""Very light weight WMO header parser."""

# Be frugal with the imports to keep speed and memory down!
import re
from datetime import datetime, timezone
from typing import Optional

from pyiem.exceptions import TextProductException

# Note that bbb of RTD is supported here, but does not appear to be allowed
WMO_RE = re.compile(
    "^(?P<ttaaii>[A-Z0-9]{4,6}) (?P<cccc>[A-Z]{4}) "
    r"(?P<ddhhmm>[0-3][0-9][0-2][0-9][0-5][0-9])\s*"
    r"(?P<bbb>[ACR][ACMORT][A-Z])?\s*$",
    re.M,
)
KNOWN_BAD_TTAAII = ["KAWN"]


class WMOProduct:
    """Base class for Products with a WMO Header."""

    def __init__(self, text, utcnow: Optional[datetime] = None):
        """Constructor."""
        self.warnings = []
        # For better or worse, ensure the text string ends with a newline
        if not text.endswith("\n"):
            text = text + "\n"
        self.text = text
        self.source = None
        self.wmo = None
        self.ddhhmm = None
        self.bbb = None
        # The WMO header based timestamp
        self.wmo_valid = None
        self.utcnow = utcnow
        if utcnow is None:
            self.utcnow = datetime.now(timezone.utc)
        else:
            # make sure this is actualing in UTC
            self.utcnow = self.utcnow.astimezone(timezone.utc)
        self.parse_wmo()

    def parse_wmo(self):
        """Parse things related to the WMO header"""
        search = WMO_RE.search(self.text[:100])
        if search is None:
            raise TextProductException(
                f"FATAL: Could not parse WMO header! '{self.text[:100]}'"
            )
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
