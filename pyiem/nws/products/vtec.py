'''
VTEC enabled TextProduct
'''
# Stand Library Imports
import datetime

# Third party
import pytz
from shapely.geometry import MultiPolygon

from pyiem.nws.product import TextProduct, TextProductException
from pyiem.nws.ugc import ugcs_to_text

def do_sql_hvtec(txn, segment):
    ''' Process the HVTEC in this product '''
    nwsli = segment.hvtec[0].nwsli.id
    if len(segment.bullets) < 4:
        return
    stage_text = ""
    flood_text = ""
    forecast_text = ""
    for qqq in range(len(segment.bullets)):
        if segment.bullets[qqq].strip().find("FLOOD STAGE") == 0:
            flood_text = segment.bullets[qqq]
        if segment.bullets[qqq].strip().find("FORECAST") == 0:
            forecast_text = segment.bullets[qqq]
        if (segment.bullets[qqq].strip().find("AT ") == 0 and 
            stage_text == ""):
            stage_text = segment.bullets[qqq]


    txn.execute("""INSERT into riverpro(nwsli, stage_text, 
      flood_text, forecast_text, severity) VALUES 
      (%s,%s,%s,%s,%s) """, (nwsli, stage_text, flood_text, 
                             forecast_text, 
                             segment.hvtec[0].severity) )

class VTECProductException(TextProductException):
    ''' Something we can raise when bad things happen! '''
    pass


class VTECProduct(TextProduct):
    ''' Represents a text product of the LSR variety '''
    
    def __init__(self, text, utcnow=None, ugc_provider=None, 
                 nwsli_provider=None):
        ''' constructor '''
        # Make sure we are CRLF above all else
        if text.find("\r\r\n") == -1:
            text = text.replace("\n", "\r\r\n")
        #  Get rid of extraneous whitespace on right hand side only
        text = "\r\r\n".join([a.rstrip() for a in text.split("\r\r\n")])
        
        TextProduct.__init__(self, text, utcnow, ugc_provider, nwsli_provider)
        self.nwsli_provider = nwsli_provider
        self.skip_con = self.get_skip_con()




    def sql(self, txn):
        ''' 
        Do necessary database work for this VTEC Product, so what all do we 
        have to support:
       'NEW' -> insert
       'EXA' -> insert
       'EXB' -> insert and update

       'CON' -> update 
       'EXT' -> update
       'UPG' -> update
       'CAN' -> update
       'EXP' -> update
       'ROU' -> update
       'COR' -> update
        
        '''
        for segment in self.segments:
            if len(segment.ugcs) == 0:
                continue
            if len(segment.vtec) == 0:
                continue
            for vtec in segment.vtec:
                if vtec.status == 'T' or vtec.action == 'ROU':
                    return
                if segment.sbw:
                    self.do_sbw_geometry(txn, segment, vtec)    
                # Check for Hydro-VTEC stuff
                if (len(segment.hvtec) > 0 and 
                    segment.hvtec[0].nwsli != "00000"):
                    do_sql_hvtec(txn, segment)

                self.do_sql_vtec(txn, segment, vtec)

    def do_sql_vtec(self, txn, segment, vtec):
        """ Persist the non-SBW stuff to the database 
        
        Arguments:
        txn -- A pyscopg2 transaction
        segment -- A TextProductSegment instance
        vtec -- A vtec instance
        """
        warning_table = "warnings_%s" % (self.valid.year,)
        ugcstring = str(tuple([str(u) for u in segment.ugcs]))
        if len(segment.ugcs) == 1:
            ugcstring = "('%s')" % (segment.ugcs[0],)
        fcster = self.get_signature()
        if fcster is not None:
            fcster = fcster[:24]
        
        if vtec.action in ['NEW', 'EXB', 'EXA']:
            # New Event Types!
            bts = vtec.begints
            if vtec.action in ["EXB", "EXA"]:
                bts = self.valid
            # If this product has no expiration time, just set it ahead
            # 24 hours in time...
            ets = vtec.endts
            if vtec.endts is None:
                ets = bts + datetime.timedelta(hours=24)

            # For each UGC code in this segment, we create a database entry
            for ugc in segment.ugcs:
                # Check to see if we have entries already for this UGC
                txn.execute("""
                SELECT issue, expire, updated from """+ warning_table +"""
                WHERE ugc = %s and eventid = %s and significance = %s and
                wfo = %s and phenomena = %s and status not in ('EXP', 'CAN')
                """, (str(ugc), vtec.ETN, vtec.significance, vtec.office,
                      vtec.phenomena))
                if txn.rowcount > 0:
                    self.warnings.append(("Duplicate(s) WWA found, "
                        +"rowcount: %s for UGC: %s") % (txn.rowcount, ugc))
                txn.execute("""
                INSERT into """+ warning_table +""" (issue, expire, updated, 
                wfo, eventid, status, fcster, report, ugc, phenomena, 
                significance, gid, init_expire, product_issue, hvtec_nwsli) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                get_gid(%s, %s), %s, %s, %s)
                RETURNING issue
                """, (bts, ets, self.valid, vtec.office, 
                      vtec.ETN, vtec.action, fcster, self.unixtext, str(ugc), 
                      vtec.phenomena, vtec.significance, str(ugc), 
                      self.valid, vtec.endts, self.valid, 
                      segment.get_hvtec_nwsli()))
                if txn.rowcount != 1:
                    self.warnings.append(('Failed to add entry for UGC: %s, '
                                          +'rowcount was: %s') % ( str(ugc),
                                                               txn.rowcount ))

        elif vtec.action in ['COR',]:
            # A previous issued product is being corrected
            txn.execute("""
            UPDATE """+ warning_table +""" SET expire = %s, status = %s,
            svs = (CASE WHEN (svs IS NULL) THEN '__' ELSE svs END) 
                   || %s || '__', issue = %s, init_expire = %s WHERE
            wfo = %s and eventid = %s and ugc in """+ugcstring+""" 
            and significance = %s and phenomena = %s  
            """, (vtec.endts, vtec.action, self.unixtext, vtec.begints,
                  vtec.endts, vtec.office, vtec.ETN, 
                  vtec.significance, vtec.phenomena))
            if txn.rowcount != len(segment.ugcs):
                self.warnings.append(('Warning: do_sql_vtec updated %s row, '
                                      +'should %s rows') %(
                                        txn.rowcount, len(segment.ugcs)))

        elif vtec.action in ['CAN', 'UPG', 'EXT']:
            # These are terminate actions, so we act accordingly
            txn.execute("""
            UPDATE """+ warning_table +""" SET expire = %s, status = %s,
            svs = (CASE WHEN (svs IS NULL) THEN '__' ELSE svs END) 
                   || %s || '__' WHERE
            wfo = %s and eventid = %s and ugc in """+ugcstring+"""
            and significance = %s and phenomena = %s 
            and status not in ('EXP', 'CAN')
            """, (vtec.endts, vtec.action, self.unixtext,
                  vtec.office, vtec.ETN, 
                  vtec.significance, vtec.phenomena))
            if txn.rowcount != len(segment.ugcs):
                self.warnings.append(('Warning: do_sql_vtec updated %s row, '
                                      +'should %s rows') %(
                                        txn.rowcount, len(segment.ugcs)))

        elif vtec.action in ['CON', 'EXP', 'ROU']:
            # These are no-ops, just updates
            ets = vtec.endts
            if vtec.endts is None:
                ets = self.valid + datetime.timedelta(hours=24)

            txn.execute("""
            UPDATE """+ warning_table +""" SET status = %s,
            svs = (CASE WHEN (svs IS NULL) THEN '__' ELSE svs END) 
                   || %s || '__' , expire = %s WHERE
            wfo = %s and eventid = %s and ugc in """+ugcstring+""" 
            and significance = %s and phenomena = %s 
            and status not in ('EXP', 'CAN')
            """, (vtec.action, self.unixtext, ets, vtec.office, vtec.ETN,
                  vtec.significance, vtec.phenomena ))
            if txn.rowcount != len(segment.ugcs):
                self.warnings.append(('Warning: do_sql_vtec updated %s row, '
                                      +'should %s rows') %(
                                        txn.rowcount, len(segment.ugcs)))

        else:
            self.warnings.append( ('Warning: do_sql_vtec() encountered %s '
                                   +'VTEC status') % (
                                                    vtec.action,))
        
    def do_sbw_geometry(self, txn, segment, vtec):
        ''' Storm Based Warnings are stored in seperate tables as we need
        to track geometry changes, etc '''
        sbw_table = "sbw_%s" % (self.valid.year,)
        
        # Some SBWs can be extended in space/time, so we need to cover these
        if vtec.action in ['EXT', 'EXA', 'EXB']:
            ets = self.valid
            if vtec.begints is not None:
                ets = vtec.begints
            txn.execute("""UPDATE """+sbw_table+""" SET 
                polygon_end = %s
                WHERE eventid = %s and wfo = %s and phenomena = %s and
                significance = %s and polygon_end = expire and status != 'CAN'
                """, (ets, vtec.ETN, vtec.office, vtec.phenomena, 
                      vtec.significance))
            if txn.rowcount != 1:
                self.warnings.append(("%s.%s.%s EXT/EXA/EXB sbw table update "
                    +"resulted in update of %s rows, should be 1") % (
                    vtec.phenomena, vtec.significance, vtec.ETN,
                                                    txn.rowcount))
        
        # If this is a cancel or upgrade action and there is only one 
        # segment, then we should update the current active polygon
        if vtec.action in ["CAN", "UPG"] and len(self.segments) == 1:
            txn.execute("""UPDATE """+ sbw_table +""" SET 
                polygon_end = (CASE WHEN polygon_end = expire
                               THEN %s ELSE polygon_end END), 
                expire = %s WHERE 
                eventid = %s and wfo = %s 
                and phenomena = %s and significance = %s""", (
                self.valid, self.valid, 
                vtec.ETN, vtec.office, vtec.phenomena, vtec.significance) )
            if txn.rowcount != 1:
                self.warnings.append(("%s.%s.%s CAN/UPG sbw table update "
                    +"resulted in update of %s rows, should be 1") % (
                    vtec.phenomena, vtec.significance, vtec.ETN,
                                                    txn.rowcount))
        
        # If this is a continues action, we should cut off the previous 
        # active polygon by setting its polygon_end
        if vtec.action == "CON":
            txn.execute("""UPDATE """+ sbw_table +""" SET 
                polygon_end = %s WHERE polygon_end = expire and 
                eventid = %s and wfo = %s and status != 'CAN'
                and phenomena = %s and significance = %s""" , ( self.valid, 
                vtec.ETN, vtec.office, vtec.phenomena, vtec.significance))
            if txn.rowcount != 1:
                self.warnings.append(("%s.%s.%s CON sbw table update "
                    +"resulted in update of %s rows, should be 1") % (
                    vtec.phenomena, vtec.significance, vtec.ETN, 
                    txn.rowcount))
        
        # When the start time is undefined, we need to go looking for it
        # from the previously processed data
        my_sts = "'%s'" % (vtec.begints,)
        if vtec.begints is None:
            my_sts = """(SELECT issue from %s WHERE 
                eventid = %s and wfo = '%s' and phenomena = '%s' 
                and significance = '%s' ORDER by updated DESC LIMIT 1)""" % (
                sbw_table, 
                vtec.ETN, vtec.office, vtec.phenomena, vtec.significance)
 
        # Prepare the TIME...MOT...LOC information
        tml_valid = None
        tml_column = 'tml_geom'
        if segment.tml_giswkt and segment.tml_giswkt.find("LINE") > 0:
            tml_column = 'tml_geom_line'
        if segment.tml_valid:
            tml_valid = segment.tml_valid
        
        
        if vtec.action in ['CAN',]:
            # issue :: we find from previous entries
            # expire :: we set to the product time
            # init_expire :: we set to the product time
            # polygon_begin :: product time
            # polygon_end :: product time
            sql = """INSERT into """+ sbw_table +"""(wfo, eventid, 
                significance, phenomena, issue, expire, init_expire, 
                polygon_begin, polygon_end, geom, status, report, windtag, 
                hailtag, tornadotag, tornadodamagetag, tml_valid, 
                tml_direction, tml_sknt, """+ tml_column +""", updated) 
                VALUES (%s,
                %s,%s,%s,"""+ my_sts +""",%s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s, %s, %s, %s, %s, %s)"""
            myargs = (vtec.office, vtec.ETN, 
                 vtec.significance, vtec.phenomena, 
                 self.valid, self.valid, self.valid, self.valid, 
                  segment.giswkt, vtec.action, self.unixtext,
                 segment.windtag, segment.hailtag, 
                 segment.tornadotag, segment.tornadodamagetag,
                 tml_valid, segment.tml_dir, segment.tml_sknt, 
                 segment.tml_giswkt, self.valid)

        elif vtec.action in ['EXP', 'UPG', 'EXT']:
            # issue :: get from previous entries
            # expire :: get from VTEC or in indefinite, set one day
            # init_expire :: ditto
            sql = """INSERT into """+ sbw_table +"""(
                wfo, eventid, significance, phenomena, 
                issue, expire, init_expire, polygon_begin, polygon_end, 
                geom, 
                status, report, windtag, hailtag, tornadotag, tornadodamagetag, 
                tml_valid, tml_direction, tml_sknt,
                """+ tml_column +""", updated) VALUES (
                %s, %s,%s,%s, 
                """+ my_sts +""",%s, %s, %s,%s,
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, %s)"""
            _expire = self.valid + datetime.timedelta(hours=24)
            if vtec.endts is not None:
                _expire = vtec.endts
            _begin = self.valid
            if vtec.begints is not None:
                _begin = vtec.begints
            myargs = (vtec.office, vtec.ETN, vtec.significance, vtec.phenomena, 
                _expire, _expire, _begin, _expire, 
                segment.giswkt, 
                vtec.action, self.unixtext, 
                segment.windtag, segment.hailtag,
                segment.tornadotag, segment.tornadodamagetag,
                tml_valid, segment.tml_dir, 
                segment.tml_sknt, segment.tml_giswkt, self.valid)
        else:
            vvv = self.valid
            if vtec.begints is not None:
                vvv = vtec.begints
            _expire = vtec.endts
            if vtec.endts is None:
                _expire = vvv + datetime.timedelta(hours=24)
            sql = """INSERT into """+ sbw_table +"""(wfo, eventid, 
                significance, phenomena, issue, expire, init_expire, 
                polygon_begin, polygon_end, geom, 
                status, report, windtag, hailtag, tornadotag, tornadodamagetag, 
                tml_valid, tml_direction, tml_sknt,
                """+ tml_column +""", updated) VALUES (%s,
                %s,%s,%s, """+ my_sts +""",%s,%s,%s,%s, %s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s, %s)""" 
            wkt = "SRID=4326;%s" % (MultiPolygon([segment.sbw]).wkt,)
            myargs = (vtec.office, vtec.ETN, 
                 vtec.significance, vtec.phenomena, _expire, 
                 _expire, vvv, 
                 _expire, wkt, vtec.action, self.unixtext,
                 segment.windtag, segment.hailtag, 
                 segment.tornadotag, segment.tornadodamagetag,
                 tml_valid, segment.tml_dir, 
                 segment.tml_sknt, segment.tml_giswkt, self.valid)
        txn.execute(sql, myargs)
        if txn.rowcount != 1:
            self.warnings.append(("%s.%s.%s sbw table insert "
                    +"resulted in %s rows, should be 1") % (
                    vtec.phenomena, vtec.significance, vtec.ETN,
                                                    txn.rowcount))            

    def is_homogeneous(self):
        ''' Test to see if this product contains just one VTEC event '''
        keys = []
        for segment in self.segments:
            for vtec in segment.vtec:
                key = "%s.%s.%s" % (vtec.phenomena, vtec.ETN, 
                                    vtec.significance)
                if key not in keys:
                    keys.append(key)
        
        return len(keys) == 1

    def get_jabbers(self, uri, river_uri=None):
        """Return a list of triples representing how this goes to social
        Arguments:
        uri -- The URL for the VTEC Browser
        river_uri -- The URL of the River App
        
        Returns:
        [[plain, html, xtra]] -- A list of triples of plain text, html, xtra
        """
        wfo = self.source[1:]
        if self.skip_con:
            xtra = {'product_id': self.get_product_id(),
                    'twitter' : '%s issues updated FLS product %s?wfo=%s' % (
                                wfo, river_uri, wfo)}
            text = ("%s has sent an updated FLS product (continued products "
                    +"were not reported here).  Consult this website for more "
                    +"details. %s?wfo=%s") % (wfo, river_uri, wfo)
            html = ("<p>%s has sent an updated FLS product (continued products "
                    +"were not reported here).  Consult "
                    +"<a href=\"%s?wfo=%s\">this website</a> for more "
                    +"details.</p>") % (wfo, river_uri, wfo)
            return [(text, html, xtra)]
        msgs = []
        
        actions = []
        long_actions = []
        html_long_actions = []
        
        for segment in self.segments:
            for vtec in segment.vtec:
                # CRITICAL: redefine this for each loop as it gets passed by
                # reference below and is subsequently overwritten otherwise!
                xtra = {'product_id': self.get_product_id(),
                        'channels': ",".join( segment.get_affected_wfos() ),
                        'status' : vtec.status,
                        'vtec' : vtec.getID(self.valid.year),
                        'ptype': vtec.phenomena,
                        'twitter': ''}
                
                long_actions.append("%s %s" % (vtec.get_action_string(),
                                              ugcs_to_text(segment.ugcs) ))
                html_long_actions.append(("<span style='font-weight: bold;'>"
                        +"%s</span> %s") % (vtec.get_action_string(),
                                              ugcs_to_text(segment.ugcs) ))
                actions.append("%s %s area%s" % (vtec.get_action_string(),
                                                len(segment.ugcs),
                                        "s" if len(segment.ugcs) > 1 else ""))

                if segment.giswkt is not None:
                    xtra['category'] = 'SBW'
                    xtra['geometry'] = segment.giswkt.replace("SRID=4326;", "")
                if vtec.endts is not None:
                    xtra['expire'] = vtec.endts.strftime("%Y%m%dT%H:%M:00")
                # Set up Jabber Dict for stuff to fill in
                jmsg_dict = {'wfo': vtec.office, 
                             'product': vtec.product_string(),
                             'county': ugcs_to_text(segment.ugcs), 
                             'sts': ' ', 'ets': ' ', 
                             'svr_special': segment.special_tags_to_text(),
                             'svs_special': '',
                             'year': self.valid.year, 
                             'phenomena': vtec.phenomena,
                             'eventid': vtec.ETN, 
                             'significance': vtec.significance,
                             'url': "%s#%s" % (uri, 
                               vtec.url(self.valid.year)) }
                if (len(segment.hvtec) > 0 and 
                    segment.hvtec[0].nwsli.id != '00000'):
                    jmsg_dict['county'] = segment.hvtec[0].nwsli.get_name()
                if (vtec.begints is not None and
                    vtec.begints > (self.utcnow + datetime.timedelta(
                                    hours=1))): 
                    jmsg_dict['sts'] = ' %s ' % (vtec.get_begin_string(self),)
                jmsg_dict['ets'] = vtec.get_end_string(self)

                # Include the special bulletin for Tornado Warnings
                if vtec.phenomena in ['TO',] and vtec.significance == 'W':
                    jmsg_dict['svs_special'] = segment.svs_search()

                plain = ("%(wfo)s %(product)s %(svr_special)s%(sts)s for "
                        +"%(county)s %(ets)s %(svs_special)s "
                        +"%(url)s") % jmsg_dict
                html = ("<p>%(wfo)s <a href='%(url)s'>%(product)s</a> "
                        +"%(svr_special)s%(sts)s for %(county)s "
                        +"%(ets)s %(svs_special)s</p>") % jmsg_dict
                xtra['twitter'] = ("%(wfo)s %(product)s%(sts)sfor %(county)s "
                                 +"%(ets)s %(url)s") % jmsg_dict
                # brute force removal of duplicate spaces
                xtra['twitter'] = ' '.join( xtra['twitter'].split())
                msgs.append([" ".join(plain.split()),
                             " ".join(html.split()), xtra])
 
        # If we have a homogeneous product and we have more than one 
        # message, lets try to condense it down, some of the xtra settings
        # from above will be used here, this is probably bad design
        if self.is_homogeneous() and len(msgs) > 1:
            vtec = self.segments[0].vtec[0]
            xtra['channels'] = ",".join( self.get_affected_wfos() )
            jdict = {
                'as' : ", ".join(actions),
                'asl' : ", ".join(long_actions),
                'hasl' : ", ".join(html_long_actions),
                'wfo': vtec.office, 
                'product': vtec.get_ps_string(),
                'url': "%s#%s" % (uri, vtec.url(self.valid.year)),
            }
            plain = ("%(wfo)s updates %(product)s (%(asl)s) %(url)s") % jdict
            xtra['twitter'] = ("%(wfo)s updates %(product)s (%(asl)s)") % jdict
            if len(xtra['twitter']) > (140-25):
                xtra['twitter'] = ("%(wfo)s updates %(product)s "
                                   +"(%(as)s)") % jdict
                if len(xtra['twitter']) > (140-25):
                    xtra['twitter'] = ("%(wfo)s updates %(product)s") % jdict
            xtra['twitter'] += " %(url)s" % jdict
            html = ("%(wfo)s <a href=\"%(url)s\">updates %(product)s</a> "
                    +"(%(hasl)s)") % jdict
            return [(plain, html, xtra)]

        
        return msgs

    def get_skip_con(self):
        ''' Should this product be skipped from generating jabber messages'''
        if self.afos[:3] == 'FLS' and len(self.segments) > 4:
            return True
        return False

def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    ''' Helper function that actually converts the raw text and emits an
    VTECProduct instance or returns an exception'''
    prod = VTECProduct(text, utcnow=utcnow, ugc_provider=ugc_provider,
                       nwsli_provider=nwsli_provider)
    
    
    return prod