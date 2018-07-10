"""TAF Parsing"""

from pyiem.nws.product import TextProduct
from pyiem import reference


class TAFProduct(TextProduct):
    """
    Represents a TAF
    """

    def __init__(self, text, utcnow=None, ugc_provider=None,
                 nwsli_provider=None):
        """ constructor """
        TextProduct.__init__(self, text, utcnow, ugc_provider, nwsli_provider)

    def get_channels(self):
        """ Return a list of channels """
        return [self.afos, "TAF...", "%s.TAF" % (self.source, )]

    def get_jabbers(self, uri, uri2=None):
        """ Get the jabber variant of this message """
        res = []
        # These products can be ignored
        if self.afos is None:
            return res
        url = "%s?pid=%s" % (uri, self.get_product_id())
        aaa = self.afos[:3]
        nicedate = self.get_nicedate()
        plain = ("%s issues %s (%s) at %s for %s %s"
                 ) % (self.source[1:],
                      reference.prodDefinitions.get(aaa, aaa),
                      aaa, nicedate, self.afos[3:], url)
        html = ('<p>%s issues <a href="%s">%s (%s)</a> at %s for %s</p>'
                ) % (self.source[1:], url,
                     reference.prodDefinitions.get(aaa, aaa),
                     aaa, nicedate, self.afos[3:])
        xtra = {
                'channels': ",".join(self.get_channels()),
                'product_id': self.get_product_id(),
                'twitter': plain
                }
        res.append((plain, html, xtra))
        return res


def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    """ Helper function """
    return TAFProduct(text, utcnow, ugc_provider, nwsli_provider)
