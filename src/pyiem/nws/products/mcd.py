import re

from pyiem.nws.product import TextProduct
from shapely.geometry import Polygon as ShapelyPolygon

LATLON = re.compile(r"LAT\.\.\.LON\s+((?:[0-9]{8}\s+)+)")
DISCUSSIONNUM = re.compile(r"MESOSCALE DISCUSSION\s+([0-9]+)")
ATTN_WFO = re.compile(r"ATTN\.\.\.WFO\.\.\.([\.A-Z]*)LAT\.\.\.LON")

class MCDException(Exception):
    ''' Exception '''
    pass

class MCDProduct( TextProduct ):
    '''
    Represents a Storm Prediction Center Mesoscale Convective Discussion
    '''
    
    def __init__(self, text):
        ''' constructor '''
        TextProduct.__init__(self, text)
        self.geometry = self.parse_geometry()
        self.discussion_num = self.parse_discussion_num()
        self.attn_wfo = self.parse_attn_wfo()
        self.areas_affected = self.parse_areas_affected()
        
    def tweet(self):
        ''' Return twitter message '''
        return "#SPC issues MCD %s: %s" % (self.discussion_num,
                                           self.areas_affected)
        
    def get_spc_url(self):
        ''' Return the URL for SPC's website '''
        return "http://www.spc.noaa.gov/products/md/%s/md%04i.html" % (
                            self.valid.year, self.discussion_num)
        
    def parse_areas_affected(self):
        ''' Return the areas affected '''
        sections = self.unixtext.split("\n\n")
        for section in sections:
            if section.strip().find("AREAS AFFECTED...") == 0:
                return section[17:]
        return None

    def get_jabbers(self, uri):
        ''' Return plain text and html variants for a Jabber msg '''
        spcuri = self.get_spc_url()
        plain = "Storm Prediction Center issues Mesoscale Discussion #%s %s" % (
                                                        self.discussion_num,
                                                        spcuri)
        html = ("Storm Prediction Center issues <a href='%s'>"
                +"Mesoscale Discussion #%s</a> "
                +"(<a href='%s'>View text</a>)") % (spcuri,
                                                           self.discussion_num,
                                                           uri
                                                           )
        return plain, html

    def parse_attn_wfo(self):
        ''' FIgure out which WFOs this product is seeking attention '''
        tokens = ATTN_WFO.findall( self.unixtext.replace("\n", ""))
        if len(tokens) == 0:
            raise MCDException('Could not parse attention WFOs')
        return re.findall("([A-Z]{3})", tokens[0])
        
    def parse_discussion_num(self):
        ''' Figure out what discussion number this is '''
        tokens = DISCUSSIONNUM.findall( self.unixtext )
        if len(tokens) == 0:
            raise MCDException('Could not parse discussion number')
        return int(tokens[0])
        
    def parse_geometry(self):
        ''' Find the polygon that's in this MCD product '''
        tokens = LATLON.findall( self.unixtext.replace("\n", " "))
        if len(tokens) == 0:
            raise MCDException('Could not parse LAT...LON geometry')
        pts = []
        for pair in tokens[0].split():
            lat = float(pair[:4]) / 100.0
            lon = 0 - float(pair[4:]) / 100.0
            if lon > -40:
                lon = lon - 100.0
            pts.append( (lon, lat) )
        return ShapelyPolygon(pts)
        
def parser(text):
    ''' Helper function '''
    return MCDProduct( text )