"""A generalized parser frontend."""

from __future__ import absolute_import

from typing import Optional, Union

from pyiem.nws.ugc import UGCProvider
from pyiem.wmo import WMOProduct


def parser(
    text,
    utcnow=None,
    ugc_provider: Optional[Union[UGCProvider, dict]] = None,
    nwsli_provider=None,
):
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
      ugc_provider (UGCProvider, optional): Provides UGC information for
        product parsing.
      nwsli_provider (dict, optional): Provides NWS Location Identifiers to
        allow lookup of geographic information for station identifiers.

    Returns:
      TextProduct: A TextProduct instance

    """
    from pyiem.nws.product import (
        TextProduct,
        TextProductException,
    )

    from . import (
        cli,
        ero,
        hwo,
        lsr,
        mcd,
        nhc,
        saw,
        sel,
        spacewx,
        spcpts,
        sps,
        taf,
        wwp,
    )

    XREF = {
        "CLI": cli.parser,
        "FFG": mcd.parser,
        "HWO": hwo.parser,
        "LSR": lsr.parser,
        "NHC": nhc.parser,
        "PFW": spcpts.parser,
        "PTS": spcpts.parser,
        "RBG": ero.parser,
        "SAW": saw.parser,
        "SEL": sel.parser,
        "SPS": sps.parser,
        "SWO": mcd.parser,
        "TAF": taf.parser,
        "TCP": nhc.parser,
        "WWP": wwp.parser,
    }
    # Kind of wasteful, but alas
    wmo = WMOProduct(text, utcnow)
    if wmo.source == "KWNP":
        return spacewx.parser(text, utcnow, ugc_provider, nwsli_provider)
    if wmo.afos is None:
        raise TextProductException("Could not locate AFOS Identifier")
    func = XREF.get(wmo.afos[:3], TextProduct)
    return func(text, utcnow, ugc_provider, nwsli_provider)
