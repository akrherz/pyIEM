"""Process HVTEC encoding."""
import re
from datetime import timezone, datetime

from pyiem.util import LOG
from pyiem.nws.nwsli import NWSLI

#         nwsli        sev         cause
_re = (
    r"(/([A-Z0-9]{5})\.([N0123U])\.([A-Z]{2})\.([0-9TZ]+)\."
    r"([0-9TZ]+)\.([0-9TZ]+)\.([A-Z]{2})/)"
)

_statusDict = {
    "00": "is not applicable",
    "NO": "is not expected",
    "NR": "may be expected",
    "UU": "is not available",
}

_causeDict = {
    "ER": "Excessive Rainfall",
    "SM": "Snowmelt",
    "RS": "Rain and Snowmelt",
    "DM": "Dam or Levee Failure",
    "GO": "Glacier-Dammed Lake Outburst",
    "IJ": "Ice Jam",
    "IC": "Rain and/or Snowmelt and/or Ice Jam",
    "FS": "Upstream Flooding plus Storm Surge",
    "FT": "Upstream Flooding plus Tidal Effects",
    "ET": "Elevated Upstream Flow plus Tidal Effects",
    "WT": "Wind and/or Tidal Effects",
    "DR": "Upstream Dam or Reservoir Release",
    "MC": "Other Multiple Causes",
    "OT": "Other Effects",
    "UU": "Unknown",
}

_severityDict = {
    "N": "None",
    "0": "None",
    "1": "Minor",
    "2": "Moderate",
    "3": "Major",
    "U": "Unknown",
}


def parse(text, nwsli_provider=None, tp=None):
    """Return list of HVTEC entries found within text.

    Args:
      text (str): String to look for HVTEC tokens within.
      nwsli_provider (dict): Provider of metadata.
      tp (TextProduct): TextProduct instance used for provider and warnings.

    Returns:
      list(HVTEC)
    """
    hvtec = []
    tokens = re.findall(_re, text)
    if nwsli_provider is None and tp is not None:
        nwsli_provider = tp.nwsli_provider
    if nwsli_provider is None:
        nwsli_provider = {}
    for t in tokens:
        entry = HVTEC(t, nwsli_provider)
        if (
            entry.nwsli.id != "00000"
            and entry.nwsli.id not in nwsli_provider
            and tp is not None
        ):
            tp.warnings.append(f"HVTEC NWSLI {entry.nwsli.id} is unknown.")
        hvtec.append(entry)
    return hvtec


def contime(s):
    """Process a string into time."""
    if len(re.findall("0000*T", s)) > 0:
        return None
    try:
        ts = datetime.strptime(s, "%y%m%dT%H%MZ")
        return ts.replace(tzinfo=timezone.utc)
    except Exception as err:
        LOG.exception(err)
        return None


class HVTEC:
    """Hydro VTEC."""

    def __init__(self, tokens, nwsli_provider=None):
        """Constructor"""
        if nwsli_provider is None:
            nwsli_provider = {}
        self.line = tokens[0]
        self.nwsli = nwsli_provider.get(tokens[1], NWSLI(tokens[1]))
        self.severity = tokens[2]
        self.cause = tokens[3]
        self.beginTS = contime(tokens[4])
        self.crestTS = contime(tokens[5])
        self.endTS = contime(tokens[6])
        self.record = tokens[7]

    def __str__(self):
        """string representation of this HVTEC"""
        return self.line
