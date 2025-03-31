"""Process GHCNh data from NCEI."""

from collections import defaultdict
from collections.abc import Generator
from typing import Optional

from metpy.units import units

from pyiem.nws.products.metarcollect import normalize_temp
from pyiem.reference import TRACE_VALUE, VARIABLE_WIND_DIRECTION
from pyiem.util import c2f, utc

MB = units("millibar")
HG = units("inch_Hg")
MPS = units("meters / second")
KTS = units("knot")
MM = units("millimeter")
INCH = units("inch")
KM = units("kilometer")
MILE = units("mile")
M = units("meter")
FT = units("feet")

# For those we don't take verbatim
PRESWX_TO_METAR = {
    "FG:44": "FG",
    "FG:45": "FZFG",
    "FG:49": "FZFG",
    "RA:61": "-RA",
    "RA:63": "+RA",
    "RA:65": "+RA",
    "SHRA:81": "SHRA",
    "SHRA:82": "+SHRA",
    "SN:71": "-SN",
    "SN:75": "+SN",
    "SQ": "SQ",
    "TS:95": "+TSRA",
    "TS:97": "+TSRA",
}


def build_dialect(line: str) -> dict[str, int]:
    """Figure out how to map colnames to token indices we need."""
    colnames = line.strip().split("|")
    return {
        "year": colnames.index("Year"),
        "month": colnames.index("Month"),
        "day": colnames.index("Day"),
        "hour": colnames.index("Hour"),
        "minute": colnames.index("Minute"),
        "tmpc": colnames.index("temperature"),
        "dwpc": colnames.index("dew_point_temperature"),
        "mslp": colnames.index("sea_level_pressure"),  # hPa
        "drct": colnames.index("wind_direction"),
        "smps": colnames.index("wind_speed"),  # m/s
        "gmps": colnames.index("wind_gust"),  # m/s
        "p01m": colnames.index("precipitation"),  # mm
        "p03m": colnames.index("precipitation_3_hour"),  # mm
        "p06m": colnames.index("precipitation_6_hour"),  # mm
        "p24m": colnames.index("precipitation_24_hour"),  # mm
        # NCEI Calculated "relh": colnames.index("relative_humidity"),  # %
        "vsby_km": colnames.index("visibility"),  # km
        "alti_mb": colnames.index("altimeter"),  # hPa
        "pres_wx_mw1": colnames.index("pres_wx_MW1"),  # code
        "pres_wx_mw2": colnames.index("pres_wx_MW2"),  # code
        "pres_wx_mw3": colnames.index("pres_wx_MW3"),  # code
        "pres_wx_au1": colnames.index("pres_wx_AU1"),  # code
        "pres_wx_au2": colnames.index("pres_wx_AU2"),  # code
        "pres_wx_au3": colnames.index("pres_wx_AU3"),  # code
        "pres_wx_aw1": colnames.index("pres_wx_AW1"),  # code
        "pres_wx_aw2": colnames.index("pres_wx_AW2"),  # code
        "pres_wx_aw3": colnames.index("pres_wx_AW3"),  # code
        "skyc1": colnames.index("sky_cover_1"),  # octas
        "skyl1": colnames.index("sky_cover_baseht_1"),  # meters
        "skyc2": colnames.index("sky_cover_2"),  # octas
        "skyl2": colnames.index("sky_cover_baseht_2"),  # meters
        "skyc3": colnames.index("sky_cover_3"),  # octas
        "skyl3": colnames.index("sky_cover_baseht_3"),  # meters
        "remarks": colnames.index("remarks"),
    }


def parse_packet(tokens: list[str], startpos: int) -> Optional[float]:
    """Process the packet, attempting to not consume memory."""
    # The six values are value, measure, qc, report_type, source_code, station
    if tokens[startpos] in ["", "9999"]:
        return None
    # Presently, code 3 and 7 are erroneous, but uffties, this may be
    # dropping good data on the floor as well :(
    if tokens[startpos + 2] in ["3", "7"]:
        return None
    if tokens[startpos + 1] == "2-Trace":
        # This is a sentinel value for trace precipitation
        return TRACE_VALUE
    if tokens[startpos] == "VRB":
        # This is a sentinel value for variable wind direction
        return VARIABLE_WIND_DIRECTION
    return float(tokens[startpos])


def clean_metar(raw: str) -> str:
    """Clean up the METAR string."""
    return (
        raw.split(";")[0]
        .split("$")[0]
        .split("=")[0]
        .replace(" KT ", " ")
        .strip()
    )


def process_line(line: str, dialect: dict[str, int]) -> dict:
    """Process a line of the file."""
    tokens = line.strip().split("|")
    ob = defaultdict(lambda: None)
    ob["valid"] = utc(
        int(tokens[dialect["year"]]),
        int(tokens[dialect["month"]]),
        int(tokens[dialect["day"]]),
        int(tokens[dialect["hour"]]),
        int(tokens[dialect["minute"]]),
    )
    val = parse_packet(tokens, dialect["tmpc"])
    if val is not None:
        ob["tmpf"] = normalize_temp(c2f(val))
        # Require a temperature to proceed
        val = parse_packet(tokens, dialect["dwpc"])
        if val is not None:
            ob["dwpf"] = normalize_temp(c2f(val))

    val = parse_packet(tokens, dialect["alti_mb"])
    if val is not None:
        ob["alti"] = round((MB * val).to(HG).m, 2)

    # No unit conversion needed for these
    for col in ["mslp", "drct"]:
        val = parse_packet(tokens, dialect[col])
        if val is not None:
            ob[col] = val

    val = parse_packet(tokens, dialect["smps"])
    if val is not None:
        ob["sknt"] = normalize_temp((MPS * val).to(KTS).m)
        if ob["sknt"] == 0:
            ob["drct"] = 0

    val = parse_packet(tokens, dialect["gmps"])
    if val is not None:
        ob["gust"] = normalize_temp((MPS * val).to(KTS).m)

    val = parse_packet(tokens, dialect["vsby_km"])
    if val is not None and (0 <= val < 100):  # Arbitrary limit of 100km
        ob["vsby"] = (KM * val).to(MILE).m
        if ob["vsby"] > 2.9:
            ob["vsby"] = round(ob["vsby"], 0)

    val = parse_packet(tokens, dialect["p01m"])
    if val is not None:
        # Maintain the sentinel value
        if val == TRACE_VALUE:
            ob["phour"] = TRACE_VALUE
        else:
            ob["phour"] = round((MM * val).to(INCH).m, 2)

    for hr in [3, 6, 24]:
        val = parse_packet(tokens, dialect[f"p{hr:02.0f}m"])
        if val is not None:
            if val == TRACE_VALUE:
                ob[f"p{hr:02.0f}i"] = TRACE_VALUE
            else:
                ob[f"p{hr:02.0f}i"] = round((MM * val).to(INCH).m, 2)

    for i in range(1, 4):
        val = tokens[dialect[f"skyc{i}"]]
        if val not in [""] and val.find(":") > 0:
            ob[f"skyc{i}"] = val.split(":")[0]
        val = parse_packet(tokens, dialect[f"skyl{i}"])
        if val is not None:
            ob[f"skyl{i}"] = int((M * val).to(FT).m)

    remark = tokens[dialect["remarks"]]
    for prefix in ["METAR", "SPECI"]:
        if (pos := remark.find(prefix)) > -1:
            ob["raw"] = clean_metar(remark[pos + 5 :])
            break

    wxcodes = []
    for i in range(1, 4):
        for src in ["mw", "au", "aw"]:
            val = tokens[dialect[f"pres_wx_{src}{i}"]]
            if val not in ["", "00", "9999"]:
                code = PRESWX_TO_METAR.get(
                    val,
                    val.split(":")[0],
                )
                if code not in wxcodes:
                    wxcodes.append(code)
    if wxcodes:
        ob["wxcodes"] = wxcodes

    return ob


def process_file(filename: str) -> Generator[dict]:
    """Process the provided file."""
    with open(filename) as fh:  # skipcq
        for linenum, line in enumerate(fh):
            if linenum == 0:
                dialect = build_dialect(line)
                continue
            # Skip lines that are woefully short
            if len(line) < 10:
                continue
            yield process_line(line, dialect)
