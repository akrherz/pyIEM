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
MAG_UNITS = re.compile(r"(ACRE|INCHES|INCH|MILE|MPH|KTS|U|FT|F|E|M|TRACE)")

from pyiem.nws.product import TextProduct, TextProductException
from pyiem import reference

class LSRProductException(TextProductException):
    ''' Something we can raise when bad things happen! '''
    pass

class LSR(object):
    ''' Represents a single Local Storm Report within the LSRProduct '''

    def __init__(self):
        ''' constructor '''
        self.utcvalid = None
        self.valid = None
        self.typetext = None
        self.geometry = None
        self.city = None
        self.county = None
        self.source = None
        self.remark = None
        self.magnitude_f = None
        self.magnitude_str = None
        self.magnitude_qualifier = None
        self.magnitude_units = None
        self.state = None
        self.source = None
        self.text = None
        self.wfo = None
    
    def get_lat(self):
        return self.geometry.xy[1][0]
    
    def get_lon(self):
        return self.geometry.xy[0][0]
                
    def consume_magnitude(self, text):
        ''' Convert LSR magnitude text into something atomic '''
        self.magnitude_str = text
        tokens = MAG_UNITS.findall(text)
        if len(tokens) == 2:
            self.magnitude_qualifier = tokens[0]
            self.magnitude_units = tokens[1]
        elif len(tokens) == 1:
            self.magnitude_units = tokens[0]
        val = MAG_UNITS.sub('', text).strip()
        if val != '':
            self.magnitude = float(val)

    def sql(self, txn):
        ''' Provided a database transaction object, persist this LSR '''
        table = "lsrs_%s" % (self.utcvalid.year,)
        wkt = "SRID=4326;%s" % (self.geometry.wkt,)
        sql = """INSERT into """+table +""" (valid, type, magnitude, city, 
               county, state, source, remark, geom, wfo, typetext) 
               values (%s, %s, %s, %s, %s, %s, 
               %s, %s, %s, %s, %s)"""
        args = (self.utcvalid, 
                reference.lsr_events.get(self.typetext, None),
                self.magnitude_f, self.city, self.county, self.state,
                self.source, self.remark, wkt, self.wfo, self.typetext)
        txn.execute(sql, args)

    def tweet(self):
        ''' return a tweet text '''
        return 'TODO'
        
    def jabber_html(self, uri='http://localhost'):
        ''' return a plain text string representing this LSR '''
        time_fmt = "%-I:%M %p %Z"
        now = datetime.datetime.utcnow()
        now = now.replace(tzinfo=pytz.timezone("UTC")) - datetime.timedelta(
                                                                    hours=24)
        if self.valid < now:
            time_fmt = "%d %b, %-I:%M %p %Z"

        return "%s [%s Co, %s] %s <a href=\"%s\">reports %s</a> at %s -- %s" % (
            self.city, self.county, self.state, self.source,
              uri, self.mag_string(),
              self.valid.strftime(time_fmt), self.remark)
        
    def jabber_text(self, uri='http://localhost'):
        ''' return a plain text string representing this LSR '''
        time_fmt = "%-I:%M %p %Z"
        now = datetime.datetime.utcnow()
        now = now.replace(tzinfo=pytz.timezone("UTC")) - datetime.timedelta(
                                                                    hours=24)
        if self.valid < now:
            time_fmt = "%d %b, %-I:%M %p %Z"

        return "%s [%s Co, %s] %s reports %s at %s -- %s %s" % (
            self.city, self.county, self.state, self.source,
              self.mag_string(),
              self.valid.strftime(time_fmt), self.remark, uri)


    def assign_timezone(self, tz):
        ''' retroactive assignment of timezone, so to improve attrs '''
        if self.valid is None:
            return
        self.valid = self.valid.replace(tzinfo=tz)
        self.utcvalid = self.valid.astimezone( pytz.timezone("UTC") )
        
    def mag_string(self):
        ''' Return a string representing the magnitude and units '''
        mag_long = "%s" % (self.typetext,)
        if (self.typetext == "HAIL" and 
            reference.hailsize.has_key(float(self.mag))):
            haildesc = reference.hailsize[float(self.mag)]
            mag_long = "%s of %s %s size (%.2fin)" % (mag_long, haildesc, 
                                                      self.magnitude_f,
                                                      self.magnitude_qualifier)
        elif self.magnitude_f:
            mag_long = "%s of %.2f %s" % (mag_long, self.magnitude_f, 
                                        self.magnitude_units)

        return mag_long

class LSRProduct(TextProduct):
    ''' Represents a text product of the LSR variety '''
    
    def __init__(self, text):
        ''' constructor '''
        self.lsrs = []
        TextProduct.__init__(self, text)

    def get_temporal_domain(self):
        ''' Return the min and max timestamps of lsrs '''
        valids = []
        for lsr in self.lsrs:
            valids.append( lsr.valid )
        return min(valids), max(valids)
    
    def is_summary(self):
        ''' Returns is this LSR is a summary or not '''
        return self.unixtext.find("...SUMMARY") > 0
        
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

def parser(text):
    ''' Helper function that actually converts the raw text and emits an
    LSRProduct instance or returns an exception'''
    prod = LSRProduct(text)
    
    for match in SPLITTER.finditer(prod.unixtext):
        lsr = parse_lsr("".join(match.groups()))
        lsr.wfo = prod.source[1:]
        lsr.assign_timezone( prod.z )
        prod.lsrs.append( lsr )
    
    return prod