"""METAR formatting utilities."""

from datetime import timezone
from typing import Optional

import numpy as np
from metpy.units import units

from pyiem.reference import VARIABLE_WIND_DIRECTION


def metar_from_dict(ob: dict) -> str:
    """Format a METAR from a dictionary like pyiem.Observation."""
    tokens = [
        f"METAR {ob['station']}",
        f"{ob['valid'].astimezone(timezone.utc):%d%H%M}Z AUTO",
        metar_format_wind(ob["drct"], ob["sknt"], ob["gust"]),
        metar_format_visibility(ob["vsby"]),
        metar_format_weather(ob["wxcodes"]),
        metar_format_sky(ob),
        metar_format_temperature(ob["tmpf"], ob["dwpf"]),
        metar_format_altimeter(ob["alti"]),
        "RMK AO2",
        metar_format_mslp(ob["mslp"]),
        metar_format_pgroup(ob["phour"], 1),
        metar_format_pgroup(ob["p03i"], 3),
        metar_format_pgroup(ob["p06i"], 6),
        metar_format_pgroup(ob["p24i"], 24),
        metar_format_temperature(ob["tmpf"], ob["dwpf"], tgroup=True),
    ]
    # Remove None values
    tokens = [t for t in tokens if t is not None]
    return " ".join(tokens)


def metar_format_altimeter(alti: Optional[float]) -> Optional[str]:
    """Format the altimeter."""
    if alti is None:
        return None
    return f"A{alti * 100.0:.0f}"


def metar_format_mslp(mslp: Optional[float]) -> Optional[str]:
    """Format the SLP value."""
    if mslp is None:
        return None
    if mslp >= 1000:
        return f"SLP{(mslp * 10.0) - 10_000:03.0f}"
    return f"SLP{(mslp * 10.0) - 9_000:03.0f}"


def metar_format_pgroup(
    phour: Optional[float], hours: Optional[int] = 1
) -> Optional[str]:
    """Format the precipitation group."""
    if phour is None or phour <= 0:
        return None
    prefix = "P" if hours == 1 else "6"
    if hours == 24:
        prefix = "7"
    if phour < 0.005:
        return f"{prefix}0000"
    return f"{prefix}{phour * 100.0:04.0f}"


def metar_format_sky(ob: dict) -> Optional[str]:
    """Format the sky conditions.

    Args:
        ob (dict): Containing skyc{1,2,3,4} and skyl{1,2,3,4} keys
    """
    res = []
    for i in range(1, 5):
        skyc = ob.get(f"skyc{i}")
        skyl = ob.get(f"skyl{i}")
        if skyc is None:
            continue
        if skyc == "CLR":
            res.append("CLR")
        elif skyl is not None:
            skyl = int(np.round(skyl, 0))
            res.append(f"{skyc}{(skyl / 100.0):03.0f}")
    if not res:
        return None
    return " ".join(res)


def metar_format_temperature(
    tmpf: Optional[float], dwpf: Optional[float], tgroup: bool = False
) -> Optional[str]:
    """Format the temperature."""
    # Understanding is that temperature is required
    if tmpf is None:
        return None
    tmpc = (units.degF * tmpf).to(units.degC).m
    df = "M" if tmpc < 0 else ""
    tf = "1" if tmpc < 0 else "0"
    metarmsg = f"{df}{abs(tmpc):02.0f}/"
    tmsg = f"T{tf}{abs(tmpc) * 10.0:03.0f}"
    if dwpf is not None:
        dwpc = (units.degF * dwpf).to(units.degC).m
        df = "M" if dwpc < 0 else ""
        tf = "1" if dwpc < 0 else "0"
        metarmsg += f"{df}{abs(dwpc):02.0f}"
        tmsg += f"{tf}{abs(dwpc) * 10.0:03.0f}"
    return tmsg if tgroup else metarmsg


def metar_format_visibility(vsby: Optional[float]) -> Optional[str]:
    """Format the visibility."""
    if vsby is None:
        return None
    res = ""
    if vsby == 0:
        res = "0"
    elif vsby < 0.07:
        res = "1/16"  # Check this for M1/16
    elif vsby < 0.13:
        res = "1/8"
    elif vsby < 0.26:
        res = "1/4"
    elif vsby < 0.38:
        res = "3/8"
    elif vsby < 0.51:
        res = "1/2"
    elif vsby < 1.1:
        res = "1"
    elif vsby < 1.6:
        res = "1 1/2"
    elif vsby < 2.1:
        res = "2"
    elif vsby < 2.6:
        res = "2 1/2"
    else:
        res = f"{vsby:.0f}"
    return f"{res}SM"


def metar_format_weather(wxcodes: Optional[list]) -> Optional[str]:
    """Format the present weather strings."""
    if wxcodes is None or not wxcodes:
        return None
    return " ".join(wxcodes)


def metar_format_wind(
    drct: Optional[float], sknt: Optional[float], gust: Optional[float]
) -> str:
    """Format the wind speed and direction."""
    res = ""
    # Wind Direction
    if drct is None:
        res += "///"
    elif drct == VARIABLE_WIND_DIRECTION:
        res += "VRB"
    else:
        res += f"{drct:03.0f}"
    if sknt is None:
        res += "//KT"
    else:
        res += f"{sknt:02.0f}"
        if gust is not None:
            res += f"G{gust:02.0f}"
        res += "KT"
    return res
