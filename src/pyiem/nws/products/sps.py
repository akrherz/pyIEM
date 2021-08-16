"""Special Weather Statement"""
import re
import datetime

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
            if headline.upper().find(ugc.name.upper()) > -1:
                hits += 1
        if (float(hits) / float(len(ugcs))) > 0.7:
            counties = ""

    return counties, expire


def _sql_segment(prod, txn, seg):
    """Do the database insert for this segment."""
    ugcs = [str(s) for s in seg.ugcs]
    ets = prod.valid + datetime.timedelta(hours=1)
    if seg.ugcexpire is not None:
        ets = seg.ugcexpire
    tml_valid = None
    tml_column = "tml_geom"
    if seg.tml_giswkt and seg.tml_giswkt.find("LINE") > 0:
        tml_column = "tml_geom_line"
    if seg.tml_valid:
        tml_valid = seg.tml_valid

    empty = "POLYGON EMPTY"
    txn.execute(
        "INSERT into sps(product_id, product, pil, wfo, issue, expire, "
        "geom, ugcs, landspout, waterspout, max_hail_size, max_wind_gust, "
        f"tml_valid, tml_direction, tml_sknt, {tml_column}, segmentnum) "
        "VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
        "%s, %s, %s)",
        (
            prod.get_product_id(),
            prod.unixtext,
            prod.afos,
            prod.source[1:],
            prod.valid,
            ets,
            f"SRID=4326;{empty if seg.sbw is None else seg.sbw.wkt}",
            ugcs,
            seg.landspouttag,
            seg.waterspouttag,
            seg.hailtag,
            seg.windtag,
            tml_valid,
            seg.tml_dir,
            seg.tml_sknt,
            seg.tml_giswkt,
            prod.segments.index(seg),
        ),
    )


class SPSProduct(TextProduct):
    """A Special Weather Statement"""

    def sql(self, txn):
        """Do database save in the case of a polygon"""
        if not self.segments:
            self.warnings.append("sql() save failed with no segments?")
            return
        for seg in self.segments:
            if not seg.ugcs:
                continue
            _sql_segment(self, txn, seg)

    def _get_channels(self, segment):
        """Returns a list of channels for this SPS."""
        channels = self.get_channels()
        for ugc in segment.ugcs:
            sugc = str(ugc)
            channels.append(f"{self.afos}.{ugc}")
            channels.append(sugc)
            channel = f"SPS.{sugc[:2]}"
            if channel not in channels:
                channels.append(channel)
        return channels

    def get_jabbers(self, uri, _uri2=None):
        """return the standard [[text, html, xtra], ] for jabber"""
        res = []
        for segnum, seg in enumerate(self.segments):
            # Skip any segments that don't have UGC information
            if not seg.ugcs:
                continue
            # Need to keep this dictionary obj unique per message
            xtra = {
                "product_id": self.get_product_id(),
                "twitter_media": (
                    "https://mesonet.agron.iastate.edu/plotting/auto/plot/217/"
                    f"pid:{self.get_product_id()}::segnum:{segnum}.png"
                ),
            }
            headline = "[No headline was found in SPS]"
            if seg.headlines:
                headline = (seg.headlines[0]).replace("\n", " ")
            elif SPECIAL_WX_STATEMENT.search(seg.unixtext):
                headline = "Special Weather Statement"
            counties = " for %s" % (ugcs_to_text(seg.ugcs),)
            expire = ""
            if seg.ugcexpire is not None:
                expire = " till %s %s" % (
                    (
                        seg.ugcexpire
                        - datetime.timedelta(
                            hours=reference.offsets.get(self.z, 0)
                        )
                    ).strftime("%-I:%M %p"),
                    self.z,
                )
            counties, expire = dedup_headline(
                headline, seg.ugcs, counties, expire
            )
            xtra["channels"] = self._get_channels(seg)
            tags = seg.special_tags_to_text()
            mess = ("%s issues %s%s%s%s %s?pid=%s") % (
                self.source[1:],
                headline,
                tags,
                counties,
                expire,
                uri,
                xtra["product_id"],
            )
            htmlmess = (
                "<p>%s issues <a href='%s?pid=%s'>%s</a>%s%s%s</p>"
            ) % (
                self.source[1:],
                uri,
                xtra["product_id"],
                headline,
                tags,
                counties,
                expire,
            )
            xtra["twitter"] = "%s%s%s%s %s?pid=%s" % (
                headline,
                tags,
                counties,
                expire,
                uri,
                xtra["product_id"],
            )
            # Check our length
            remaining = (
                reference.TWEET_CHARS
                - len(xtra["twitter"].rsplit(" ", 1)[0])
                - 25
            )
            if remaining <= 0:
                xtra["twitter"] = "%s%s%s%s %s?pid=%s" % (
                    headline,
                    tags,
                    counties[: (remaining - 5)] + "... ",
                    expire,
                    uri,
                    xtra["product_id"],
                )
            res.append([mess, htmlmess, xtra])

        return res


def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    """The SPS Parser"""
    return SPSProduct(
        text, utcnow, ugc_provider=ugc_provider, nwsli_provider=nwsli_provider
    )
