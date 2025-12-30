"""Parser of the Daily Summary Message (DSM)."""

import re
from datetime import datetime, timedelta

from metpy.units import units

from pyiem.reference import TRACE_VALUE
from pyiem.util import utc
from pyiem.wmo import WMOProduct

PARSER_RE = re.compile(
    r"""^(?P<station>[A-Z][A-Z0-9]{3})\s+
   DS\s+
   (COR\s)?
   ([0-9]{4}\s)?
   (?P<day>\d\d)/(?P<month>\d\d)\s?
   ((?P<highmiss>M)|((?P<high>(-?\d+))(?P<hightime>[0-9]{4})))/\s?
   ((?P<lowmiss>M)|((?P<low>(-?\d+))(?P<lowtime>[0-9]{4})))//\s?
   (?P<coophigh>(-?\d+|M))/\s?
   (?P<cooplow>(-?\d+|M))//
   (?P<minslp>M|[\-0-9]{3,4})(?P<slptime>[0-9]{4})?/
   (?P<pday>T|M|[0-9]{,4})/
    (?P<p01>T|M|\-|\-?[0-9]{,4})/(?P<p02>T|M|\-|\-?[0-9]{,4})/
    (?P<p03>T|M|\-|\-?[0-9]{,4})/(?P<p04>T|M|\-|\-?[0-9]{,4})/
    (?P<p05>T|M|\-|\-?[0-9]{,4})/(?P<p06>T|M|\-|\-?[0-9]{,4})/
    (?P<p07>T|M|\-|\-?[0-9]{,4})/(?P<p08>T|M|\-|\-?[0-9]{,4})/
    (?P<p09>T|M|\-|\-?[0-9]{,4})/(?P<p10>T|M|\-|\-?[0-9]{,4})/
    (?P<p11>T|M|\-|\-?[0-9]{,4})/(?P<p12>T|M|\-|\-?[0-9]{,4})/
    (?P<p13>T|M|\-|\-?[0-9]{,4})/(?P<p14>T|M|\-|\-?[0-9]{,4})/
    (?P<p15>T|M|\-|\-?[0-9]{,4})/(?P<p16>T|M|\-|\-?[0-9]{,4})/
    (?P<p17>T|M|\-|\-?[0-9]{,4})/(?P<p18>T|M|\-|\-?[0-9]{,4})/
    (?P<p19>T|M|\-|\-?[0-9]{,4})/(?P<p20>T|M|\-|\-?[0-9]{,4})/
    (?P<p21>T|M|\-|\-?[0-9]{,4})/(?P<p22>T|M|\-|\-?[0-9]{,4})/
    (?P<p23>T|M|\-|\-?[0-9]{,4})/(?P<p24>T|M|\-|\-?[0-9]{,4})/
   (?P<avg_sped>M|\-|[0-9]{2,3})/
   ((?P<drct_sped_max>[0-9]{2})
    (?P<sped_max>[0-9]{2,3})(?P<time_sped_max>[0-9]{4})/
    (?P<drct_gust_max>[0-9]{2})
    (?P<sped_gust_max>[0-9]{2,3})(?P<time_sped_gust_max>[0-9]{4}))?
""",
    re.VERBOSE,
)


def process(text: str):
    """Emit DSMProduct object for what we can parse."""
    m = PARSER_RE.match(
        " ".join(text.split()).replace("\r", "").replace("\n", "")
    )
    if m is None:
        return None
    return DSMProduct(m.groupdict())


def compute_time(date, timestamp):
    """Make a valid timestamp."""
    if timestamp is None:
        return None
    return datetime(
        date.year,
        date.month,
        date.day,
        int(timestamp[:2]),
        int(timestamp[2:4]),
    )


class DSMProduct:
    """Represents a single DSM."""

    def __init__(self, groupdict):
        """Contructor."""
        self.date = None
        self.high_time = None
        self.low_time = None
        self.time_sped_max = None
        self.time_sped_gust_max = None
        self.station = groupdict["station"]
        self.groupdict = groupdict

    def tzlocalize(self, tzinfo):
        """Localize the timestamps, tricky."""
        offset = tzinfo.utcoffset(datetime(2000, 1, 1)).total_seconds()
        for name in [
            "high_time",
            "low_time",
            "time_sped_max",
            "time_sped_gust_max",
        ]:
            val = getattr(self, name)
            if val is None:
                continue
            # Need to convert timestamp into standard time time, tricky
            ts = val - timedelta(seconds=offset)
            setattr(
                self,
                name,
                utc(ts.year, ts.month, ts.day, ts.hour, ts.minute).astimezone(
                    tzinfo
                ),
            )

    def compute_times(self, utcnow):
        """Figure out when this DSM is valid for."""
        ts = utcnow.replace(
            day=int(self.groupdict["day"]), month=int(self.groupdict["month"])
        )
        # Is this ob from 'last year'
        if ts.month == 12 and utcnow.month == 1:
            ts = ts.replace(year=ts.year - 1)
        self.date = datetime(ts.year, ts.month, ts.day).date()
        self.high_time = compute_time(
            self.date, self.groupdict.get("hightime")
        )
        self.low_time = compute_time(self.date, self.groupdict.get("lowtime"))
        self.time_sped_max = compute_time(
            self.date, self.groupdict.get("time_sped_max")
        )
        self.time_sped_gust_max = compute_time(
            self.date, self.groupdict.get("time_sped_gust_max")
        )

    def sql(self, txn, product_id: str = None):
        """Persist to database given the transaction object."""
        cols = []
        args = []

        val = self.groupdict.get("high")
        if val is not None and val != "M":
            cols.append("max_tmpf")
            args.append(val)

        val = self.groupdict.get("low")
        if val is not None and val != "M":
            cols.append("min_tmpf")
            args.append(val)

        val = self.groupdict.get("pday")
        if val is not None and val != "M":
            cols.append("pday")
            args.append(TRACE_VALUE if val == "T" else float(val) / 100.0)

        val = self.groupdict.get("sped_max")
        if val is not None:
            cols.append("max_sknt")
            args.append(
                (int(val) * units("miles / hour")).to(units("knots")).m
            )

        val = self.time_sped_max
        if val is not None:
            cols.append("max_sknt_ts")
            args.append(val)

        val = self.groupdict.get("sped_gust_max")
        if val is not None:
            cols.append("max_gust")
            args.append(
                (int(val) * units("miles / hour")).to(units("knots")).m
            )

        val = self.time_sped_gust_max
        if val is not None:
            cols.append("max_gust_ts")
            args.append(val)

        if not cols:
            return False
        cs = ", ".join([f"{c} = %s" for c in cols])
        slicer = slice(0, 4) if self.station[0] != "K" else slice(1, 4)
        args.extend([product_id, product_id, self.station[slicer], self.date])
        txn.execute(
            f"""
    UPDATE summary_{self.date:%Y} s SET {cs}
    , report = case when %s::text is null then report else
        coalesce(report || ' ', '') || %s::text end
    FROM stations t
    WHERE s.iemid = t.iemid and t.network ~* 'ASOS'
    and t.id = %s and s.day = %s""",
            args,
        )
        return txn.rowcount == 1


class DSMCollective(WMOProduct):
    """A collective representing a NOAAPort Text Product with many DSMs."""

    def __init__(
        self, text, utcnow=None, ugc_provider=None, nwsli_provider=None
    ):
        """constructor"""
        super().__init__(
            text,
            utcnow,
        )
        # appease linter and keep ABI
        self.ugc_provider = ugc_provider
        self.nwsli_provider = nwsli_provider
        # hold our parsing results
        self.data: list[DSMProduct] = []
        lines = self.text.replace("\r", "").split("\n")
        if len(lines[3]) < 10:
            meat = ("".join(lines[4:])).split("=")
        else:
            meat = ("".join(lines[3:])).split("=")
        for piece in meat:
            if piece == "":
                continue
            res = process(piece)
            if res is None:
                self.warnings.append(f"DSM RE Match Failure: '{piece}'")
                continue
            res.compute_times(utcnow if utcnow is not None else utc())
            self.data.append(res)

    def tzlocalize(self, tzprovider):
        """Localize our currently stored timestamps."""
        for dsm in self.data:
            tzinfo = tzprovider.get(dsm.station)
            if tzinfo is None:
                self.warnings.append(f"station {dsm.station} has no tzinfo")
                continue
            dsm.tzlocalize(tzinfo)

    def sql(self, txn) -> list[bool]:
        """Do databasing."""
        res = []
        for dsm in self.data:
            # Some magic is happening here to construct a product_id
            # that is unique for this DSM and based on the pyWWA splitting of
            # DSMs that is done
            product_id = (
                f"{self.wmo_valid:%Y%m%d%H%M}-{self.source}-{self.wmo}-"
                f"DSM{dsm.station[1:]}"
            )
            res.append(dsm.sql(txn, product_id))
        return res


def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    """Provide back DSM objects based on the parsing of this text"""
    return DSMCollective(text, utcnow, ugc_provider, nwsli_provider)
