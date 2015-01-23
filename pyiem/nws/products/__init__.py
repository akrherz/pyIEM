import re

from pyiem.nws.product import TextProduct, TextProductException, WMO_RE, AFOSRE
import spacewx
import cli
import hwo
import lsr
import mcd
import nhc
    
def parser(text , utcnow=None, ugc_provider=None, nwsli_provider=None):
    """Omnibus parser of NWS Text Data
    
    This is intended to be a catch-all parser of text data.  As it currently
    stands, it does not correctly hand products off to the correct sub-processor
    , but some day it will!
    
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

    tmp = text[:100].replace('\r\r\n', '\n')
    m = WMO_RE.search(tmp)
    if m is not None:
        d = m.groupdict()
        if d['cccc'] == 'KWNP':
            return spacewx.parser( text, utcnow, ugc_provider, nwsli_provider )

    tokens = AFOSRE.findall(tmp)
    if len(tokens) == 0:
        raise TextProductException("Could not locate AFOS Identifier")
 
    afos = tokens[0]
    if afos[:3] == 'CLI':
        return cli.parser( text, utcnow, ugc_provider, nwsli_provider )
    elif afos[:3] == 'TCP':
        return nhc.parser( text, utcnow, ugc_provider, nwsli_provider )
    elif afos[:3] == 'HWO':
        return hwo.parser( text, utcnow, ugc_provider, nwsli_provider )
    elif afos in ['SWOMCD', 'FFGMPD']:
        return mcd.parser( text, utcnow, ugc_provider, nwsli_provider )
    elif afos[:3] == 'LSR':
        return lsr.parser( text, utcnow, ugc_provider, nwsli_provider )
    
    return TextProduct( text, utcnow, ugc_provider, nwsli_provider )