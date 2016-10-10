"""NWS Hydrological Markup Language

Attempt to break up the HML product into atomic data

"""
import pyiem.nws.product as product
import re
import datetime
import pytz
import pandas as pd
import xml.etree.cElementTree as ET
DELIMITER = """\<\?xml version="1.0" standalone="yes"\?\>"""


def no999(val):
    if val is None or val == -999 or val == -9999:
        return None
    return val


def parseUTC(s):
    """Parse an ISO-ish string into UTC timestamp"""
    if s is None:
        return None
    return datetime.datetime.strptime(s[:19],
                                      "%Y-%m-%dT%H:%M:%S").replace(
                                          tzinfo=pytz.timezone("UTC"))


def parse_xml(token):
    """Attempt to parse the XML into something useful"""
    root = ET.fromstring(token)
    hml = HMLData()
    hml.station = root.attrib['id']
    hml.stationname = root.attrib.get('name')
    hml.originator = root.attrib.get('originator')
    hml.generationtime = parseUTC(root.attrib['generationtime'])
    for child in root:
        if child.tag not in ['observed', 'forecast']:
            continue
        rows = []
        for datum in child.findall("datum"):
            secondary = datum.find('secondary')
            rows.append(dict(name=child.tag,
                             valid=parseUTC(datum.find('valid').text),
                             primary=datum.find('primary').text,
                             secondary=(secondary.text
                                        if secondary is not None
                                        else None)))
        mydict = hml.data[child.tag]
        df = pd.DataFrame(rows)
        df['primary'] = pd.to_numeric(df['primary'], errors='coerse')
        df['secondary'] = pd.to_numeric(df['secondary'], errors='coerse')
        mydict['dataframe'] = df
        mydict['issued'] = parseUTC(child.attrib.get('issued'))
        for attr in ['primaryName', 'secondaryName',
                     'primaryUnits', 'secondaryUnits']:
            mydict[attr] = child.attrib.get(attr)
    return hml


class HMLData(object):

    def __init__(self):
        self.station = None
        self.stationname = None
        self.originator = None
        self.generationtime = None
        self.data = {'observed': dict(dataframe=None,
                                      primaryUnits=None,
                                      issued=None,
                                      secondaryUnits=None,
                                      primaryName=None,
                                      secondaryName=None),
                     'forecast': dict(dataframe=None,
                                      primaryUnits=None,
                                      issued=None,
                                      secondaryUnits=None,
                                      primaryName=None,
                                      secondaryName=None)}


class HML(product.TextProduct):
    ''' Class for parsing and representing Space Wx Products '''

    def __init__(self, text, utcnow=None, ugc_provider=None,
                 nwsli_provider=None):
        ''' constructor '''
        product.TextProduct.__init__(self, text, utcnow=utcnow,
                                     ugc_provider=ugc_provider,
                                     nwsli_provider=nwsli_provider)
        self.data = []
        self.parsing()

    def do_sql_observed(self, cursor, _hml):
        """Process the observed portion of the dataset"""
        fx = _hml.data['observed']
        if fx['dataframe'] is None:
            return
        df = fx['dataframe']
        if len(df.index) == 0:
            return
        minvalid = df['valid'].min()
        maxvalid = df['valid'].max()
        for col in ['primary', 'secondary']:
            if fx[col+'Name'] is None:
                continue
            key = "%s[%s]" % (fx[col+'Name'], fx[col+'Units'])
            cursor.execute("""DELETE from hml_observed_data WHERE
            station = %s and valid >= %s and valid <= %s and
            key = get_hml_observed_key(%s)
            """, (_hml.station, minvalid, maxvalid, key))
            for _, row in df.iterrows():
                val = no999(row[col])
                if val is None:
                    continue
                y = "%s" % (row['valid'].year,)
                cursor.execute("""
                    INSERT into hml_observed_data_""" + y + """
                    (station, valid, key, value)
                    VALUES (%s, %s, get_hml_observed_key(%s), %s)
                    """, (_hml.station, row['valid'], key, val))

    def do_sql_forecast(self, cursor, _hml):
        """Process the forecast portion of the dataset"""
        fx = _hml.data['forecast']
        df = fx['dataframe']
        if df is None:
            return
        if len(df.index) == 0:
            return
        # Get an id
        cursor.execute("""
        INSERT into hml_forecast(station, generationtime, originator,
        product_id, primaryname, secondaryname, primaryunits,
        secondaryunits, issued, forecast_sts, forecast_ets)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """, (_hml.station, _hml.generationtime,
              _hml.originator, self.get_product_id(),
              fx['primaryName'], fx['secondaryName'],
              fx['primaryUnits'], fx['secondaryUnits'],
              fx['issued'], df['valid'].min(), df['valid'].max()))
        fid = cursor.fetchone()[0]
        # Table partitioning is done by issued time
        table = "hml_forecast_data_%s" % (fx['issued'].year,)
        for _, row in fx['dataframe'].iterrows():
            cursor.execute("""
                INSERT into """ + table + """
                (hml_forecast_id, valid, primary_value,
                secondary_value) VALUES
                (%s, %s, %s, %s)
                """, (fid, row['valid'], no999(row['primary']),
                      no999(row['secondary'])))

    def sql(self, cursor):
        """Persist this information to the database"""
        for _hml in self.data:
            self.do_sql_forecast(cursor, _hml)
            self.do_sql_observed(cursor, _hml)

    def parsing(self):
        """Attempt to parse out what we have found"""
        tokens = re.split(DELIMITER, self.unixtext)
        for token in tokens:
            if token.find("</site>") == -1:
                continue
            content = token.strip()
            try:
                self.data.append(parse_xml(content))
            except Exception as exp:
                self.warnings.append(("Parsing %s resulted in %s\n%s"
                                      ) % (self.get_product_id(), exp,
                                           content))

    def __str__(self):
        """string representation"""
        s = "HML %s\n" % (self.get_product_id(),)
        for _hml in self.data:
            s += "  + SID: %s generationTime: %s\n" % (_hml.station,
                                                       _hml.generationtime)
        return s


def parser(buf, utcnow=None, ugc_provider=None, nwsli_provider=None):
    """Parse a HML NOAAPort product

    This may have multiple xml documents inside.

    Args:
      buf (str): What we want to parse
    """
    return HML(buf, utcnow, ugc_provider, nwsli_provider)
