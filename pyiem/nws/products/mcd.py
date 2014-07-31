'''
 Supports parsing of Storm Prediction Center's MCD and
 parsing of Weather Prediction Center's MPD
'''
import re
import cgi

from pyiem.nws.product import TextProduct
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.geometry import MultiPolygon

LATLON = re.compile(r"LAT\.\.\.LON\s+((?:[0-9]{8}\s+)+)")
DISCUSSIONNUM = re.compile(r"MESOSCALE (?:PRECIPITATION )?DISCUSSION\s+([0-9]+)")
ATTN_WFO = re.compile(r"ATTN\.\.\.WFO\.\.\.([\.A-Z]*?)(?:LAT\.\.\.LON|ATTN\.\.\.RFC)")
ATTN_RFC = re.compile(r"ATTN\.\.\.RFC\.\.\.([\.A-Z]*)")
WATCH_PROB = re.compile(r"PROBABILITY OF WATCH ISSUANCE\s?\.\.\.\s?([0-9]+) PERCENT")

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
        self.attn_rfc = self.parse_attn_rfc()
        self.areas_affected = self.parse_areas_affected()
        self.watch_prob = self.find_watch_probability()
        
    def find_watch_probability(self):
        ''' Find the probability of watch issuance for SPC MCD'''
        tokens = WATCH_PROB.findall( self.unixtext.replace("\n", ""))
        if len(tokens) == 0:
            return None
        return int(tokens[0])
        
    def tweet(self):
        ''' Return twitter message '''
        charsleft = 140 - 22 # default safe 22 for t.co shortening
        if self.afos == 'SWOMCD':
            center = 'SPC'
        else:
            center = 'WPC'
        prob_extra = ""
        if self.watch_prob is not None:
            prob_extra = " [watch prob: %.0f%%]" % (self.watch_prob,)
        attempt = "#%s issues %s %s%s: %s " % (center, self.afos[3:], 
                                         self.discussion_num, prob_extra, 
                                        self.areas_affected)
        return "%s%s" % (attempt[:charsleft], self.get_url())
        
    def get_url(self):
        ''' Return the URL for SPC's website '''
        if self.afos == 'SWOMCD':
            return "http://www.spc.noaa.gov/products/md/%s/md%04i.html" % (
                            self.valid.year, self.discussion_num)
        else:
            return ('http://www.wpc.ncep.noaa.gov/metwatch/'
                    +'metwatch_mpd_multi.php?md=%s&yr=%s') % (
                                                    self.discussion_num,
                                                    self.valid.year)
        
    def parse_areas_affected(self):
        ''' Return the areas affected '''
        sections = self.unixtext.split("\n\n")
        for section in sections:
            if section.strip().find("AREAS AFFECTED...") == 0:
                return section[17:].replace("\n", " ")
        return None

    def get_jabbers(self, uri):
        ''' Return plain text and html variants for a Jabber msg '''
        # convert htmlentities
        spcuri = cgi.escape( self.get_url() )
        center = 'Storm Prediction Center'
        pextra = ''
        if self.afos == 'FFGMPD':
            center = 'Weather Prediction Center'
            pextra = 'Precipitation '
        prob_extra = ""
        if self.watch_prob is not None:
            prob_extra = "[watch probability: %.0f%%] " % (self.watch_prob,)
        plain = "%s issues Mesoscale %sDiscussion #%s%s %s" % (center, pextra,
                                                        self.discussion_num,
                                                        prob_extra,
                                                        spcuri)
        html = ('<p>%s issues <a href="%s">'
                +'Mesoscale %sDiscussion #%s</a> %s'
                +'(<a href="%s?pid=%s">View text</a>)</p>') % (center, spcuri, pextra,
                                                           self.discussion_num,
                                                           prob_extra, uri,
                                                    self.get_product_id()
                                                           )
        return plain, html

    def parse_attn_rfc(self):
        ''' FIgure out which RFCs this product is seeking attention '''
        tokens = ATTN_RFC.findall( self.unixtext.replace("\n", ""))
        if len(tokens) == 0:
            return []
        return re.findall("([A-Z]{5})", tokens[0])

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
        
    def find_cwsus(self, txn):
        ''' 
        Provided a database transaction, go look for CWSUs that 
        overlap the discussion geometry.
        ST_Overlaps do the geometries overlap
        ST_Covers does polygon exist inside CWSU
        '''
        wkt = 'SRID=4326;%s' % (self.geometry.wkt,)
        sql = """select distinct id from cwsu WHERE 
               st_overlaps('%s', geom) or 
               st_covers(geom, '%s') ORDER by id ASC""" % (wkt, wkt)
        txn.execute(sql)
        cwsu = []
        for row in txn:
            cwsu.append( row[0] )
        return cwsu
        
    def database_save(self, txn):
        ''' Save this product to the database '''
        giswkt = "SRID=4326;%s" % (MultiPolygon([self.geometry]).wkt,)
        sql = """INSERT into text_products(product, product_id, geom) 
          values (%s, %s, %s)"""
        args = (self.text, self.get_product_id(), giswkt)
        txn.execute(sql, args)
        
def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    ''' Helper function '''
    return MCDProduct( text )