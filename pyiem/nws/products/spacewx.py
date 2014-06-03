# A parser for stuff that the Space Weather Center issues

from pyiem.nws.product import TextProduct

class SpaceWxProduct( TextProduct ):
    ''' Class for parsing and representing Space Wx Products '''
    
    def __init__(self, text):
        ''' constructor '''
        TextProduct.__init__(self, text)
        self.title = "Unknown (AWIPSID: %s)" % (self.afos,)
        self.parse_title()
        
    def parse_title(self):
        ''' Figure out the title of this product '''
        if len(self.sections) < 2:
            return
        self.title = self.sections[2].split("\n")[0]
        
    def get_jabbers(self, uri):
        ''' Custom Implementation of the TextProduct#get_jabbers '''
        url = "%s%s" % (uri, self.get_product_id())
        xtra = {'channels': 'WNP,%s' % (self.afos,),
                'twitter': 'SWPC issues %s %s' % (self.title, url)
                }
        plain = 'Space Weather Prediction Center issues %s %s' % (self.title,
                        url)
        html = ('<p>Space Weather Prediction Center '
                +'<a href="%s">issues %s</a></p>') % (
                                    url, self.title)
        return [(plain, html, xtra)]
        

def parser(buf):
    ''' A parser implementation '''
    return SpaceWxProduct( buf )