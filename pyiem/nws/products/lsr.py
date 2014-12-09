'''
Local Storm Report
'''
# Stand Library Imports
import datetime
import re

# Third party
import pytz
from shapely.geometry import Point as ShapelyPoint

SPLITTER = re.compile(r"(^[0-9].+?\n^[0-9].+?\n)((?:.*?\n)+?)(?=^[0-9]|$)",
                      re.MULTILINE)


from pyiem.nws.product import TextProduct, TextProductException
from pyiem import reference
from pyiem.nws.lsr import LSR

class LSRProductException(TextProductException):
    ''' Something we can raise when bad things happen! '''
    pass



class LSRProduct(TextProduct):
    ''' Represents a text product of the LSR variety '''
    
    def __init__(self, text, utcnow=None):
        ''' constructor '''
        self.lsrs = []
        self.duplicates = 0
        TextProduct.__init__(self, text, utcnow=utcnow)

    def get_temporal_domain(self):
        ''' Return the min and max timestamps of lsrs '''
        valids = []
        for lsr in self.lsrs:
            valids.append( lsr.valid )
        if len(valids) == 0:
            return None, None
        return min(valids), max(valids)
    
    def is_summary(self):
        ''' Returns is this LSR is a summary or not '''
        return self.unixtext.find("...SUMMARY") > 0
        
    def get_url(self, baseuri):
        ''' Get the URL of this product '''
        min_time, max_time = self.get_temporal_domain()
        wfo = self.source[1:]
        return "%s#%s/%s/%s" % (baseuri, wfo, 
               min_time.strftime("%Y%m%d%H%M"),
               max_time.strftime("%Y%m%d%H%M") )
        
    def get_jabbers(self, uri):
        ''' return a text and html variant for Jabber stuff '''
        res = []
        wfo = self.source[1:]
        url =  self.get_url(uri)

        for mylsr in self.lsrs:
            if mylsr.duplicate:
                continue
            time_fmt = "%-I:%M %p %Z"
            url = "%s#%s/%s/%s" % (uri, mylsr.wfo, 
                                   mylsr.utcvalid.strftime("%Y%m%d%H%M"),
                                   mylsr.utcvalid.strftime("%Y%m%d%H%M") )
            if mylsr.valid.day != self.utcnow.day:
                time_fmt = "%-d %b, %-I:%M %p %Z"
            xtra = {
        'product_id': self.get_product_id(),
        'channels': "LSR%s,LSR.ALL,LSR.%s" % (mylsr.wfo, 
                                              mylsr.typetext.replace(" ", "_")),        
        'geometry': 'POINT(%s %s)' % (mylsr.get_lon(), mylsr.get_lat()),
        'ptype' : mylsr.get_dbtype(),
        'valid' : mylsr.utcvalid.strftime("%Y%m%dT%H:%M:00"),
        'category' : 'LSR',
        'twitter' : "%s %s" % (mylsr.tweet(), url),
        'lat': str(mylsr.get_lat()),
        'long': str(mylsr.get_lon()),
            }
            html = ("<p>%s [%s Co, %s] %s <a href=\"%s\">reports %s</a> at "
            +"%s -- %s</p>") % (
                        _mylowercase(mylsr.city), mylsr.county.title(), mylsr.state, mylsr.source,
                        url, mylsr.mag_string(),
                        mylsr.valid.strftime(time_fmt), mylsr.remark)
    
            plain = "%s [%s Co, %s] %s reports %s at %s -- %s %s" % (
                        _mylowercase(mylsr.city), mylsr.county.title(), 
                        mylsr.state, mylsr.source,
                        mylsr.mag_string(),
                        mylsr.valid.strftime(time_fmt), mylsr.remark, url)
            res.append( [plain, html, xtra])
        
        if self.is_summary():
            extra_text = ""
            if self.duplicates > 0:
                extra_text = (", %s out of %s reports were previously "
                            +"sent and not repeated here.") % (self.duplicates, 
                                                    len(self.lsrs))
            text = "%s: %s issues Summary Local Storm Report %s %s" % (
                                                    wfo, wfo, extra_text, url)
            
            html = ("<p>%s issues "
                          +"<a href='%s'>Summary Local Storm Report</a>%s</p>") % (
                                                wfo, url, extra_text)
            xtra = {
                'product_id': self.get_product_id(),
                'channels': 'LSR%s' % (wfo,),
                }
            res.append([text, html, xtra] )
        return res

def _mylowercase(text):
    ''' Specialized lowercase function ''' 
    tokens = text.split()
    for i,t in enumerate(tokens):
        if len(t) > 3:
            tokens[i] = t.title()
        elif t in ['N', 'NNE', 'NNW', 'NE',
                   'E', 'ENE', 'ESE', 'SE',
                   'S', 'SSE', 'SSW', 'SW',
                   'W', 'WSW', 'WNW', 'NW']:
            continue
    return " ".join(tokens)
        
def parse_lsr(text):
    ''' Emit a LSR object based on this text! 
    0914 PM     HAIL             SHAW                    33.60N 90.77W
    04/29/2005  1.00 INCH        BOLIVAR            MS   EMERGENCY MNGR
    '''
    lines = text.split("\n")
    if len(lines) < 2:
        raise LSRProductException("LSR text is too short |%s|" % (
                                                text.replace("\n", "<NL>"),))
    lsr = LSR()
    lsr.text = text
    tokens = lines[0].split()
    h12 = tokens[0][:-2]
    mm = tokens[0][-2:]
    ampm = tokens[1]
    dstr = "%s:%s %s %s" % (h12, mm, ampm, lines[1][:10])
    lsr.valid = datetime.datetime.strptime(dstr, "%I:%M %p %m/%d/%Y")
   
    lsr.typetext = lines[0][12:29].strip().upper()

    lsr.city = lines[0][29:53].strip()
    
    tokens = lines[0][53:].strip().split()
    lat = float(tokens[0][:-1])
    lon = 0 - float(tokens[1][:-1])
    lsr.geometry = ShapelyPoint((lon,lat))
    
    lsr.consume_magnitude( lines[1][12:29].strip() )
    lsr.county = lines[1][29:48].strip()
    lsr.state = lines[1][48:50]
    lsr.source = lines[1][53:].strip()
    if len(lines) > 2:
        meat = " ".join( lines[2:] ).strip()
        lsr.remark = " ".join( meat.split())
    return lsr

def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    ''' Helper function that actually converts the raw text and emits an
    LSRProduct instance or returns an exception'''
    prod = LSRProduct(text, utcnow)
    
    for match in SPLITTER.finditer(prod.unixtext):
        lsr = parse_lsr("".join(match.groups()))
        lsr.wfo = prod.source[1:]
        lsr.assign_timezone( prod.tz, prod.z )
        prod.lsrs.append( lsr )
    
    return prod