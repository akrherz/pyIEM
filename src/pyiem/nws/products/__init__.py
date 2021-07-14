"""A generalized parser frontend."""
from __future__ import absolute_import
from pyiem.nws.product import TextProduct, TextProductException, WMO_RE, AFOSRE
from . import spacewx
from . import cli
from . import hwo
from . import lsr
from . import mcd
from . import nhc
from . import spcpts
from . import sps
from . import taf
from . import ero


def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    """Omnibus parser of NWS Text Data

    This is intended to be a catch-all parser of text data.  As it currently
    stands, it does not correctly hand products off to the correct
    sub-processor, but some day it will!

    Args:
      text (str): The actual product text, this can have the <cntr>-a
        character to start the string.
      utcnow (datetime, optional): What is the current time, this is useful
        for when ingesting old data.  Many times, the product does not contain
        enough information to assign a current valid timestamp to it.  So we
        need to know the current timestamp to do the relative computation.
      ugc_provider (dict, optional): Provides NWS UGC metadata, the dictionary
        keys are UGC codes.
      nwsli_provider (dict, optional): Provides NWS Location Identifiers to
        allow lookup of geographic information for station identifiers.

    Returns:
      TextProduct: A TextProduct instance

    """

    tmp = text[:100].replace("\r\r\n", "\n")
    m = WMO_RE.search(tmp)
    if m is not None:
        d = m.groupdict()
        if d["cccc"] == "KWNP":
            return spacewx.parser(text, utcnow, ugc_provider, nwsli_provider)

    tokens = AFOSRE.findall(tmp)
    if not tokens:
        raise TextProductException("Could not locate AFOS Identifier")
    afos = tokens[0]
    if afos[:3] == "CLI":
        return cli.parser(text, utcnow, ugc_provider, nwsli_provider)
    elif afos[:3] == "TCP":
        return nhc.parser(text, utcnow, ugc_provider, nwsli_provider)
    elif afos[:3] == "HWO":
        return hwo.parser(text, utcnow, ugc_provider, nwsli_provider)
    elif afos in ["SWOMCD", "FFGMPD"]:
        return mcd.parser(text, utcnow, ugc_provider, nwsli_provider)
    elif afos[:3] == "LSR":
        return lsr.parser(text, utcnow, ugc_provider, nwsli_provider)
    elif afos[:3] in ["PTS", "PFW"]:
        return spcpts.parser(text, utcnow, ugc_provider, nwsli_provider)
    elif afos[:3] == "RBG":
        return ero.parser(text, utcnow, ugc_provider, nwsli_provider)
    elif afos[:3] == "TAF":
        return taf.parser(text, utcnow, ugc_provider, nwsli_provider)
    elif afos[:3] == "SPS":
        return sps.parser(text, utcnow, ugc_provider, nwsli_provider)

    return TextProduct(text, utcnow, ugc_provider, nwsli_provider)
