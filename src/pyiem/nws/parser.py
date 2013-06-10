"""
 This is my NWS text product parser, it emits a dict with all sorts of
 fun included 
"""
import re

from pyiem.nws.product import TextProduct
from pyiem.nws.ugc import UGC
from pyiem import reference

SIMPLE_PRODUCTS = ["TCE", "DSA", "AQA", "DGT", "FWF", "RTP", "HPA", "CWF", 
            "SRF", "SFT", "PFM", "ZFP", "CAE", "AFD", "FTM", "AWU", "HWO",
            "NOW", "PSH", "NOW", "PNS", "RER", "ADM", "TCU", "RVA", "EQR",
            "OEP", "SIG", "VAA", "RVF", "PWO", "TWO", "TCM", "TCD", "TCP"]

class Tweet(object):
    """ Represent a tweet """

    def __init__(self, plain, url=None, xtra={}):
        """ Constructor """
        self.plain = plain
        self.url = url
        self.xtra = xtra

class JabberMessage(object):
    """ Represent a message we can send to the jabber server """

    def __init__(self, plain, html=None, xtra={}):
        """ Constructor """
        self.plain = plain
        self.html = html
        self.xtra = xtra

class Engine(object):
    """ Represents some data parsing engine """
    
    def __init__(self, config=None):
        """ Constructor """
        self.config = config
        self.ugcs = {}
        self.nwslis = {}
        if config is None:
            self.config = {
                           'product_uri': 'http://localhost/'
                           }

    def dbload_ugcs(self, txn):
        """ Load database definitions of UGC codes """
        sql = "SELECT name, ugc from nws_ugc WHERE name IS NOT Null"
        txn.execute( sql )
        for row in txn:
            self.ugcs[ row['ugc'] ] = UGC(row['ugc'][:2], row['ugc'][2], 
                                          row['ugc'][3:],
                                      row['name'])

    def dbload_nwsli(self, txn):
        """ Load nwsli information from the database """
        sql = """SELECT nwsli, river_name as r, 
             proximity || ' ' || name || ' ['||state||']' as rname 
             from hvtec_nwsli"""
        txn.execute(sql)
        for row in txn:
            self.nwslis[ row['nwsli'] ] = {
                                'rname': (row['r']).replace("&"," and "), 
                                'river': (row['rname']).replace("&"," and ") }

    def simple_tweet(self, tp):
        """ Convert Text Product into a simple tweet message """
        uri = "%s%s" % (self.config['product_uri'], tp.get_product_id())
        xtra = {'channels': [tp.afos,],
                }
        return Tweet("%s issues %s" % (tp.source[1:],
                reference.prodDefinitions.get(tp.afos[:3])), uri, xtra )

    def simple_jabber_msg(self, tp):
        """ Make a simple message from a text product """
        uri = "%s%s" % (self.config['product_uri'], tp.get_product_id())
        plain = "%s issues %s %s" % (tp.source[1:],
                reference.prodDefinitions.get(tp.afos[:3], tp.afos[:3]),
                uri)
        html = "%s issues <a href=\"%s\">%s</a>" % (tp.source[1:], uri,
                reference.prodDefinitions.get(tp.afos[:3], tp.afos[:3]))
        xtra = {'product_id': tp.get_product_id(),
                'channels': [tp.afos,]}
        return JabberMessage(plain, html, xtra)
        
    def text_products_db(self, tp):
        """ Generate the proper SQL statement and args for this TextProduct"""
        sqlraw = tp.unixtext.replace("\000", "").strip()
        sql = """INSERT into text_products(product, product_id) values (%s,%s)"""
        myargs = (sqlraw, tp.get_product_id())
        if len(tp.segments) > 0 and tp.segments[0].giswkt:
            sql = """INSERT into text_products(product, product_id, geom) values (%s,%s,%s)""" 
            myargs = (sqlraw, tp.get_product_id(), tp.segments[0].giswkt)
        return sql, myargs
    
    def jabber_rvf_segment_hander(self, tp, seg):
        """ Process a TextProduct into jabber msgs """
        tokens = re.findall("\.E ([A-Z0-9]{5}) ", seg.raw)
        if len(tokens) == 0:
            return None
        wfo = tp.source[1:]
        uri = "%s%s" % (self.config['product_uri'], tp.get_product_id())
        hsas = re.findall("HSA:([A-Z]{3}) ", seg.raw)
        prodtxt = reference.prodDefinitions[ tp.afos[:3] ]
        mess = "%s issues %s %s" % (wfo, prodtxt, uri)
        htmlmess = "%s issues <a href=\"%s\">%s</a> for " % (wfo, uri, prodtxt)
        usednwsli = {}
        hsa_cnt = -1
        rivers = {}
        j = []
        for nwsli in tokens:
            if usednwsli.has_key(nwsli):
                continue
            usednwsli[nwsli] = 1
            hsa_cnt += 1
            if self.nwslis.has_key(nwsli):
                rname = self.nwslis[nwsli]['rname']
                r = self.nwslis[nwsli]['river']
            else:
                rname = "((%s))" % (nwsli,)
                r = "Unknown River"
            if not rivers.has_key(r):
                rivers[r] = "<br/>%s " % (r,)
            if len(hsas) > hsa_cnt and reference.wfo_dict.has_key( hsas[hsa_cnt] ):
                rivers[r] += "%s (%s), " % (rname, nwsli)
            for r in rivers.keys():
                htmlmess += " %s" % (rivers[r][:-2],)
            j.append( JabberMessage(mess, htmlmess[:-1]) )
        return j
    
    def handle_vtec_segment(self, tp, seg, res):
        """ Process VTEC segment, lots to do! """
        pass
    
    def parse(self, raw ):
        """
        Parse the raw string into something we can use
        """
        res = dict(jabber_msgs = [], sqls = [], tweets = [])
        tp = TextProduct( raw , ugc_provider=self.ugcs)
        res['sqls'].append( self.text_products_db(tp) )
        if tp.afos and tp.afos[:3] in SIMPLE_PRODUCTS:
            res['jabber_msgs'].append( self.simple_jabber_msg(tp) )
            res['tweets'].append( self.simple_tweet(tp) )
        else:
            for seg in tp.segments:
                if tp.afos[:3] == 'RVF':
                    js = self.jabber_rvf_segment_hander(tp, seg)
                    for j in js:
                        res['jabber_msgs'].append( j )
                elif len(seg.vtec) > 0:
                    self.handle_vtec_segment(tp, seg, res)
        
        return res