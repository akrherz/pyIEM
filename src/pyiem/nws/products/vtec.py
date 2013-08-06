'''
VTEC enabled TextProduct
'''
# Stand Library Imports
import datetime
import re

# Third party
import pytz
from shapely.geometry import MultiPolygon

from pyiem.nws.product import TextProduct, TextProductException
from pyiem.nws.ugc import ugcs_to_text
from pyiem import reference

class VTECProductException(TextProductException):
    ''' Something we can raise when bad things happen! '''
    pass


class VTECProduct(TextProduct):
    ''' Represents a text product of the LSR variety '''
    
    def __init__(self, text, utcnow=None, ugc_provider={}, nwsli_provider={}):
        ''' constructor '''
        TextProduct.__init__(self, text, utcnow, ugc_provider)
        self.nwsli_provider = nwsli_provider
        self.skip_con = self.get_skip_con()

    def do_sql_hvtec(self, txn, segment, vtec):
        ''' Process the HVTEC in this product '''
        nwsli = segment.hvtec[0].nwsli.id
        if len(segment.bullets) > 3:
            stage_text = ""
            flood_text = ""
            forecast_text = ""
            for qqq in range(len(segment.bullets)):
                if segment.bullets[qqq].strip().find("FLOOD STAGE") == 0:
                    flood_text = segment.bullets[qqq]
                if segment.bullets[qqq].strip().find("FORECAST") == 0:
                    forecast_text = segment.bullets[qqq]
                if segment.bullets[qqq].strip().find("AT ") == 0 and stage_text == "":
                    stage_text = segment.bullets[qqq]


            txn.execute("""INSERT into riverpro(nwsli, stage_text, 
              flood_text, forecast_text, severity) VALUES 
              (%s,%s,%s,%s,%s) """, (nwsli, stage_text, flood_text, 
                                     forecast_text, 
                                     segment.hvtec[0].severity) )


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
                if vtec.status == 'T':
                    return
                if segment.sbw:
                    self.do_sbw_geometry(txn, segment, vtec)    
                # Check for Hydro-VTEC stuff
                if (len(segment.hvtec) > 0 and 
                    segment.hvtec[0].nwsli != "00000"):
                    self.do_sql_hvtec(txn, segment, vtec)

                self.do_sql_vtec(txn, segment, vtec)

    def do_sql_vtec(self, txn, segment, vtec):
        ''' Exec the needed VTEC SQL statements '''
        warning_table = "warnings_%s" % (self.valid.year,)
        ugcstring = str(tuple([str(u) for u in segment.ugcs]))
        if len(segment.ugcs) == 1:
            ugcstring = "('%s')" % (segment.ugcs[0],)
        fcster = self.get_signature()
        if fcster is not None:
            fcster = fcster[:24]
        if vtec.action in ['NEW', 'EXB', 'EXA']:
            bts = vtec.begints
            if vtec.action in ["EXB", "EXA"]:
                bts = self.valid

            if segment.sbw:
                giswkt = 'SRID=4326;%s' % (MultiPolygon([segment.sbw]).wkt,)
                txn.execute("""
                INSERT into """+ warning_table +""" (issue, expire, updated, 
                gtype, wfo, eventid, status, fcster, report, phenomena, 
                significance, geom) VALUES (%s, %s, %s, 'P', %s, %s, %s, %s, 
                %s, %s, %s, %s)
                RETURNING issue
                """, (bts, vtec.endts, self.valid, vtec.office, 
                      vtec.ETN, vtec.action, fcster, self.unixtext, 
                      vtec.phenomena, vtec.significance, giswkt))
            for ugc in segment.ugcs:
                txn.execute("""
                INSERT into """+ warning_table +""" (issue, expire, updated, 
                gtype, wfo, eventid, status, fcster, report, ugc, phenomena, 
                significance, geom) VALUES (%s, %s, %s, 'C', %s, %s, %s, %s, 
                %s, %s, %s, %s, (SELECT geom from nws_ugc where ugc = %s))
                RETURNING issue
                """, (bts, vtec.endts, self.valid, vtec.office, 
                      vtec.ETN, vtec.action, fcster, self.unixtext, str(ugc), 
                      vtec.phenomena, vtec.significance, str(ugc)))
                if txn.rowcount != 1:
                    print 'Warning: do_sql_vtec inserted %s row, should be 1' % (
                                        txn.rowcount, )
        elif vtec.action in ['COR',]:
            txn.execute("""
            UPDATE """+ warning_table +""" SET expire = %s, status = %s,
            svs = svs || %s, issue = %s WHERE
            wfo = %s and eventid = %s and ugc in """+ugcstring+""" and significance = %s
            and phenomena = %s and gtype = 'C' 
            """, (vtec.endts, vtec.action, self.unixtext, vtec.begints,
                  vtec.office, vtec.ETN, 
                  vtec.significance, vtec.phenomena))
            if txn.rowcount != len(segment.ugcs):
                print 'Warning: do_sql_vtec updated %s row, should %s rows' %(
                                        txn.rowcount, len(segment.ugcs))

        elif vtec.action in ['CAN','UPG', 'EXT']:
            txn.execute("""
            UPDATE """+ warning_table +""" SET expire = %s, status = %s,
            svs = svs || %s WHERE
            wfo = %s and eventid = %s and ugc in """+ugcstring+"""
            and significance = %s
            and phenomena = %s and gtype = 'C' 
            """, (vtec.endts, vtec.action, self.unixtext,
                  vtec.office, vtec.ETN, 
                  vtec.significance, vtec.phenomena))
            if txn.rowcount != len(segment.ugcs):
                print 'Warning: do_sql_vtec updated %s row, should %s rows' %(
                                        txn.rowcount, len(segment.ugcs))

        elif vtec.action in ['CON','EXP', 'ROU']:
            txn.execute("""
            UPDATE """+ warning_table +""" SET status = %s,
            svs = svs || %s WHERE
            wfo = %s and eventid = %s and ugc in """+ugcstring+""" 
            and significance = %s
            and phenomena = %s and gtype = 'C'
            """, (vtec.action, self.unixtext, vtec.office, vtec.ETN,
                  vtec.significance, vtec.phenomena ))
            if txn.rowcount != len(segment.ugcs):
                print 'Warning: do_sql_vtec updated %s row, should %s rows' %(
                                        txn.rowcount, len(segment.ugcs))

        
    def do_sbw_geometry(self, txn, segment, vtec):
        ''' Do SBW stuff '''
        sbw_table = "sbw_%s" % (self.valid.year,)
        if vtec.action in ["CAN", "UPG"] and len(self.segments) == 1:
            txn.execute("""UPDATE """+ sbw_table +""" SET 
                polygon_end = (CASE WHEN polygon_end = expire
                               THEN %s ELSE polygon_end END), 
                expire = %s WHERE 
                eventid = %s and wfo = %s 
                and phenomena = %s and significance = %s""", (
                self.valid, self.valid, 
                vtec.ETN, vtec.office, vtec.phenomena, vtec.significance) )
            if txn.rowcount < 1:
                #TODO
                pass
        
        if vtec.action == "CON":
            txn.execute("""UPDATE """+ sbw_table +""" SET 
                polygon_end = %s WHERE polygon_end = expire and 
                eventid = %s and wfo = %s 
                and phenomena = %s and significance = %s""" , ( self.valid, 
                vtec.ETN, vtec.office, vtec.phenomena, vtec.significance))
          
        my_sts = "'%s'" % (vtec.begints,)
        if vtec.begints is None:
            my_sts = """(SELECT issue from %s WHERE eventid = %s 
              and wfo = '%s' and phenomena = '%s' and significance = '%s' 
              LIMIT 1)""" % (sbw_table, vtec.ETN, vtec.office, 
              vtec.phenomena, vtec.significance)
        my_ets = "'%s'" % (vtec.endts,)
        if vtec.endts is None:
            my_ets = """(SELECT expire from %s WHERE eventid = %s 
              and wfo = '%s' and phenomena = '%s' and significance = '%s' 
              LIMIT 1)""" % (sbw_table, vtec.ETN, vtec.office, 
              vtec.phenomena, vtec.significance)

        tml_valid = None
        tml_column = 'tml_geom'
        if segment.tml_giswkt and segment.tml_giswkt.find("LINE") > 0:
            tml_column = 'tml_geom_line'
        if segment.tml_valid:
            tml_valid = segment.tml_valid
        if vtec.action in ['CAN',]:
            sql = """INSERT into """+ sbw_table +"""(wfo, eventid, 
                significance, phenomena, issue, expire, init_expire, polygon_begin, 
                polygon_end, geom, status, report, windtag, hailtag, tornadotag,
                tornadodamagetag, tml_valid, tml_direction, tml_sknt,
                """+ tml_column +""") VALUES (%s,
                %s,%s,%s,"""+ my_sts +""",%s,"""+ my_ets +""",%s,%s,%s,%s,%s,
                %s,%s,%s,%s, %s, %s, %s, %s)"""
            myargs = (vtec.office, vtec.ETN, 
                 vtec.significance, vtec.phenomena, 
                 self.valid, 
                 self.valid, 
                 self.valid, 
                  segment.giswkt, vtec.action, self.unixtext,
                 segment.windtag, segment.hailtag, 
                 segment.tornadotag, segment.tornadodamagetag,
                 tml_valid, segment.tml_dir, segment.tml_sknt, 
                 segment.tml_giswkt)

        elif vtec.action in ['EXP', 'UPG', 'EXT']:
            sql = """INSERT into """+ sbw_table +"""(wfo, eventid, significance,
                phenomena, issue, expire, init_expire, polygon_begin, 
                polygon_end, geom, 
                status, report, windtag, hailtag, tornadotag, tornadodamagetag, 
                tml_valid, tml_direction, tml_sknt,
                """+ tml_column +""") VALUES (%s,
                %s,%s,%s, """+ my_sts +""","""+ my_ets +""","""+ my_ets +""",%s,%s, 
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
            vvv = self.valid
            if vtec.endts:
                vvv = vtec.endts
            myargs = ( vtec.office, vtec.ETN, 
                 vtec.significance, vtec.phenomena, vvv, vvv, 
                  segment.giswkt, vtec.action, self.unixtext, 
                  segment.windtag, segment.hailtag,
                  segment.tornadotag, segment.tornadodamagetag,
                  tml_valid, segment.tml_dir, 
                  segment.tml_sknt, segment.tml_giswkt)
        else:
            _expire = vtec.endts
            if vtec.endts is None:
                _expire = datetime.datetime.now() + datetime.timedelta(days=10)
                _expire = _expire.replace(tzinfo=pytz.timezone("UTC"))
            sql = """INSERT into """+ sbw_table +"""(wfo, eventid, 
                significance, phenomena, issue, expire, init_expire, 
                polygon_begin, polygon_end, geom, 
                status, report, windtag, hailtag, tornadotag, tornadodamagetag, 
                tml_valid, tml_direction, tml_sknt,
                """+ tml_column +""") VALUES (%s,
                %s,%s,%s, """+ my_sts +""",%s,%s,%s,%s, %s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s)""" 
            vvv = self.valid
            if vtec.begints:
                vvv = vtec.begints
            wkt = "SRID=4326;%s" % (MultiPolygon([segment.sbw]).wkt,)
            myargs = (vtec.office, vtec.ETN, 
                 vtec.significance, vtec.phenomena, _expire, 
                 _expire, vvv, 
                 _expire, wkt, vtec.action, self.unixtext,
                 segment.windtag, segment.hailtag, 
                 segment.tornadotag, segment.tornadodamagetag,
                 tml_valid, segment.tml_dir, 
                 segment.tml_sknt, segment.tml_giswkt)
        txn.execute(sql, myargs)

    def get_jabbers(self, uri):
        ''' Return a list[plain, html string] for jabber messages '''
        utcnow = datetime.datetime.utcnow().replace(tzinfo=pytz.timezone("UTC"))
        wfo = self.source[1:]
        xtra = {'product_id': self.get_product_id(),
                'tweet': ''}
        if self.skip_con:
            xtra['tweet'] = '%s issues updated FLS product %s?wfo=%s' % (wfo, 
                                                                uri, wfo)
            text = ("%s has sent an updated FLS product (continued products "
                    +"were not reported here).  Consult this website for more "
                    +"details. %s?wfo=%s") % (wfo, uri, wfo)
            html = ("%s has sent an updated FLS product (continued products "
                    +"were not reported here).  Consult "
                    +"<a href=\"%s?wfo=%s\">this website</a> for more "
                    +"details.") % (wfo, uri, wfo)
            return [(text, html, xtra)]
        msgs = []
        for segment in self.segments:
            # Compute affected WFOs
            affected_wfos = {wfo: True}
            for ugc in segment.ugcs:
                for wfo in ugc.wfos:
                    affected_wfos[ wfo ] = True
            xtra['channels'] = ",".join(affected_wfos.keys(),)
            for vtec in segment.vtec:
                # Set up Jabber Dict for stuff to fill in
                jmsg_dict = {'wfo': vtec.office, 'product': vtec.product_string(),
                             'county': ugcs_to_text(segment.ugcs), 
                             'sts': ' ', 'ets': ' ', 
                             'svs_special': '',
                             'year': self.valid.year, 'phenomena': vtec.phenomena,
                             'eventid': vtec.ETN, 'significance': vtec.significance,
                             'url': "%s#%s" % (uri, 
                               vtec.url(self.valid.year)) }
                if len(segment.hvtec) > 0:
                    jmsg_dict['county'] = segment.hvtec[0].nwsli.get_name()
                if (vtec.begints is not None and
                    vtec.begints > (utcnow + datetime.timedelta(hours=1))): 
                    jmsg_dict['sts'] = vtec.get_begin_string(self)
                jmsg_dict['ets'] = vtec.get_end_string(self)

                if (vtec.phenomena in ['TO',] and vtec.significance == 'W'):
                    jmsg_dict['svs_special'] = segment.svs_search()

                plain = ("%(wfo)s %(product)s %(sts)s for "
                        +"%(county)s %(ets)s %(svs_special)s "
                        +"%(url)s") % jmsg_dict
                html = ("%(wfo)s <a href='%(url)s'>%(product)s</a> "
                        +"%(sts)s for %(county)s "
                        +"%(ets)s %(svs_special)s") % jmsg_dict
                msgs.append([plain,html,xtra])
        
        return msgs

    def get_skip_con(self):
        ''' Should this product be skipped from generating jabber messages'''
        if self.afos[:3] == 'FLS' and len(self.segments) > 4:
            return True
        return False

def parser(text, utcnow=None, ugc_provider={}, nwsli_provider={}):
    ''' Helper function that actually converts the raw text and emits an
    VTECProduct instance or returns an exception'''
    prod = VTECProduct(text, utcnow=utcnow, ugc_provider=ugc_provider,
                       nwsli_provider=nwsli_provider)
    
    
    return prod