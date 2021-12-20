"""
Eh, I am able to parse the SPC PTS now, so why not add more pain.

Weather Prediction Center Excessive Rainfall Outlook.
"""
import re
import datetime
import tempfile
import math

from shapely.geometry import MultiPolygon

from metpy.units import units

# Local
from pyiem.reference import txt2drct
from pyiem.nws.product import TextProduct
from pyiem.util import LOG, load_geodf
from ._outlook_util import (
    CONUS,
    condition_segment,
    convert_segments,
    winding_logic,
    load_conus_data,
    THRESHOLD2TEXT,
    sql_day_collect,
    quality_control,
)

RISK_RE = re.compile(
    r"^(?P<cat>MARGINAL|SLIGHT|MODERATE|HIGH)",
    re.I,
)
VALID_RE = re.compile(
    r"Valid\s+(?P<start>[0-9]{1,4})Z?\s+...\s+(?P<smonth>[A-Z]{3})\s+"
    r"(?P<sday>\d+)\s+(?P<syear>\d\d\d\d)\s+\-\s+"
    r"(?P<end>[0-9]{1,4})Z?\s+...\s+(?P<emonth>[A-Z]{3})\s+"
    r"(?P<eday>\d+)\s+(?P<eyear>\d\d\d\d)",
    re.IGNORECASE,
)

TEXT2THRESHOLD = {
    "MARGINAL": "MRGL",
    "SLIGHT": "SLGT",
    "ENHANCED": "ENH",
    "MODERATE": "MDT",
    "HIGH": "HIGH",
}


def init_days(prod):
    """Figure out which days this product should have based on the AFOS."""
    day = 1
    if prod.afos == "RBG98E":
        day = 2
    elif prod.afos == "RBG99E":
        day = 3
    return day, {day: OutlookCollection(prod.issue, prod.expire, day)}


def _compute_cycle(prod):
    """Figure out an integer cycle that identifies this product."""
    if prod.day == 1:
        if prod.valid.hour in range(0, 6):
            return 1
        if prod.valid.hour in range(6, 13):
            return 8
        if prod.valid.hour in range(13, 20):
            return 16
    if prod.valid.hour in range(4, 12):
        return 8
    if prod.valid.hour in range(17, 22):
        return 20
    return -1


def compute_loc(lon, lat, dist, bearing):
    """Estimate a lat/lon"""
    meters = (units("mile") * dist).to(units("meter")).m
    northing = meters * math.cos(math.radians(bearing)) / 111111.0
    easting = (
        meters
        * math.sin(math.radians(bearing))
        / math.cos(math.radians(lat))
        / 111111.0
    )
    return lon + easting, lat + northing


def sid_rectify(sid):
    """Ensure it matches our nomenclature."""
    if sid.startswith("K") and len(sid) == 4:
        return sid[1:]
    return sid


def meat2segment(meat):
    """Convert into a list of points."""
    asos = load_geodf("sfstns")
    tokens = meat.split()
    sz = len(tokens)
    i = 0
    pts = []
    gc = "geometry"
    while i < sz:
        token = tokens[i]
        if token.isdigit() and (i + 2) < sz:
            miles = float(token)
            drct = txt2drct.get(tokens[i + 1])
            sid = sid_rectify(tokens[i + 2])
            row = asos.loc[sid]
            pts.append(compute_loc(row[gc].x, row[gc].y, miles, drct))
            i += 3
            continue
        sid = sid_rectify(tokens[i])
        row = asos.loc[sid]
        pts.append([row[gc].x, row[gc].y])
        i += 1
    return pts


class OutlookCollection:
    """A collection of outlooks for a single 'day'"""

    def __init__(self, issue, expire, day):
        """Constructor"""
        self.issue = issue
        self.expire = expire
        self.day = day
        self.outlooks = []


class Outlook:
    """A class holding what we store for a single outlook."""

    def __init__(self, category, threshold, multipoly):
        """Constructor.

        Args:
          category (str): the label of this category
          threshold (str): the threshold associated with the category
          multipoly (MultiPolygon): the geometry
        """
        self.category = category
        self.threshold = threshold
        self.geometry = multipoly
        self.wfos = []


def jabber_messages(valid, outlook_collections) -> list:
    """Generate a list of Jabber messages to send.

    Args:
        valid (datetime): the valid time of the outlook
        outlook_collections (dict): a list of OutlookCollection objects

    Returns:
        list: a list of Jabber messages [(plain, html, xtradict), ...]
    """
    res = []
    url = "https://www.wpc.ncep.noaa.gov/archives/web_pages/ero/ero.shtml"
    product_descript = "Excessive Rainfall Outlook"
    jdict = {
        "title": product_descript,
        "name": "The Weather Prediction Center",
        "tstamp": valid.strftime("%b %-d, %-H:%Mz"),
        "url": url,
        "wfo": "DMX",  # autoplot expects something valid here
        "cat": "E",
        "t220": "cwa",
    }
    twmedia = (
        "https://mesonet.agron.iastate.edu/plotting/auto/plot/220/"
        "cat:categorical::which:%(day)s%(cat)s::t:%(t220)s::network:WFO::"
        "wfo:%(wfo)s::"
        f"csector:conus::valid:{valid.strftime('%Y-%m-%d %H%M')}"
        ".png"
    ).replace(" ", "%%20")
    for day, collect in outlook_collections.items():

        wfos = {
            "MRGL": [],
            "SLGT": [],
            "ENH": [],
            "MDT": [],
            "HIGH": [],
        }

        for outlook in collect.outlooks:
            _d = wfos.setdefault(outlook.threshold, [])
            _d.extend(outlook.wfos)

        jdict["day"] = day
        wfomsgs = {}
        # We order in least to greatest, so that the highest threshold
        # overwrites lower ones
        for cat in [
            "MRGL",
            "SLGT",
            "ENH",
            "MDT",
            "HIGH",
        ]:
            jdict["ttext"] = f"{THRESHOLD2TEXT[cat]} Risk {product_descript}"
            for wfo in wfos[cat]:
                jdict["wfo"] = wfo
                wfomsgs[wfo] = [
                    (
                        "%(name)s issues Day %(day)s %(ttext)s "
                        "at %(tstamp)s for portions of %(wfo)s %(url)s"
                    )
                    % jdict,
                    (
                        "<p>%(name)s issues "
                        '<a href="%(url)s">Day %(day)s %(ttext)s</a> '
                        "at %(tstamp)s for portions of %(wfo)s's area</p>"
                    )
                    % jdict,
                    {
                        "channels": [
                            wfo,
                            f"{wfo}.ERODY{day}",
                            f"{wfo}.ERODY{day}.{cat}",
                        ],
                        "twitter_media": twmedia % jdict,
                        "twitter": (
                            "WPC issues Day %(day)s %(ttext)s "
                            "at %(tstamp)s for %(wfo)s %(url)s"
                        )
                        % jdict,
                    },
                ]
        keys = list(wfomsgs.keys())
        keys.sort()
        for wfo in keys:
            res.append(wfomsgs[wfo])

    # Generic for WPC
    jdict["t220"] = "conus"
    jdict["title2"] = "%(name)s issues Day %(day)s %(title)s" % jdict
    res.append(
        [
            "%(title2)s at %(tstamp)s %(url)s" % jdict,
            (
                '<p>%(name)s issues <a href="%(url)s">Day %(day)s '
                "%(title)s</a> at %(tstamp)s</p>"
            )
            % jdict,
            {
                "channels": ["WPC", "ERODY%(day)s" % jdict],
                "twitter_media": twmedia % jdict,
                "twitter": "%(title2)s at %(tstamp)s %(url)s" % jdict,
            },
        ],
    )
    return res


def compute_wfos(outlook_collections):
    """Compute the WFOs affected for each outlook in collection."""
    # self.draw_outlooks()
    geodf = load_geodf("cwa")
    for day, collect in outlook_collections.items():
        for outlook in collect.outlooks:
            df2 = geodf[geodf["geom"].intersects(outlook.geometry)]
            outlook.wfos = df2.index.to_list()
            LOG.info(
                "Day: %s Category: %s Threshold: %s #WFOS: %s %s",
                day,
                outlook.category,
                outlook.threshold,
                len(outlook.wfos),
                ",".join(outlook.wfos),
            )


class ERO(TextProduct):
    """A class representing the polygons and metadata in WPC ERO Product"""

    def __init__(
        self, text, utcnow=None, ugc_provider=None, nwsli_provider=None
    ):
        """Constructor

        Args:
          text (string): the raw PTS product that is to be parsed
          utcnow (datetime, optional): in case of ambuigity with time
          ugc_provider (dict, optional): unused in this class
          nwsli_provider (dict, optional): unused in this class
        """
        TextProduct.__init__(self, text, utcnow, ugc_provider, nwsli_provider)
        LOG.info("==== ERO Processing: %s", self.get_product_id())
        load_conus_data()
        self.issue = None
        self.expire = None
        self.outlook_type = "E"
        self.find_issue_expire()
        self.day, self.outlook_collections = init_days(self)
        self.find_outlooks()
        quality_control(self)
        compute_wfos(self.outlook_collections)
        self.cycle = _compute_cycle(self)

    def get_outlookcollection(self, day):
        """Returns the OutlookCollection for a given day"""
        return self.outlook_collections.get(day)

    def get_outlook(self, category, threshold, day):
        """Get an outlook by category and threshold"""
        if day not in self.outlook_collections:
            return None
        for outlook in self.outlook_collections[day].outlooks:
            if outlook.category == category and outlook.threshold == threshold:
                return outlook
        return None

    def draw_outlooks(self):
        """For debugging, draw the outlooks on a simple map for inspection!"""
        # pylint: disable=import-outside-toplevel
        import matplotlib.pyplot as plt

        for day, collect in self.outlook_collections.items():
            for outlook in collect.outlooks:
                fig = plt.figure(figsize=(12, 8))
                ax = fig.add_subplot(111)
                # pylint: disable=unsubscriptable-object
                ax.plot(
                    CONUS["line"][:, 0],
                    CONUS["line"][:, 1],
                    color="b",
                    label="Conus",
                )
                for poly in outlook.geometry.geoms:
                    ax.plot(
                        poly.exterior.xy[0],
                        poly.exterior.xy[1],
                        lw=2,
                        color="r",
                    )
                ax.set_title(
                    f"Day {day} Category {outlook.category} "
                    f"Threshold {outlook.threshold}"
                )
                ax.legend(loc=3)
                fn = (
                    f"{tempfile.gettempdir()}/{day}_{self.issue:%Y%m%d%H%M}_"
                    f"{outlook.category}_{outlook.threshold}.png"
                ).replace(" ", "_")
                LOG.info(":: creating plot %s", fn)
                fig.savefig(fn)
                plt.close()

    def find_issue_expire(self):
        """
        Determine the period this product is valid for
        """
        m = VALID_RE.findall(self.text)[0]
        if len(m[0]) >= 3:
            hour1 = int(m[0][:2])
            minute1 = int(m[0][-2:])
        else:
            hour1 = int(m[0])
            minute1 = 0
        if len(m[4]) >= 3:
            hour2 = int(m[4][:2])
            minute2 = int(m[4][-2:])
        else:
            hour2 = int(m[4])
            minute2 = 0
        self.issue = datetime.datetime.strptime(
            f"{hour1}:{minute1} {m[1]} {m[2]} {m[3]}",
            "%H:%M %b %d %Y",
        ).replace(tzinfo=datetime.timezone.utc)
        self.expire = datetime.datetime.strptime(
            f"{hour2}:{minute2} {m[5]} {m[6]} {m[7]}",
            "%H:%M %b %d %Y",
        ).replace(tzinfo=datetime.timezone.utc)

    def find_outlooks(self):
        """Find the outlook sections within the text product!"""
        text = "\n".join([x.strip() for x in self.text.split("\n")])
        tokens = text.strip().split("\n\n")
        point_data = {}
        for token in tokens:
            section = token.strip().replace("\n", " ")
            m = RISK_RE.match(section)
            if m is None:
                continue
            threshold = TEXT2THRESHOLD[m.groupdict()["cat"]]
            arr = point_data.setdefault(threshold, [])
            meat = section.split(" FROM ", 1)[1].replace(".", "")
            arr.append(meat2segment(meat))
        collect = self.get_outlookcollection(self.day)
        for threshold, pdata in point_data.items():
            segments = []
            for segment in pdata:
                res = condition_segment(segment)
                if res:
                    segments.extend(res)
            polygons, _interiors, linestrings = convert_segments(segments)
            # we do our winding logic now
            polygons.extend(winding_logic(linestrings))
            mp = MultiPolygon(polygons)
            collect.outlooks.append(Outlook("CATEGORICAL", threshold, mp))

    def sql(self, txn):
        """Do database work

        Args:
          txn (psycopg2.cursor): database cursor
        """
        for day, collect in self.outlook_collections.items():
            sql_day_collect(self, txn, day, collect)

    def get_jabbers(self, uri, _uri2=None):
        """Wordsmith the Jabber/Twitter Messaging"""
        return jabber_messages(self.valid, self.outlook_collections)


def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    """Parse this text!"""
    return ERO(text, utcnow, ugc_provider, nwsli_provider)
