"""
 Supports parsing of Textual Model Output Statistics files
"""
import re
import datetime

from pyiem.util import utc
from pyiem.nws.product import TextProduct

REMAP_VARS = {"X_N": "N_X", "WND": "WSP", "WGS": "GST"}


def section_parser(sect):
    """Parse this section of text"""
    metadata = re.findall(
        (
            r"([A-Z0-9_]{3,10})\s+(....?) (V[0-9]\.[0-9] )?(....?) GUIDANCE\s+"
            r"([01]?[0-9])/([0-3][0-9])/([0-9]{4})\s+"
            r"([0-2][0-9][0-6][0-9]) UTC"
        ),
        sect,
    )
    (station, model, _bogus, mos, month, day, year, hhmm) = metadata[0]
    if model == "NBM":
        model = mos
        if mos == "NBX":
            model = "NBE"
    if mos == "LAMP":
        model = "LAV"
    if model == "GFSX":
        model = "MEX"
    # We drop the minutes for the LAV, which has :30 after for some reason?
    initts = utc(int(year), int(month), int(day), int(hhmm[:2]))

    times = [initts]
    data = {}
    lines = sect.split(";;;")
    hrline = 2
    if model in ["MEX", "LAV"]:
        hrline = 1
    elif model in ["NBE", "NBS"]:
        hrline = 3
    hrs = lines[hrline].replace("|", " ").split()
    if hrs[0] == "DT":  # Hack
        hrs = lines[2].split()
    for i, hr in enumerate(hrs[1:]):
        if model == "LAV" and hrs[0] == "HR":
            ts = initts + datetime.timedelta(hours=int(hr))
        elif model == "LAV":
            ts = initts + datetime.timedelta(hours=(i + 1))
            assert ts.hour == int(hr)
        elif model in ["MEX", "NBE", "NBS"]:
            ts = initts + datetime.timedelta(hours=int(hr))
        elif hr == "00":
            ts = times[-1] + datetime.timedelta(days=1)
            ts = ts.replace(hour=0)
        else:
            ts = times[-1].replace(hour=int(hr))
        times.append(ts)
        data[ts] = {}
    # Double check
    for ts in data:
        if ts < initts:
            raise AssertionError(f"Computed ts of {ts} < initts {initts}")

    chars = "(...)" if model not in ["MEX", "NBE"] else "(....)"
    startline = 2 if model in ["LAV"] else 3
    startlinepos = 4 if model not in ["NBE"] else 5
    if mos == "NBX" or model == "MEX":
        startlinepos = 3
    for line in lines[startline:]:
        if len(line) < 20:
            continue
        line = line.replace("|", " ")
        vname = line[:3].replace("/", "_").strip()
        vals = re.findall(chars, line[startlinepos:])
        for i, val in enumerate(vals):
            # Some products have more data than columns :(
            if i >= len(data):
                continue
            if vname == "T06" and times[i + 1].hour in [0, 6, 12, 18]:
                data[times[i + 1]]["T06_1"] = (
                    vals[i - 1].replace("/", "").strip()
                )
                data[times[i + 1]]["T06_2"] = val.replace("/", "").strip()
            elif vname == "T06":
                pass
            elif vname == "T12" and times[i + 1].hour in [0, 12]:
                data[times[i + 1]]["T12_1"] = (
                    vals[i - 1].replace("/", "").strip()
                )
                data[times[i + 1]]["T12_2"] = val.replace("/", "").strip()
            elif vname == "T12":
                pass
            elif vname == "WDR" and vals[i].strip() != "":
                data[times[i + 1]][vname] = int(vals[i].strip()) * 10
            else:
                data[times[i + 1]][vname] = val.strip()
    return dict(station=station, model=model, data=data, initts=initts)


def make_null(val):
    """Hmmm, perhaps we should set 999 as null too?"""
    if val in ["", "NG"] or val is None:
        return None
    return val


class MOSProduct(TextProduct):
    """
    Represents a Model Output Statistics file
    """

    def __init__(
        self, text, utcnow=None, ugc_provider=None, nwsli_provider=None
    ):
        """constructor"""
        TextProduct.__init__(self, text, utcnow, ugc_provider, nwsli_provider)
        self.data = []
        self.parse_data()

    def sql(self, txn):
        """Persist our data to the database

        Args:
          txn: Database cursor

        Returns:
          int number of inserts made to the database
        """
        inserts = 0
        for sect in self.data:
            for ts in sect["data"]:
                # Account for 'empty' MOS products
                if not sect["data"][ts]:
                    continue
                fst = (
                    f"INSERT into t{sect['initts'].year} "
                    "(station, model, runtime, ftime, "
                )
                sst = "VALUES(%s,%s,%s,%s,"
                args = [sect["station"], sect["model"], sect["initts"], ts]
                for vname in sect["data"][ts].keys():
                    # variables we don't wish to database
                    if vname in ["FHR", "HR", "UTC"]:
                        continue
                    # save some database space :/
                    fst += f" {REMAP_VARS.get(vname, vname)},"
                    sst += "%s,"
                    args.append(make_null(sect["data"][ts][vname]))
                if len(args) == 4:
                    # No data was found
                    continue
                sql = fst[:-1] + ") " + sst[:-1] + ")"
                txn.execute(sql, args)
                inserts += 1
        return inserts

    def parse_data(self):
        """Parse out our data!"""
        # Whitespace trim
        raw = "\n".join([s.strip() for s in self.unixtext.split("\n")])
        raw = raw + "\n"
        raw = raw.replace("\n", ";;;").replace("\x1e", "")
        sections = re.findall(
            r"([A-Z0-9_]{3,10}\s+....? V?[0-9]?\.?[0-9]? ?"
            r"....? GUIDANCE .*?);;;;;;",
            raw,
        )
        self.data = list(map(section_parser, sections))
        if not sections:
            raise Exception("Failed to split MOS Product")


def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    """Helper function"""
    return MOSProduct(text, utcnow, ugc_provider, nwsli_provider)
