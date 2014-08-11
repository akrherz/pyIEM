""" Handle some of the fun things that come from the Hurricane Center """

import re

from pyiem.nws.product import TextProduct

class NHCException(Exception):
    """ Exception """
    pass

class NHCProduct( TextProduct ):
    """
    Represents a NHC
    """
    
    def __init__(self, text, utcnow=None, ugc_provider=None, 
                 nwsli_provider=None):
        """ constructor """
        TextProduct.__init__(self, text, utcnow, ugc_provider, nwsli_provider)

    def get_jabbers(self, uri, uri2=None):
        """ Get the jabber variant of this message """
        myurl = "%s?pid=%s" % (uri, self.get_product_id() )
        
        tokens = re.findall("(POST-TROPICAL CYCLONE|TROPICAL STORM|HURRICANE|TROPICAL DEPRESSION|REMNANTS OF) ([A-Z0-9\- ]*) (DISCUSSION|INTERMEDIATE ADVISORY|FORECAST/ADVISORY|ADVISORY) NUMBER\s+([0-9A-Z]+)", self.unixtext )
        if len(tokens) == 0:
            raise NHCException("Count not parse header from NHC Prodct!")

        classification = tokens[0][0]
        name = tokens[0][1]
        twitter_name = name.title().replace("-", "_")
        prodtype = tokens[0][2]
        prodnumber = tokens[0][3]
        center = "National Hurricance Center"

        tformat = "%(classification)s #%(storm_name)s %(btype)s %(num)s issued. %(headline)s http://go.usa.gov/W3H"
        tdict = {'classification': classification.title(),
             'storm_name': twitter_name,
             'num': prodnumber,
             'btype': prodtype,
             'headline': '',
             'url': myurl
             }

        mess = "%s issues %s #%s for %s %s %s" % (
               center, prodtype, prodnumber, classification, name, myurl)
        htmlmess = "%s issues <a href=\"%s\">%s #%s</a> for %s %s" % (
               center, myurl, prodtype, prodnumber, classification, name)

        if len(self.segments[0].headlines) > 0:
            headline = self.segments[0].headlines[0]
            headline = headline.lower().replace(name.lower(), '#%s' % (twitter_name,))
            headline = headline[0].upper() + headline[1:] +"."
            if (144 - len(tformat % tdict)) > len(headline):
                tdict['headline'] = headline
            else:
                headline = headline[:headline.find(",")]
                if (144 - len(tformat % tdict)) > len(headline):
                    tdict['headline'] = headline
    
        tweet = tformat % tdict
    
        return [[mess.replace("#","") % tdict, 
                htmlmess.replace("#","") % tdict, 
            {
                'channels':"NHC,%s,%s,%s" % (self.afos[:5],name, self.afos),
                'product_id': self.get_product_id(),
                'twitter': ' '.join( tweet.split(),)
            }],]


        
def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    """ Helper function """
    return NHCProduct( text, utcnow, ugc_provider, nwsli_provider )