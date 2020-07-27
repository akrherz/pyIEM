"""
http://www.unidata.ucar.edu/data/lightning/nldn.html
"""
from datetime import timezone, datetime, timedelta
import struct

import pandas as pd


class NLDNProduct:
    """Simple class representing obs found in a NLDNProduct."""

    def __init__(self):
        """Constructor."""
        self.header = ""
        self.df = None

    def sql(self, cursor):
        """Persist data to the database"""
        if self.df is None:
            return
        for _, row in self.df.iterrows():
            table = "nldn%s" % (row["valid"].strftime("%Y_%m"),)
            cursor.execute(
                f"INSERT into {table} (valid, geom, signal, multiplicity, "
                "axis, eccentricity, ellipse, chisqr) VALUES (%s, "
                "'SRID=4326;POINT(%s %s)', %s, %s, %s, %s, %s, %s)",
                (
                    row["valid"],
                    row["longitude"],
                    row["latitude"],
                    row["signal"],
                    row["multiplicity"],
                    row["axis"],
                    row["eccentricity"],
                    row["ellipse"],
                    row["chisqr"],
                ),
            )


def parser(buf):
    """NLDN (unencrypted product)"""

    np = NLDNProduct()
    _ = buf.read(4)  # NLDN
    records = struct.unpack(">i", buf.read(4))
    np.header = buf.read(records[0] * 28 - 8)  # SGDS SUNY@ALBANY Thu Sep  ...

    rows = []
    while True:
        chunk = buf.read(28)
        if not chunk:
            break
        (tsec, nsec, lat1000, lon1000) = struct.unpack(">4i", chunk[:16])
        secs = float(tsec) + (nsec / 1000000.0)
        ts = datetime(1970, 1, 1) + timedelta(seconds=secs)
        ts = ts.replace(tzinfo=timezone.utc)
        (_, sgnl10, _) = struct.unpack(">3h", chunk[16:22])
        (multi, _, axis, eccentricity, ellipse, chisqr) = struct.unpack(
            "6b", chunk[22:28]
        )
        rows.append(
            dict(
                valid=ts,
                latitude=lat1000 / 1000.0,
                longitude=lon1000 / 1000.0,
                signal=sgnl10 / 10.0,
                multiplicity=multi,
                axis=axis,
                eccentricity=eccentricity,
                ellipse=ellipse,
                chisqr=chisqr,
            )
        )
    if rows:
        np.df = pd.DataFrame(rows)
    return np
