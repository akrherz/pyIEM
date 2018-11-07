"""
 Supports parsing of Textual Model Output Statistics files
"""
import re
import datetime

import pytz
from pyiem.nws.product import TextProduct

LATLON = re.compile(r"LAT\.\.\.LON\s+((?:[0-9]{8}\s+)+)")
DISCUSSIONNUM = re.compile(
    r"MESOSCALE (?:PRECIPITATION )?DISCUSSION\s+([0-9]+)", re.IGNORECASE)
ATTN_WFO = re.compile(
    r"ATTN\.\.\.WFO\.\.\.([\.A-Z]*?)(?:LAT\.\.\.LON|ATTN\.\.\.RFC)")
ATTN_RFC = re.compile(r"ATTN\.\.\.RFC\.\.\.([\.A-Z]*)")
WATCH_PROB = re.compile(
    r"PROBABILITY OF WATCH ISSUANCE\s?\.\.\.\s?([0-9]+) PERCENT",
    re.IGNORECASE)


def section_parser(sect):
    """Parse this section of text"""
    metadata = re.findall((r"([A-Z0-9]{4})\s+(...) (...) GUIDANCE\s+"
                           r"([01]?[0-9])/([0-3][0-9])/([0-9]{4})\s+"
                           r"([0-2][0-9]00) UTC"), sect)
    (station, model, mos, month, day, year, hhmm) = metadata[0]
    if model == 'NBM':
        model = mos
    initts = datetime.datetime(int(year), int(month), int(day), int(hhmm[:2]))
    initts = initts.replace(tzinfo=pytz.utc)

    times = [initts, ]
    data = {}
    lines = sect.split("___")
    hrs = lines[2].split()
    for hr in hrs[1:]:
        if hr == "00":
            ts = times[-1] + datetime.timedelta(days=1)
            ts = ts.replace(hour=0)
        else:
            ts = times[-1].replace(hour=int(hr))
        times.append(ts)
        data[ts] = {}

    for line in lines[3:]:
        if len(line) < 10:
            continue
        vname = line[:3].replace("/", "_")
        if vname == "X_N":
            vname = "N_X"
        vals = re.findall("(...)", line[4:])
        for i, val in enumerate(vals):
            if vname == "T06" and times[i+1].hour in [0, 6, 12, 18]:
                data[times[i+1]]["T06_1"] = vals[i-1].replace("/", "").strip()
                data[times[i+1]]["T06_2"] = val.replace("/", "").strip()
            elif vname == "T06":
                pass
            elif vname == "T12" and times[i+1].hour in [0, 12]:
                data[times[i+1]]["T12_1"] = vals[i-1].replace("/", "").strip()
                data[times[i+1]]["T12_2"] = val.replace("/", "").strip()
            elif vname == "T12":
                pass
            elif vname == "WDR":
                data[times[i+1]][vname] = int(vals[i].strip()) * 10
            else:
                data[times[i+1]][vname] = val.strip()
    return dict(station=station, model=model, data=data, initts=initts)


def make_null(val):
    """Hmmm"""
    if val == "" or val is None:
        return None
    return val


class MOSProduct(TextProduct):
    """
    Represents a Model Output Statistics file
    """

    def __init__(self, text, utcnow=None, ugc_provider=None,
                 nwsli_provider=None):
        """constructor"""
        TextProduct.__init__(self, text, utcnow, ugc_provider,
                             nwsli_provider)
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
            for ts in sect['data']:
                if ts == sect['initts']:
                    continue
                # Account for 'empty' MOS products
                if not sect['data'][ts]:
                    continue
                fst = """
                INSERT into t%s (station, model, runtime, ftime,
                """ % (sect['initts'].year, )
                sst = "VALUES(%s,%s,%s,%s,"
                args = [sect['station'], sect['model'], sect['initts'], ts]
                for vname in sect['data'][ts].keys():
                    # variables we don't wish to database
                    if vname in ['FHR', ]:
                        continue
                    fst += " %s," % (vname, )
                    sst += "%s,"
                    args.append(make_null(sect['data'][ts][vname]))
                if len(args) == 4:
                    # No data was found
                    continue
                sql = fst[:-1] + ") " + sst[:-1] + ")"
                txn.execute(sql, args)
                inserts += 1
        return inserts

    def parse_data(self):
        """Parse out our data!"""
        raw = self.unixtext + "\n"
        raw = raw.replace("\n", "___").replace("\x1e", "")
        sections = re.findall(r"([A-Z0-9]{4}\s+... ... GUIDANCE .*?)______",
                              raw)
        self.data = list(map(section_parser, sections))
        if not sections:
            raise Exception("Failed to split MOS Product")


def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    ''' Helper function '''
    return MOSProduct(text, utcnow, ugc_provider, nwsli_provider)
