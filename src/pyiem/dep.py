"""Utilities for the Daily Erosion Project"""
import datetime
import re

import pandas as pd
from pandas import read_sql
import numpy as np
from scipy.interpolate import interp1d
from pyiem.util import get_dbconnstr

# The bounds of the climate files we store on disk and processing
# SOUTH is approx OKC and EAST is approx NYC
SOUTH = 35.0
WEST = -104.0
NORTH = 49.0
EAST = -74.0

YLD_CROPTYPE = re.compile(r"Crop Type #\s+(?P<num>\d+)\s+is (?P<name>[^\s]+)")
YLD_DATA = re.compile(
    (
        r"Crop Type #\s+(?P<num>\d+)\s+Date = (?P<doy>\d+)"
        r" OFE #\s+(?P<ofe>\d+)\s+yield=\s+(?P<yield>[0-9\.]+)"
        r" \(kg/m\*\*2\) year= (?P<year>\d+)"
    )
)
# 9 values for 8 colors on the website
# NB: Keep the lowest value just above zero so that plots always show data
RAMPS = {
    "english": [
        [0.01, 0.1, 0.25, 0.5, 0.75, 1.0, 2.0, 3.0, 5.0],
        [0.01, 0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 20.0],
        [0.01, 1.0, 2.0, 5.0, 7.0, 10.0, 20.0, 30.0, 40.0],
    ],
    "metric": [
        [0.25, 1.0, 10.0, 15.0, 25.0, 35.0, 50.0, 100.0, 200.0],
        [0.25, 2.0, 20.0, 30.0, 50.0, 70.0, 100.0, 200.0, 400.0],
        [0.25, 25.0, 50.0, 125.0, 200.0, 300.0, 500.0, 750.0, 1000.0],
    ],
}


def load_scenarios():
    """Build a dataframe of DEP scenarios."""
    df = read_sql(
        "SELECT * from scenarios ORDER by id ASC",
        get_dbconnstr("idep"),
        index_col="id",
    )
    return df


def get_cli_fname(lon, lat, scenario=0):
    """Get the climate file name for the given lon, lat, and scenario"""
    # The trouble here is relying on rounding is problematic, so we just
    # truncate
    lon = round(lon, 2)
    lat = round(lat, 2)
    return "/i/%s/cli/%03ix%03i/%06.2fx%06.2f.cli" % (
        scenario,
        0 - lon,
        lat,
        0 - lon,
        lat,
    )


def read_yld(filename):
    """read WEPP yld file with some local mods to include a year

    Args:
      filename (str): Filename to read

    Returns:
      pandas.DataFrame
    """
    data = open(filename, encoding="utf8").read()
    xref = {}
    for (cropcode, label) in YLD_CROPTYPE.findall(data):
        xref[cropcode] = label
    rows = []
    for (cropcode, doy, ofe, yld, year) in YLD_DATA.findall(data):
        date = datetime.date(int(year), 1, 1) + datetime.timedelta(
            days=(int(doy) - 1)
        )
        rows.append(
            dict(
                valid=date,
                year=int(year),
                yield_kgm2=float(yld),
                crop=xref[cropcode],
                ofe=int(ofe),
            )
        )
    return pd.DataFrame(rows)


def read_slp(filename):
    """read WEPP slp file.

    Args:
      filename (str): Filename to read

    Returns:
      list of slope profiles
    """
    lines = [a[: a.find("#")].strip() for a in open(filename, encoding="utf8")]
    segments = int(lines[5])
    res = [None] * segments
    xpos = 0
    elev = 0
    for seg in range(segments):
        # first line is pts and x-length
        (_pts, length) = [float(x) for x in lines[7 + seg * 2].split()]
        # next line is the combo of x-position along length and slope at pt
        line2 = lines[8 + seg * 2].replace(",", "")
        tokens = np.array([float(x) for x in line2.split()])
        # first value in each pair is the x-pos relative to the length
        xs = xpos + tokens[::2] * length
        # second value is the slope at that position?
        slopes = tokens[1::2]
        # initialize the y-position at the current elevation
        ys = [elev]
        for i in range(1, len(slopes)):
            # dx * slope
            elev -= (xs[i] - xs[i - 1]) * slopes[i - 1]
            ys.append(elev)
        res[seg] = {"x": xs, "slopes": slopes, "y": np.array(ys)}
        xpos += length
    return res


def man2df(mandict: dict, year1: int = 1) -> pd.DataFrame:
    """Convert nasty dictionary returned from `read_man` into `pd.DataFrame`.

    The DataFrame is oriented with OFE, year.

    Args:
      mandict (dict): Dictionary populated from read_man.
      year1 (int,optional): What does WEPP year index 1 equate to in the
        real world!  The default of 1 just uses what WEPP does.

    Returns:
      pd.DataFrame
    """
    rows = []
    baseyear = year1  # roundabout
    for iofe in range(mandict["iofe"]):
        for iyear in range(mandict["inyr"]):
            year = iyear + baseyear
            scenyr = mandict["rotations"][iyear][iofe]["yearindex"]
            ncrop = mandict["scens"][scenyr - 1]["ntype"]
            tilseq = mandict["scens"][scenyr - 1]["tilseq"]
            plant_date = None
            for surfeff in mandict["surfeffects"][tilseq - 1]["tills"]:
                op = surfeff["op"]
                if (
                    mandict["operations"][op - 1]["scecomment"].find("Planter")
                    > -1
                ):
                    doy = surfeff["mdate"]
                    plant_date = datetime.date(
                        year, 1, 1
                    ) + datetime.timedelta(days=(doy - 1))
            rows.append(
                {
                    "year": year,
                    "ofe": iofe + 1,
                    "plant_date": plant_date,
                    "crop_name": mandict["crops"][ncrop - 1]["crpnam"],
                }
            )
    return pd.DataFrame(rows)


def read_man(filename):
    """Implements WEPP's INFILE.for for reading management file

    Args:
      filename (str): Filename to read

    Returns:
      dict of management info
    """
    res = {}
    # Step one make a array of any data
    lines = [a[: a.find("#")].strip() for a in open(filename)]
    res["manver"] = lines[0]
    res["iofe"] = int(lines[6])
    res["inyr"] = int(lines[7])
    res["ncrop"] = int(lines[13])
    res["crops"] = [None] * res["ncrop"]
    linenum = 16
    for ncrop in range(res["ncrop"]):
        res["crops"][ncrop] = {
            "crpnam": lines[linenum],
            "crpcomment": "\n".join(lines[linenum + 1 : linenum + 4]),
            "iplant": int(lines[linenum + 4]),
        }
        linenum += 5
        if res["crops"][ncrop]["iplant"] == 1:
            # TODO
            linenum += 7
    linenum += 4
    res["nop"] = int(lines[linenum])
    linenum += 3
    res["operations"] = [None] * res["nop"]
    for nop in range(res["nop"]):
        res["operations"][nop] = {
            "scenam": lines[linenum],
            "scecomment": "\n".join(lines[linenum + 1 : linenum + 4]),
            "iplant": int(lines[linenum + 4]),
        }
        linenum += 9
    linenum += 6
    res["nini"] = int(lines[linenum])
    res["ini"] = [None] * res["nini"]
    linenum += 3
    for ini in range(res["nini"]):
        res["ini"][ini] = {
            "scenam": lines[linenum],
            "scecomment": "\n".join(lines[linenum + 1 : linenum + 4]),
            "iplant": int(lines[linenum + 4]),
        }
        linenum += 14
    linenum += 6

    res["nsurf"] = int(lines[linenum])
    res["surfeffects"] = [None] * res["nsurf"]
    linenum += 6
    for surf in range(res["nsurf"]):
        res["surfeffects"][surf] = {
            "scenam": lines[linenum],
            "scecomment": "\n".join(lines[linenum + 1 : linenum + 4]),
            "iplant": int(lines[linenum + 4]),
            "ntill": int(lines[linenum + 5]),
        }
        res["surfeffects"][surf]["tills"] = [None] * res["surfeffects"][surf][
            "ntill"
        ]
        linenum += 6
        for till in range(res["surfeffects"][surf]["ntill"]):
            res["surfeffects"][surf]["tills"][till] = {
                "mdate": int(lines[linenum]),
                "op": int(lines[linenum + 1]),
                "depth": float(lines[linenum + 2]),
                "type": int(lines[linenum + 3]),
            }
            linenum += 4
        linenum += 4
    linenum += 2
    res["ncnt"] = int(lines[linenum])
    linenum += 7
    res["ndrain"] = int(lines[linenum])
    linenum += 7
    res["nmscen"] = int(lines[linenum])
    linenum += 4
    res["scens"] = [None] * res["nmscen"]
    for scen in range(res["nmscen"]):
        res["scens"][scen] = {
            "scenam": lines[linenum],
            "scecomment": "\n".join(lines[linenum + 1 : linenum + 4]),
            "iplant": int(lines[linenum + 4]),
            "ntype": int(lines[linenum + 5]),
            "tilseq": int(lines[linenum + 6]),
            "conseq": int(lines[linenum + 7]),
            "drseq": int(lines[linenum + 8]),
            "imngmt": int(lines[linenum + 9]),
        }
        if res["scens"][scen]["iplant"] == 1:
            if res["scens"][scen]["imngmt"] in [1, 3]:
                # Annual/Fallow Cropping system
                res["scens"][scen]["jdharv"] = int(lines[linenum + 10])
                res["scens"][scen]["jdplt"] = int(lines[linenum + 11])
                res["scens"][scen]["r1"] = float(lines[linenum + 12])
                res["scens"][scen]["resmgt"] = int(lines[linenum + 13])
                if res["scens"][scen]["resmgt"] == 1:
                    res["scens"][scen]["jdherb"] = int(lines[linenum + 14])
                    linenum += 15
                elif res["scens"][scen]["resmgt"] == 2:
                    res["scens"][scen]["jdburn"] = int(lines[linenum + 14])
                    res["scens"][scen]["fbrna1"] = float(
                        lines[linenum + 15].split()[0]
                    )
                    res["scens"][scen]["fbrno1"] = float(
                        lines[linenum + 15].split()[1]
                    )
                    linenum += 16
                elif res["scens"][scen]["resmgt"] == 3:
                    res["scens"][scen]["jdslge"] = int(lines[linenum + 14])
                    linenum += 15
                elif res["scens"][scen]["resmgt"] == 4:
                    res["scens"][scen]["jdcut"] = int(lines[linenum + 14])
                    res["scens"][scen]["frcu1"] = int(lines[linenum + 15])
                    linenum += 16
                elif res["scens"][scen]["resmgt"] == 5:
                    res["scens"][scen]["jdmove"] = int(lines[linenum + 14])
                    res["scens"][scen]["frmov1"] = float(lines[linenum + 14])
                    linenum += 16
                elif res["scens"][scen]["resmgt"] == 6:
                    linenum += 14
            else:
                # Perrenial Cropland
                res["scens"][scen]["jdharv"] = int(lines[linenum + 10])
                res["scens"][scen]["jdplt"] = int(lines[linenum + 11])
                res["scens"][scen]["jdstop"] = int(lines[linenum + 12])
                res["scens"][scen]["r1"] = float(lines[linenum + 13])
                res["scens"][scen]["mgtopt"] = int(lines[linenum + 14])
                if res["scens"][scen]["mgtopt"] == 1:
                    # Cutting
                    res["scens"][scen]["ncut"] = int(lines[linenum + 15])
                    res["scens"][scen]["cuts"] = [None] * res["scens"][scen][
                        "ncut"
                    ]
                    linenum += 16
                    for cut in range(res["scens"][scen]["ncut"]):
                        res["scens"][scen]["cuts"][cut] = int(lines[linenum])
                        linenum += 1
                elif res["scens"][scen]["mgtopt"] == 2:
                    # Grazing
                    res["scens"][scen]["ncycle"] = int(lines[linenum + 15])
                    res["scens"][scen]["cycles"] = [None] * res["scens"][scen][
                        "ncycle"
                    ]
                    linenum += 16
                    for cycle in range(res["scens"][scen]["ncycle"]):
                        res["scens"][scen]["cycles"][cycle] = {
                            "arr": lines[linenum],
                            "gday": int(lines[linenum + 1]),
                            "gend": int(lines[linenum + 2]),
                        }
                        linenum += 1
                elif res["scens"][scen]["mgtopt"] == 3:
                    linenum += 15
        elif res["scens"][scen]["iplant"] == 2:
            pass
        linenum += 3
    linenum += 3
    res["mantitle"] = lines[linenum]
    res["mandesc"] = "\n".join(lines[linenum + 1 : linenum + 4])
    linenum += 4
    res["nwsofe"] = int(lines[linenum])
    res["inindx"] = [None] * res["nwsofe"]
    linenum += 1
    for idx in range(res["nwsofe"]):
        res["inindx"][idx] = int(lines[linenum])
        linenum += 1
    res["nrots"] = int(lines[linenum])
    linenum += 1
    res["nyears"] = int(lines[linenum])
    sz = res["nyears"] * res["nrots"]
    res["rotations"] = [None] * sz
    linenum += 6
    yidx = 0
    for _rot in range(res["nrots"]):
        for _year in range(res["nyears"]):
            res["rotations"][yidx] = [None] * res["nwsofe"]
            for ofe in range(res["nwsofe"]):
                res["rotations"][yidx][ofe] = {
                    "plant": int(lines[linenum]),
                    "yearindex": int(lines[linenum + 1]),
                }
                linenum += 3
            yidx += 1
        linenum += 4

    return res


def rfactor(times, points, return_rfactor_metric=True):
    """Compute the R-factor.

    https://www.hydrol-earth-syst-sci.net/19/4113/2015/hess-19-4113-2015.pdf
    It would appear that a strict implementation would need to have a six
    hour dry period around events and require more then 12mm of precipitation.

    Args:
      times (list): List of decimal time values for a date.
      points (list): list of accumulated precip values (mm).
      return_rfactor_metric (bool, optional): Should this return a metric
        (default) or english unit R value.

    Returns:
      rfactor (float): Units of MJ mm ha-1 h-1
    """
    # No precip!
    if not times:
        return 0
    # interpolate dataset into 30 minute bins
    func = interp1d(
        times,
        points,
        kind="linear",
        fill_value=(0, points[-1]),
        bounds_error=False,
    )
    accum = func(np.arange(0, 24.01, 0.5))
    rate_mmhr = (accum[1:] - accum[0:-1]) * 2.0
    # sum of E x I
    # I is the 30 minute peak intensity (mm h-1), capped at 3 in/hr
    Imax = min([3.0 * 25.4, np.max(rate_mmhr)])
    # E is sum of e_r (MJ ha-1 mm-1) * p_r (mm)
    e_r = 0.29 * (1.0 - 0.72 * np.exp(-0.082 * rate_mmhr))
    # rate * times
    p_r = rate_mmhr / 2.0
    # MJ ha-1 * mm h-1  or MJ inch a-1 h-1
    unitconv = 1.0 if return_rfactor_metric else (1.0 / 25.4 / 2.47105)
    return np.sum(e_r * p_r) * Imax * unitconv


def read_cli(filename, compute_rfactor=False, return_rfactor_metric=True):
    """Read WEPP CLI File, Return DataFrame

    Args:
      filename (str): Filename to read
      compute_rfactor (bool, optional): Should the R-factor be computed as
        well, adds computational expense and default is False.
      return_rfactor_metric (bool, optional): should the R-factor be
        computed as the common metric value.  Default is True.

    Returns:
      pandas.DataFrame
    """
    rows = []
    dates = []
    lines = open(filename).readlines()
    linenum = 15
    while linenum < len(lines):
        (da, mo, year, breakpoints, tmax, tmin, rad, wvl, wdir, tdew) = lines[
            linenum
        ].split()
        breakpoints = int(breakpoints)
        accum = 0
        times = []
        points = []
        for i in range(1, breakpoints + 1):
            (ts, accum) = lines[linenum + i].split()
            times.append(float(ts))
            points.append(float(accum))
        maxr = 0
        for i in range(1, len(times)):
            dt = times[i] - times[i - 1]
            dr = points[i] - points[i - 1]
            rate = dr / dt
            if rate > maxr:
                maxr = rate
        linenum += breakpoints + 1
        dates.append(datetime.date(int(year), int(mo), int(da)))
        rows.append(
            {
                "tmax": float(tmax),
                "tmin": float(tmin),
                "rad": float(rad),
                "wvl": float(wvl),
                "wdir": float(wdir),
                "tdew": float(tdew),
                "maxr": maxr,
                "bpcount": breakpoints,
                "pcpn": float(accum),
                "rfactor": (
                    np.nan
                    if not compute_rfactor
                    else rfactor(
                        times,
                        points,
                        return_rfactor_metric=return_rfactor_metric,
                    )
                ),
            }
        )

    return pd.DataFrame(rows, index=pd.DatetimeIndex(dates))


def read_env(filename, year0=2006):
    """Read WEPP .env file, return a dataframe

    Args:
      filename (str): Filename to read
      year0 (int,optional): The simulation start year minus 1

    Returns:
      pd.DataFrame
    """
    df = pd.read_csv(
        filename,
        skiprows=3,
        index_col=False,
        sep=r"\s+",
        header=None,
        na_values=["*******", "******", "*****"],
        names=[
            "day",
            "month",
            "year",
            "precip",
            "runoff",
            "ir_det",
            "av_det",
            "mx_det",
            "point",
            "av_dep",
            "max_dep",
            "point2",
            "sed_del",
            "er",
        ],
    )
    if df.empty:
        df["date"] = None
    else:
        # Faster than +=
        df["year"] = df["year"] + year0
        # Considerably faster than df.apply
        df["date"] = pd.to_datetime(
            dict(year=df["year"], month=df["month"], day=df["day"])
        )
    return df


def read_ofe(filename, year0=2006):
    """Read OFE .ofe file, return a dataframe

    Args:
      filename (str): Filename to read
      year0 (int,optional): The simulation start year minus 1

    Returns:
      pd.DataFrame
    """
    df = pd.read_csv(
        filename,
        skiprows=2,
        index_col=False,
        sep=r"\s+",
        header=None,
        na_values=["*******", "******", "********"],
        names=[
            "ofe",
            "day",
            "month",
            "year",
            "precip",
            "runoff",
            "effint",
            "peakro",
            "effdur",
            "enrich_ratio",
            "keff",
            "sm",
            "leafarea",
            "canhght",
            "cancov",
            "intcov",
            "rilcov",
            "livbio",
            "deadbio",
            "ki",
            "kr",
            "tcrit",
            "rilwid",
            "sedleave",
        ],
    )
    if df.empty:
        df["date"] = None
    else:
        # Faster than +=
        df["year"] = df["year"] + year0
        # Considerably faster than df.apply
        df["date"] = pd.to_datetime(
            dict(year=df["year"], month=df["month"], day=df["day"])
        )
    return df


def _date_from_year_jday(df):
    """Create a date column based on year and jday columns."""
    df["date"] = pd.to_datetime(
        df["year"].astype(str) + " " + df["jday"].astype(str), format="%Y %j"
    )


def read_wb(filename):
    """Read a *custom* WEPP .wb file into Pandas Data Table"""
    df = pd.read_csv(filename, sep=r"\s+", na_values=["*******", "******"])
    if df.empty:
        df["date"] = None
    else:
        # Considerably faster than df.apply
        _date_from_year_jday(df)
    return df


def read_crop(filename):
    """Read WEPP's plant and residue output file.

    Args:
      filename (str): The file to read in.

    Returns:
      pandas.DataFrame
    """
    df = pd.read_csv(
        filename,
        skiprows=13,
        index_col=False,
        sep=r"\s+",
        header=None,
        na_values=["*******", "******", "********"],
        names=[
            "ofe",
            "jday",
            "year",
            "canopy_height_m",
            "canopy_percent",
            "lai",
            "cover_rill_percent",
            "cover_inter_percent",
            "cover_inter_type",
            "live_biomass_kgm2",
            "standing_residue_kgm2",
            "flat_residue_last_type",
            "flat_residue_last_kgm2",
            "flat_residue_prev_type",
            "flat_residue_prev_kgm2",
            "flat_residue_all_type",
            "flat_residue_all_kgm2",
            "buried_residue_last_kgm2",
            "buried_residue_prev_kgm2",
            "buried_residue_all_kgm2",
            "deadroot_residue_last_type",
            "deadroot_residue_last_kgm2",
            "deadroot_residue_prev_type",
            "deadroot_residue_prev_kgm2",
            "deadroot_residue_all_type",
            "deadroot_residue_all_kgm2",
            "avg_temp_c",
        ],
    )
    # Convert jday into dates
    _date_from_year_jday(df)
    return df
