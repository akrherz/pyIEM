""" module 

Template:

from pyiem.nws.product import TextProduct

class NHCException(Exception):
    pass

class NHCProduct( TextProduct ):
    def __init__(self, text, utcnow=None, ugc_provider=None, 
                 nwsli_provider=None):
        TextProduct.__init__(self, text, utcnow, ugc_provider, nwsli_provider)
        

        
def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    return NHCProduct( text, utcnow, ugc_provider, nwsli_provider )

"""
import re


from pyiem.nws.product import TextProduct, TextProductException, WMO_RE, AFOSRE
import spacewx
import cli
import hwo
import lsr
import mcd
import nhc
    
def parser( text , utcnow=None, ugc_provider=None, nwsli_provider=None):
    """ generalized parser of a text product """

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