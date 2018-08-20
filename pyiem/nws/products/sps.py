"""Special Weather Statement"""
import re
import datetime

from shapely.geometry import MultiPolygon
from pyiem import reference
from pyiem.nws.product import TextProduct
from pyiem.nws.ugc import ugcs_to_text

SPECIAL_WX_STATEMENT = re.compile("SPECIAL WEATHER STATEMENT", re.I)
TILL = re.compile(" (TILL|UNTIL|THROUGH) [0-9]{1,2}:?[0-5][0-9]", re.I)


def dedup_headline(headline, ugcs, counties, expire):
    """Try to not be redundant

    Args:
      headline (str): our current headline
      ugcs (list(ugc)): list of ugcs this SPS is for
      counties (str): our current parsed string of counties
      expire (str): our current parsed expiration string

    Returns:
       (str): our new counties, which has been deduped
       (str): our new expire, which has been deduped
    """
    if TILL.search(headline):
        expire = ""
    if ugcs:
        hits = 0
        for ugc in ugcs:
            if ugc.name is None:
                continue
            if headline.upper().find(ugc.name.upper()) > -1:
                hits += 1
        if (float(hits) / float(len(ugcs))) > 0.7:
            counties = ""

    return counties, expire


class SPSProduct(TextProduct):
    """A Special Weather Statement"""

    def sql(self, txn):
        """Do database save in the case of a polygon"""
        for seg in self.segments:
            if not seg.sbw:
                continue
            # Figure out an end time
            ets = self.valid + datetime.timedelta(hours=1)
            if seg.ugcexpire is not None:
                ets = seg.ugcexpire
            giswkt = 'SRID=4326;%s' % (MultiPolygon([seg.sbw]).wkt,)
            sql = """
                INSERT into text_products(product, product_id, geom,
                issue, expire, pil) values (%s, %s, %s, %s, %s, %s)
            """
            myargs = (self.unixtext, self.get_product_id(), giswkt,
                      self.valid, ets, self.afos)
            txn.execute(sql, myargs)

    def _get_channels(self, segment):
        """Returns a list of channels for this SPS."""
        channels = self.get_channels()
        for ugc in segment.ugcs:
            channels.append("%s.%s" % (self.afos, ugc))
            channels.append(str(ugc))
        return channels

    def get_jabbers(self, uri, uri2=None):
        """return the standard [[text, html, xtra], ] for jabber"""
        res = []
        xtra = {'product_id': self.get_product_id()}
        for seg in self.segments:
            # Skip any segments that don't have UGC information
            if not seg.ugcs:
                continue
            headline = "[No headline was found in SPS]"
            if seg.headlines:
                headline = (seg.headlines[0]).replace("\n", " ")
            elif SPECIAL_WX_STATEMENT.search(seg.unixtext):
                headline = "Special Weather Statement"
            counties = " for %s" % (ugcs_to_text(seg.ugcs), )
            expire = ""
            if seg.ugcexpire is not None:
                expire = " till %s %s" % (
                    (seg.ugcexpire -
                     datetime.timedelta(hours=reference.offsets.get(self.z, 0))
                     ).strftime("%-I:%M %p"), self.z)
            counties, expire = dedup_headline(headline, seg.ugcs, counties,
                                              expire)
            xtra['channels'] = self._get_channels(seg)
            mess = ("%s issues %s%s%s %s?pid=%s"
                    ) % (self.source[1:], headline, counties,
                         expire, uri, xtra['product_id'])
            htmlmess = ("<p>%s issues <a href='%s?pid=%s'>%s</a>%s%s</p>"
                        ) % (self.source[1:], uri, xtra['product_id'],
                             headline, counties, expire)
            xtra['twitter'] = "%s%s%s %s?pid=%s" % (headline, counties,
                                                    expire, uri,
                                                    xtra['product_id'])
            res.append([mess, htmlmess, xtra])

        return res


def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    """The SPS Parser"""
    return SPSProduct(text, utcnow, ugc_provider=ugc_provider,
                      nwsli_provider=nwsli_provider)
