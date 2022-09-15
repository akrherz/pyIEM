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
        self.title = f"Unknown (AWIPSID: {self.afos})"
        if len(self.sections) >= 2:
            self.title = self.sections[2].split("\n")[0]

    def get_jabbers(self, uri, _uri2=None):
        """Custom Implementation of the TextProduct#get_jabbers"""
        url = f"{uri}?pid={self.get_product_id()}"
        xtra = {
            "channels": f"WNP,{self.afos}",
            "twitter": f"SWPC issues {self.title} {url}",
        }
        plain = f"Space Weather Prediction Center issues {self.title} {url}"
        html = (
            "<p>Space Weather Prediction Center "
            f'<a href="{url}">issues {self.title}</a></p>'
        )
        return [(plain, html, xtra)]


def parser(buf, utcnow=None, ugc_provider=None, nwsli_provider=None):
    """A parser implementation"""
    return SpaceWxProduct(buf, utcnow, ugc_provider, nwsli_provider)
