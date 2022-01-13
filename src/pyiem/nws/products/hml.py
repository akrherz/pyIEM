"""NWS Hydrological Markup Language

Attempt to break up the HML product into atomic data

"""
import re
from datetime import timezone, datetime
import xml.etree.cElementTree as ET

import pandas as pd
import pyiem.nws.product as product
from pyiem.util import LOG

DELIMITER = r"""\<\?xml version="1.0" standalone="yes"\?\>"""


def no999(val):
    """No negative -999 or -9999 please."""
    if val is None or val == "-999" or val == "-9999":
        return None
    return val


def parseUTC(s):
    """Parse an ISO-ish string into UTC timestamp"""
    if s is None:
        return None
    return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").replace(
        tzinfo=timezone.utc
    )


def parse_xml(token):
    """Attempt to parse the XML into something useful"""
    root = ET.fromstring(token)
    hml = HMLData()
    hml.station = root.attrib["id"]
    hml.stationname = root.attrib.get("name")
    hml.originator = root.attrib.get("originator")
    hml.generationtime = parseUTC(root.attrib["generationtime"])
    for child in root:
        if child.tag not in ["observed", "forecast"]:
            continue
        rows = []
        for datum in child.findall("datum"):
            secondary = datum.find("secondary")
            rows.append(
                dict(
                    name=child.tag,
                    valid=parseUTC(datum.find("valid").text),
                    primary=no999(datum.find("primary").text),
                    secondary=(
                        no999(secondary.text)
                        if secondary is not None
                        else None
                    ),
                )
            )
        mydict = hml.data[child.tag]
        df = pd.DataFrame(rows)
        df["primary"] = pd.to_numeric(df["primary"], errors="coerce")
        df["secondary"] = pd.to_numeric(df["secondary"], errors="coerce")
        mydict["dataframe"] = df
        mydict["issued"] = parseUTC(child.attrib.get("issued"))
        for attr in [
            "primaryName",
            "secondaryName",
            "primaryUnits",
            "secondaryUnits",
        ]:
            mydict[attr] = child.attrib.get(attr)
    return hml


class HMLData:
    """Our data object."""

    def __init__(self):
        """Constructor."""
        self.station = None
        self.stationname = None
        self.originator = None
        self.generationtime = None
        self.data = {
            "observed": dict(
                dataframe=None,
                primaryUnits=None,
                issued=None,
                secondaryUnits=None,
                primaryName=None,
                secondaryName=None,
            ),
            "forecast": dict(
                dataframe=None,
                primaryUnits=None,
                issued=None,
                secondaryUnits=None,
                primaryName=None,
                secondaryName=None,
            ),
        }


class HML(product.TextProduct):
    """Class for parsing and representing Space Wx Products"""

    def __init__(
        self, text, utcnow=None, ugc_provider=None, nwsli_provider=None
    ):
        """constructor"""
        product.TextProduct.__init__(
            self,
            text,
            utcnow=utcnow,
            ugc_provider=ugc_provider,
            nwsli_provider=nwsli_provider,
        )
        self.data = []
        self.parsing()

    def do_sql_observed(self, cursor, _hml):
        """Process the observed portion of the dataset"""
        ob = _hml.data["observed"]
        if ob["dataframe"] is None:
            return
        df = ob["dataframe"]
        if df.empty:
            return
        for col in ["primary", "secondary"]:
            if ob[col + "Name"] is None:
                continue
            key = "%s[%s]" % (ob[col + "Name"], ob[col + "Units"])
            # Check that we have some non-null data
            df2 = df[pd.notnull(df[col])]
            if df2.empty:
                continue
            minvalid = df2["valid"].min()
            maxvalid = df2["valid"].max()
            cursor.execute(
                """
                DELETE from hml_observed_data WHERE
                station = %s and valid >= %s and valid <= %s and
                key = get_hml_observed_key(%s)
            """,
                (_hml.station, minvalid, maxvalid, key),
            )
            for _, row in df2.iterrows():
                val = row[col]
                if val is None:
                    continue
                cursor.execute(
                    (
                        "INSERT into hml_observed_data "
                        "(station, valid, key, value) "
                        "VALUES (%s, %s, get_hml_observed_key(%s), %s) "
                        "RETURNING key"
                    ),
                    (_hml.station, row["valid"], key, val),
                )
                if cursor.fetchone()[0] is not None:
                    continue
                # Delete the bad row
                cursor.execute(
                    "DELETE from hml_observed_data WHERE station = %s and "
                    "valid = %s and key is null",
                    (_hml.station, row["valid"]),
                )
                # Need to create a new unit!
                cursor.execute(
                    "INSERT into hml_observed_keys(id, label) VALUES ("
                    "(SELECT coalesce(max(id) + 1, 0) from hml_observed_keys),"
                    "%s) RETURNING id",
                    (key,),
                )
                LOG.warning("Created key %s for %s", cursor.fetchone()[0], key)

    def do_sql_forecast(self, cursor, _hml):
        """Process the forecast portion of the dataset"""
        fx = _hml.data["forecast"]
        df = fx["dataframe"]
        if df is None:
            return
        if df.empty:
            return
        # Get an id
        cursor.execute(
            """
        INSERT into hml_forecast(station, generationtime, originator,
        product_id, primaryname, secondaryname, primaryunits,
        secondaryunits, issued, forecast_sts, forecast_ets)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
            (
                _hml.station,
                _hml.generationtime,
                _hml.originator,
                self.get_product_id(),
                fx["primaryName"],
                fx["secondaryName"],
                fx["primaryUnits"],
                fx["secondaryUnits"],
                fx["issued"],
                df["valid"].min(),
                df["valid"].max(),
            ),
        )
        fid = cursor.fetchone()[0]
        # Table partitioning is done by issued time
        table = "hml_forecast_data_%s" % (fx["issued"].year,)
        for _, row in fx["dataframe"].iterrows():
            cursor.execute(
                f"INSERT into {table} (hml_forecast_id, valid, primary_value, "
                "secondary_value) VALUES (%s, %s, %s, %s)",
                (fid, row["valid"], row["primary"], row["secondary"]),
            )

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
                self.warnings.append(
                    ("Parsing %s resulted in %s\n%s")
                    % (self.get_product_id(), exp, content)
                )

    def __str__(self):
        """string representation"""
        s = "HML %s\n" % (self.get_product_id(),)
        for _hml in self.data:
            s += "  + SID: %s generationTime: %s\n" % (
                _hml.station,
                _hml.generationtime,
            )
        return s


def parser(buf, utcnow=None, ugc_provider=None, nwsli_provider=None):
    """Parse a HML NOAAPort product

    This may have multiple xml documents inside.

    Args:
      buf (str): What we want to parse
    """
    return HML(buf, utcnow, ugc_provider, nwsli_provider)
