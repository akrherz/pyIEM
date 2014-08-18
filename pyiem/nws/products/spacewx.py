# A parser for stuff that the Space Weather Center issues

import pyiem.nws.product as product

class SpaceWxProduct( product.TextProduct ):
    ''' Class for parsing and representing Space Wx Products '''
    
    def __init__(self, text, utcnow=None):
        ''' constructor '''
        product.TextProduct.__init__(self, text, utcnow=utcnow)
        self.title = "Unknown (AWIPSID: %s)" % (self.afos,)
        self.parse_title()
        
    def parse_title(self):
        ''' Figure out the title of this product '''
        if len(self.sections) < 2:
            return
        self.title = self.sections[2].split("\n")[0]
        
    def get_jabbers(self, uri):
        ''' Custom Implementation of the TextProduct#get_jabbers '''
        url = "%s?pid=%s" % (uri, self.get_product_id())
        xtra = {'channels': 'WNP,%s' % (self.afos,),
                'twitter': 'SWPC issues %s %s' % (self.title, url)
                }
        plain = 'Space Weather Prediction Center issues %s %s' % (self.title,
                        url)
        html = ('<p>Space Weather Prediction Center '
                +'<a href="%s">issues %s</a></p>') % (
                                    url, self.title)
        return [(plain, html, xtra)]
        

def parser(buf, utcnow=None, ugc_provider=None, nwsli_provider=None):
    ''' A parser implementation '''
    return SpaceWxProduct( buf, utcnow=utcnow )