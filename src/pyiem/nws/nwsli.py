'''
Class for NWSLI identifiers
'''
from shapely.geometry import Point

class NWSLI(object):
    
    def __init__(self, identifier, name=None, wfos=[], lon=0, lat=0):
        ''' Constructor '''
        self.id = identifier
        self.name = name
        self.wfos = wfos
        self.geometry = Point([lon, lat])

    def get_name(self):
        ''' Return the name of this site '''
        if self.name is None:
            return '((%s))' % (self.id,)
        return self.name