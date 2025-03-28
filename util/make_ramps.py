"""Serialization of geometries for use in pyIEM.plot mapping

We use a pickled protocol=2, which is compat binary.
"""

import pandas as pd

from pyiem.database import get_dbconnstr
from pyiem.util import logger

LOG = logger()
PATH = "../src/pyiem/data/ramps/"
# Be annoying
LOG.info("Be sure to run this against Mesonet database and not laptop!")


def do(ramp):
    """states."""
    df = pd.read_sql(
        "SELECT l.coloridx, l.value, l.r, l.g, l.b from iemrasters_lookup l "
        "JOIN iemrasters r ON (l.iemraster_id = r.id) WHERE r.name = %s and "
        "value is not null "
        "ORDER by coloridx ASC",
        get_dbconnstr("mesosite"),
        params=(ramp,),
        index_col="coloridx",
    )
    df.to_csv(f"{PATH}{ramp}.txt")


def main():
    """Go Main"""
    for table in ["composite_n0r", "composite_n0q"]:
        do(table)


if __name__ == "__main__":
    main()
