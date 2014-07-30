""" module 

Template:

from pyiem.nws.product import TextProduct

class XXXException(Exception):
    ''' Exception '''
    pass

class XXXProduct( TextProduct ):
    '''
    Represents a XXX
    '''
    
    def __init__(self, text):
        ''' constructor '''
        TextProduct.__init__(self, text)
        

        
def parser(text):
    ''' Helper function '''
    return XXXProduct( text )


"""