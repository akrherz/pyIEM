"""Pilot Reports (PIREP)

This module attempts to process and store atomic data from PIREPs.  These are
encoded products that look like so:

  UBUS01 KMSC 221700
  EAU UA /OV EAU360030/TM 1715/FL350/TP B737/TB CONT LGT-MOD CHOP =
  EHY UA /OV MBW253036 /TM 1729 /FL105 /TP C206 /SK FEW250 /TA M06
  /TB NEG /RM SMTH=

Unfortunately, there is not much documentation of this format and the feed of
this data contains a bunch of formatting errors.

"""
import pyiem.nws.product as product
import datetime
import re
import math
from pyiem.datatypes import distance

OV_LATLON = re.compile("\s?(?P<lat>[0-9]{3,4}[NS])\s?(?P<lon>[0-9]{3,5}[EW])")
OV_LOCDIR = re.compile(".*?(?P<loc>[A-Z0-9]{3,4})\s?(?P<dir>[0-9]{3})(?P<dist>[0-9]{3})")
OV_TWOLOC = re.compile("(?P<loc1>[A-Z0-9]{3,4})\s?-\s?(?P<loc2>[A-Z0-9]{3,4})")
OV_OFFSET = re.compile("(?P<dist>[0-9]{1,3})\s?(?P<dir>NORTH|EAST|SOUTH|WEST|N|NNE|NE|ENE|E|ESE|SE|SSE|S|SSW|SW|WSW|W|WNW|NW|NNW)\s+(OF )?(?P<loc>[A-Z0-9]{3,4})""")

DRCT2DIR = {'N': 0, 'NNE': 22.5, 'NE': 45, 'ENE': 67.5, 'E': 90,
            'ESE': 112.5, 'SE': 135, 'SSE': 157.5, 'S': 180,
            'SSW': 202.5, 'SW': 225, 'WSW': 247.5, 'W': 270,
            'WNW': 292.5, 'NW': 305, 'NNW': 327.5,
            'NORTH': 0, 'EAST': 90, 'SOUTH': 180, 'WEST': 270}

class PilotReport:
    """ A Pilot Report Object """

    def __init__(self):
        """ Constructor"""
        self.base_loc = None
        self.text = None
        self.priority = None
        self.latitude = None
        self.longitude = None
        self.valid = None
        self.cwsu = None
        self.aircraft_type = None
        self.is_duplicate = False

class Pirep( product.TextProduct ):
    ''' Class for parsing and representing Space Wx Products '''

    def __init__(self, text, utcnow=None, ugc_provider=None,
                 nwsli_provider=None):
        ''' constructor '''
        product.TextProduct.__init__(self, text, utcnow=utcnow,
                                     ugc_provider=ugc_provider,
                                     nwsli_provider=nwsli_provider)
        self.reports = []
        self.parse_reports()
        
    def parse_reports(self):
        """ Actually do the parsing of the product that generates the reports
        stored within the self.reports list """
        txt = self.unixtext if self.unixtext[:2] != '\001\n' else self.unixtext[2:]
            
        lines = txt.split("\n")
        # There may be an AWIPSID in line 3
        pos = 3 if len(lines[2]) < 10 else 2
        meat = "".join(lines[pos:])
        for report in meat.split("="):
            if report.strip() == "":
                continue
            res = self.process_pirep(" ".join(report.strip().split()))
            if res is not None:
                self.reports.append(res)
    
    def process_pirep(self, report):
        """ Convert this report text into an actual PIREP object """
        _pr = PilotReport()
        _pr.text = report
        
        for i, token in enumerate(report.split("/")):
            token = token.strip()
            # First token is always priority
            if i == 0:
                if len(token) > 10:
                    print("Aborting as not-PIREP? |%s|" % (report,))
                    return
                if token.find(" UUA") > 0:
                    _pr.priority = "UUA"
                else:
                    _pr.priority = "UA"
                parts = token.split()
                if len(parts) == 2:
                    _pr.base_loc = parts[0]
                    if len(_pr.base_loc) == 4 and _pr.base_loc[0] == 'K':
                        _pr.base_loc = _pr.base_loc[1:]
                continue
            # Aircraft Type
            if token.startswith("TP "):
                _pr.aircraft_type = token[3:]

            # Location
            if token.startswith("OV "):
                dist = 0
                bearing = 0
                therest = token[3:]
                if len(therest) == 3:
                    loc = therest
                elif therest.startswith("FINAL RWY"):
                    loc = report[:8].split()[0]
                    if len(loc) == 4 and loc[0] == 'K':
                        loc = loc[1:]
                elif len(therest) == 4:
                    if therest[0] == 'K':
                        loc = therest[1:]
                    else:
                        loc = therest
                elif re.match(OV_OFFSET, therest):
                    d = re.match(OV_OFFSET, therest).groupdict()
                    loc = d['loc']
                    if len(loc) == 4 and loc[0] == 'K':
                        loc = loc[1:]
                    dist = int(d['dist'])
                    bearing = DRCT2DIR[d['dir']]
                 
                elif re.match(OV_LOCDIR, therest):
                    # KFAR330008
                    d = re.match(OV_LOCDIR, therest).groupdict()
                    loc = d['loc']
                    if len(loc) == 4 and loc[0] == 'K':
                        loc = loc[1:]
                    bearing = int(d['dir'])
                    dist = int(d['dist'])
                elif re.match(OV_LATLON, therest):
                    # 2500N07000W
                    d = re.match(OV_LATLON, therest).groupdict()
                    _pr.latitude = float(d['lat'][:-1]) / 100.
                    if d['lat'][-1] == 'S':
                        _pr.latitude = 0 - _pr.latitude
                    _pr.longitude = float(d['lon'][:-1]) / 100.
                    if d['lon'][-1] == 'W':
                        _pr.longitude = 0 - _pr.longitude
                    continue
                elif therest == 'O':
                    # Use the first part of the report in this case
                    loc = report[:3]
                elif therest.find("-") > 0 and re.match(OV_TWOLOC, therest):
                    d = re.match(OV_TWOLOC, therest).groupdict()
                    numbers = re.findall("[0-9]{6}", therest)
                    if len(numbers) > 0:
                        bearing = int(numbers[0][:3])
                        dist = int(numbers[0][3:])
                        loc = d['loc2']
                        if len(loc) == 4 and loc[0] == 'K':
                            loc = loc[1:]
                    else:
                        # Split the distance between the two points
                        lats = []
                        lons = []
                        for loc in [d['loc1'], d['loc2']]:
                            if len(loc) == 4 and loc[0] == 'K':
                                loc = loc[1:]
                            if not self.nwsli_provider.has_key(loc):
                                self.warnings.append("Unknown location: %s '%s'" % (loc,
                                                                report))
                                return None
                            lats.append(self.nwsli_provider[loc]['lat'])
                            lons.append(self.nwsli_provider[loc]['lon'])
                        _pr.latitude = sum(lats) / 2.0
                        _pr.longitude = sum(lons) / 2.0
                        continue                                
                else:
                    loc = therest[:3]

                if not self.nwsli_provider.has_key(loc):
                    if _pr.base_loc is None:
                        self.warnings.append("Unknown location: %s '%s'" % (loc,
                                                                report))
                        return None
                    loc = _pr.base_loc
                    if not self.nwsli_provider.has_key(loc):
                        self.warnings.append("Double-unknown location: %s" %(
                                                                    report,))
                        return None
                    dist = 0
                    bearing = 0
                _pr.longitude, _pr.latitude = self.compute_loc(loc, dist,
                                                               bearing)
                continue

            # Time            
            if token.startswith("TM "):
                numbers = re.findall("[0-9]{4}", token)
                if len(numbers) != 1:
                    self.warnings.append("TM parse failed %s" % (report,))
                    return None
                hour = int(numbers[0][:2])
                minute = int(numbers[0][2:])
                _pr.valid = self.compute_pirep_valid(hour, minute)
                continue
        
        return _pr
    
    def compute_loc(self, loc, dist, bearing):
        """ Figure out the lon/lat for this location """
        lat = self.nwsli_provider[loc]['lat']
        lon = self.nwsli_provider[loc]['lon']
        # shortcut
        if dist == 0:
            return lon, lat
        meters = distance(float(dist), "MI").value("M")
        northing = meters * math.cos(math.radians(bearing)) / 111111.0
        easting = (meters * math.sin(math.radians(bearing)) / 
                   math.cos(math.radians(lat)) / 111111.0)
        #print 'meters: %.1f easting: %.3f northing: %.3f' % (meters, easting,
        #                                               northing)
        return lon + easting, lat + northing
    
    
    def compute_pirep_valid(self, hour, minute):
        """ Based on what utcnow is set to, compute when this is valid """
        res = self.utcnow.replace(hour=hour, minute=minute, second=0,
                                  microsecond=0)
        if hour > self.utcnow.hour:
            res -= datetime.timedelta(hours=24)
        return res

    def sql(self, txn):
        """ Save the reports to the database via the transaction """
        for report in self.reports:
            if report.is_duplicate:
                continue
            txn.execute("""INSERT into pireps(valid, geom, is_urgent,
            aircraft_type, report) VALUES (%s,
            ST_GeographyFromText('SRID=4326;POINT(%s %s)'),%s,%s,%s)""", (
            report.valid, report.longitude, report.latitude, 
            report.priority == 'UUA',
            report.aircraft_type, report.text))

    def assign_cwsu(self, txn):
        """ Use this transaction object to assign CWSUs for the pireps """
        for report in self.reports:
            sql = """select distinct id from cwsu WHERE  
               st_contains(geom, geomFromEWKT('SRID=4326;POINT(%s %s)'))""" %(
                report.longitude, report.latitude)
            txn.execute(sql)
            if txn.rowcount == 0:
                #self.warnings.append("Find CWSU failed %.3f %.3f %s" % (
                #    report.longitude, report.latitude, report.text))
                continue
            row = txn.fetchone()
            report.cwsu = row['id']
        
    def get_jabbers(self, uri=None, uri2=None):
        """ get jabber messages """
        res = []
        for report in self.reports:
            if report.is_duplicate:
                continue
            jmsg = {'priority': 
                    'Urgent' if report.priority == 'UUA' else 'Routine',
                    'ts': report.valid.strftime("%H%M"),
                    'report': report.text,
                    'color':
                    '#ff0000' if report.priority == 'UUA' else '#00ff00',
             }
            plain = "%(priority)s pilot report at %(ts)sZ: %(report)s" % jmsg
            html = ("<span style='color:%(color)s;'>%(priority)s pilot "
                    +"report</span> at %(ts)sZ: %(report)s") % jmsg
            xtra = {'channels':
                    '%s.%s,%s.PIREP' % (report.priority, report.cwsu,
                                        report.priority),
                    'geometry': 'POINT(%s %s)' % (report.longitude,
                                                  report.latitude),
                    'ptype': report.priority,
                    'category': 'PIREP',
                    'twitter': plain[:140],
                    'valid': report.valid.strftime("%Y%m%dT%H:%M:00")}
            res.append([plain, html, xtra])
        return res

def parser(buf, utcnow=None, ugc_provider=None, nwsli_provider=None):
    ''' A parser implementation '''
    return Pirep(buf, utcnow=utcnow, ugc_provider=ugc_provider,
                nwsli_provider=nwsli_provider)