"""WPC's XTEUS Nationwide High/Low."""
from datetime import datetime, timezone

import defusedxml.ElementTree as ET
import pandas as pd

from pyiem.nws.product import TextProduct
from pyiem.util import LOG

ISO = "%Y-%m-%dT%H:%M"


def _parse_xml(textprod: TextProduct) -> pd.DataFrame:
    """Turn this product into a dataframe."""
    pos = textprod.unixtext[:200].find("<dwml ")
    if pos < 0:
        raise ValueError("No <dwml text found in product.")
    root = ET.fromstring(textprod.unixtext[pos:].strip())
    rows = []
    timelayout = {}
    for layout in root.findall("data/time-layout"):
        key = layout.find("layout-key").text
        sts = datetime.strptime(layout.find("start-valid-time").text[:16], ISO)
        sts = sts.replace(tzinfo=timezone.utc)
        ets = datetime.strptime(layout.find("end-valid-time").text[:16], ISO)
        ets = ets.replace(tzinfo=timezone.utc)
        # Is it this easy?
        if sts.hour < 6:  # low
            computed_date = ets.date()
        else:
            computed_date = sts.date()
        timelayout[key] = {"date": computed_date, "sts": sts, "ets": ets}
    xref = {}
    suffix = "-"
    for location in root.findall("data/location"):
        key = location.find("location-key").text
        if key in xref:
            textprod.warnings.append(
                "Found duplicated location-key... attempting workaround."
            )
            key = f"{key}{suffix}"
            suffix += "-"
        xref[key] = {
            "state": location.find("city").attrib["state"][:2],
            "name": location.find("city").text,
        }

    used = []
    suffix = "-"
    for param in root.findall("data/parameters"):
        for child in param:
            key = param.attrib["applicable-location"]
            if key in used:
                textprod.warnings.append(
                    "Found uplicated applicable-location, working around."
                )
                key = f"{key}{suffix}"
                suffix += "-"
            used.append(key)
            tkey = child.attrib["time-layout"]
            rows.append(
                {
                    "sid": key.replace("~", ""),
                    "date": timelayout[tkey]["date"],
                    "sts": timelayout[tkey]["sts"],
                    "ets": timelayout[tkey]["ets"],
                    "type": child.attrib["type"],
                    "value": float(child.find("value").text),
                    "state": xref[key]["state"],
                    "name": xref[key]["name"],
                }
            )
    return pd.DataFrame(rows)


class XTEUSProduct(TextProduct):
    """A Special Weather Statement"""

    def __init__(
        self, text, utcnow=None, ugc_provider=None, nwsli_provider=None
    ):
        """constructor"""
        TextProduct.__init__(self, text, utcnow, ugc_provider, nwsli_provider)
        self.data = _parse_xml(self)

    def sql(self, cursor):
        """Do database insert logic."""
        # Check to see what we have for current entries
        product_id = self.get_product_id()
        types_to_take = []
        for (date, typ), _gdf in self.data.groupby(["date", "type"]):
            dbtype = "N" if typ.lower() == "minimum" else "X"
            cursor.execute(
                "SELECT product_id from wpc_national_high_low WHERE date = %s "
                "and n_x = %s",
                (
                    date,
                    dbtype,
                ),
            )
            if cursor.rowcount == 0:
                types_to_take.append(typ)
                continue
            dbprod = cursor.fetchone()["product_id"]
            if dbprod > product_id:
                LOG.warning("Database has newer %s [%s]", typ, dbprod)
                continue
            types_to_take.append(typ)
            cursor.execute(
                "DELETE from wpc_national_high_low where date = %s and "
                "n_x = %s",
                (date, dbtype),
            )

        for _, row in self.data.iterrows():
            if row["type"] not in types_to_take:
                LOG.warning("Skipping insert for %s", row["type"])
                continue
            cursor.execute(
                """
                INSERT into wpc_national_high_low(product_id, station, state,
                name, date, sts, ets, n_x, value) VALUES (%s, %s, %s, %s,
                %s, %s, %s, %s, %s)
                """,
                (
                    product_id,
                    row["sid"],
                    row["state"],
                    row["name"],
                    row["date"],
                    row["sts"],
                    row["ets"],
                    "N" if row["type"].lower() == "minimum" else "X",
                    row["value"],
                ),
            )


def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    """The XTEUS Parser"""
    return XTEUSProduct(
        text, utcnow, ugc_provider=ugc_provider, nwsli_provider=nwsli_provider
    )
