"""Space Weather Center processor"""

import pyiem.nws.product as product


class SpaceWxProduct(product.TextProduct):
    """Class for parsing and representing Space Wx Products"""

    def __init__(
        self, text, utcnow=None, ugc_provider=None, nwsli_provider=None
    ):
        """constructor"""
        product.TextProduct.__init__(
            self, text, utcnow, ugc_provider, nwsli_provider
        )
        self.title = "Unknown (AWIPSID: %s)" % (self.afos,)
        if len(self.sections) >= 2:
            self.title = self.sections[2].split("\n")[0]

    def get_jabbers(self, uri, _uri2=None):
        """Custom Implementation of the TextProduct#get_jabbers"""
        url = "%s?pid=%s" % (uri, self.get_product_id())
        xtra = {
            "channels": "WNP,%s" % (self.afos,),
            "twitter": "SWPC issues %s %s" % (self.title, url),
        }
        plain = ("Space Weather Prediction Center issues %s %s") % (
            self.title,
            url,
        )
        html = (
            "<p>Space Weather Prediction Center "
            '<a href="%s">issues %s</a></p>'
        ) % (url, self.title)
        return [(plain, html, xtra)]


def parser(buf, utcnow=None, ugc_provider=None, nwsli_provider=None):
    """A parser implementation"""
    return SpaceWxProduct(buf, utcnow, ugc_provider, nwsli_provider)
