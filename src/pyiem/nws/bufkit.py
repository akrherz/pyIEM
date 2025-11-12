"""A BUFKIT File Reader."""

import re
from io import StringIO

import numpy as np
import pandas as pd

from pyiem.util import LOG

KEY_VAL_RE = re.compile(r"(?P<key>[A-Z0-9]{4}) = (?P<value>[0-9\-\./]+)")


def _read_station(text: str):
    """our station data reader."""
    # GEMPAK variables always start with letters
    keys = [t for t in text[:1000].split() if t[0].isalpha()]
    # Split on the last key above to get just numbers
    numbers = text.split(keys[-1])[1].split()
    if len(numbers) % len(keys) != 0:
        LOG.info(
            "BUFKIT reader found len(numbers)[%s] %% len(keys)[%s] != 0",
            len(numbers),
            len(keys),
        )
        # Likely a corrupted file, so an evasive hack
        meat = text.split(keys[-1])[1]
        pos = meat.find("STID")
        meat = meat[:pos]
        numbers = meat.strip().split()
    rows = [
        numbers[i : (i + len(keys))] for i in range(0, len(numbers), len(keys))
    ]
    df = pd.DataFrame(rows, columns=keys)
    df["utc_valid"] = pd.to_datetime(
        df["YYMMDD/HHMM"],
        format="%y%m%d/%H%M",
        utc=True,
    )
    return df.drop("YYMMDD/HHMM", axis=1).astype(float, False, "ignore")


def _read_sounding(text):
    """our sounding reader."""
    snparm = []
    stnprm = []
    # Figure out some headers by taking a sample
    for line in text[:1000].split("\n"):
        if not snparm and line.startswith("SNPARM"):
            snparm = line.split("=")[1].strip().split(";")
        elif not stnprm and line.startswith("STNPRM"):
            stnprm = line.split("=")[1].strip().split(";")
    rows = []
    stnrows = []
    # Split into sections, skipping the already parsed header
    sections = text.split("STID =")[1:]
    for section in sections:
        settings = dict(KEY_VAL_RE.findall(section))
        stnrows.append(settings)
        # split based on the last snparm
        numbers = section.split(snparm[-1])[-1].split()
        # should be a multiple of snparm
        if len(numbers) % len(snparm) != 0:
            LOG.info(
                "BUFKIT reader found len(numbers)[%s] %% len(snparm)[%s] != 0",
                len(numbers),
                len(snparm),
            )
            # Likely a corrupted file, just skip it
            continue
        for i in range(0, len(numbers), len(snparm)):
            rows.append([settings["STIM"], *numbers[i : (i + len(snparm))]])  # noqa
    cols = ["STIM", *snparm]
    stndf = pd.DataFrame(stnrows)
    stndf["utc_valid"] = pd.to_datetime(
        stndf["TIME"],
        format="%y%m%d/%H%M",
        utc=True,
    )
    stndf = stndf.drop("TIME", axis=1).astype(float, False, "ignore")
    sndf = pd.DataFrame(rows, columns=cols, dtype=float)
    sndf["STIM"] = sndf["STIM"].astype(int)
    return sndf, stndf


def read_bufkit(mixedobj):
    """Read a BUFKIT file and return two pandas dataframes.

    The first dataframe is the sounding values with a column called `STIM`,
    which can be joined against the index of the station_dataframe.

    Args:
      mixedobj (str or filelike): What to read.

    Returns:
      (profile_dataframe, station_dataframe)
    """
    if isinstance(mixedobj, str):
        with open(mixedobj, encoding="utf8") as fh:
            text = fh.read()
    elif isinstance(mixedobj, StringIO):
        text = mixedobj.getvalue()
    else:
        raise ValueError("Provided mixedobj should be str or StringIO")
    # Step 0 remove CR
    text = text.replace("\r", "")
    # Step 1 split the text into two sections
    pos = text.find("STN YYMMDD/HHMM")
    if pos == -1:
        raise ValueError("Failed to find station data delimiter")
    sounding_text = text[:pos]
    station_text = text[pos:]
    sndf, paramdf = _read_sounding(sounding_text)
    stndf = _read_station(station_text)
    # Join the paramdf into stndf
    stndf = pd.merge(
        stndf, paramdf, how="outer", left_on="utc_valid", right_on="utc_valid"
    ).set_index("STIM")
    # -9999 is missing
    stndf = stndf.replace({-9999: np.nan})
    sndf = sndf.replace({-9999: np.nan})
    return sndf, stndf
