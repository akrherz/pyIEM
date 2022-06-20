"""util script to call `windrose` package"""
from calendar import month_abbr
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo  # type: ignore

import numpy as np
import pandas as pd
from pandas import read_sql
from metpy.units import units as mpunits
from sqlalchemy import text

# Local
from pyiem.plot.util import fitbox
from pyiem.plot.windrose import histogram, plot, WindrosePlot
from pyiem.util import get_sqlalchemy_conn, utc
from pyiem.network import Table as NetworkTable


WINDUNITS = {
    "mph": {
        "label": "miles per hour",
        "units": mpunits("mph"),
        "bins": (2, 5, 7, 10, 15, 20),
    },
    "kts": {
        "label": "knots",
        "units": mpunits("knots"),
        "bins": (2, 5, 7, 10, 15, 20),
    },
    "mps": {
        "label": "meters per second",
        "units": mpunits("meter / second"),
        "bins": (1, 4, 6, 8, 10, 12),
    },
    "kph": {
        "label": "kilometers per hour",
        "units": mpunits("kilometer / hour"),
        "bins": (4, 10, 14, 20, 30, 40),
    },
}
RAOB_BINS = {
    "mph": [2, 25, 50, 75, 100, 150],
    "kts": [2, 25, 50, 75, 100, 15],
    "mps": [1, 10, 15, 25, 50, 75],
    "kph": [4, 10, 14, 20, 30, 40],
}


def _make_timelimit_string(kwargs):
    """Generate a string for the time limiters"""
    hours = kwargs.get("hours")
    months = kwargs.get("months")
    limit_by_doy = kwargs.get("limit_by_doy")
    if hours is None and months is None and limit_by_doy is None:
        return ""
    tlimit = "[Time Domain: "
    if limit_by_doy is not None:
        sts = kwargs.get("sts")
        ets = kwargs.get("ets")
        d1 = sts.strftime("%b %-d")
        d2 = ets.strftime("%b %-d")
        tlimit += f"{d1} - {d2}, "
    elif months is not None and len(months) < 12:
        for h in months:
            tlimit += f"{month_abbr[h]},"
    if hours is not None:
        if len(hours) > 4:
            tlimit += (
                f"{datetime(2000, 1, 1, hours[0]):%-I %p}-"
                f"{datetime(2000, 1, 1, hours[-1]):%-I %p}"
            )
        else:
            for h in hours:
                tlimit += f"{datetime(2000, 1, 1, h):%-I %p},"
    tlimit += "]"
    return tlimit


def _get_data(station, **kwargs):
    """Helper function to get data out of IEM databases

    Args:
      station (str): the station identifier
      database (str): the name of the database to connect to, we assume we can
        then query a table called `alldata`
      sts (datetime): the floor to query data for
      ets (datetime): the ceiling to query data for
      monthinfo (dict): information on how to query for months
      hourinfo (dict): information on how to query for hours
      level (int): in case of RAOB, which pressure level (hPa)

    Returns:
      pandas.DataFrame of the data
    """
    rlimiter = ""
    sts = kwargs.get("sts")
    ets = kwargs.get("ets")
    database = kwargs.get("database", "asos")
    if database == "asos":
        rlimiter = " and report_type = 2 "
    tlimit = ""
    sqlargs = {}
    if kwargs.get("limit_by_doy", False):
        tlimit = (
            f"and to_char(valid, 'mmdd') >= '{sts:%m%d}' and "
            f"to_char(valid, 'mmdd') < '{ets:%m%d}' "
        )
        if sts.strftime("%m%d") > ets.strftime("%m%d"):
            tlimit = (
                f"and (to_char(valid, 'mmdd') >= '{sts:%m%d}' or "
                f"to_char(valid, 'mmdd') < '{ets:%m%d}') "
            )
    elif kwargs.get("months") is not None and len(kwargs["months"]) < 12:
        sqlargs["months"] = tuple(kwargs["months"])
        tlimit += " and extract(month from valid) in :months "
    if kwargs.get("hours") is not None:  # can combo with the above
        tzname = kwargs.get("tzname")
        te = "" if tzname is None else f" at time zone '{tzname}'"
        if len(kwargs["hours"]) < 24:
            sqlargs["hours"] = tuple(kwargs["hours"])
            tlimit += f" and extract(hour from valid{te}) in :hours "
    sql = text(
        "SELECT sknt, drct, valid at time zone 'UTC' as valid "
        "from alldata WHERE station = :station "
        f"and valid > :sts and valid < :ets {tlimit} {rlimiter}"
    )
    sqlargs["station"] = station
    sqlargs["sts"] = sts
    sqlargs["ets"] = ets
    if kwargs.get("level") is not None:  # HACK!
        database = "raob"
        # here comes another hack, stations with starting with _ are virtual
        sqlargs["stations"] = [station, "ZZZZ"]
        if station.startswith("_"):
            nt = NetworkTable("RAOB")
            sqlargs["stations"] = tuple(
                nt.sts.get(station, {})
                .get("name", "X--YYY ZZZ")
                .split("--")[1]
                .strip()
                .split(" ")
            )
        sql = text(
            f"""SELECT p.smps * 1.94384 as sknt, p.drct,
        f.valid at time zone 'UTC' as valid from
        raob_flights f JOIN raob_profile p on (f.fid = p.fid) WHERE
        f.station in :stations and p.pressure = :level and
        p.smps is not null
        and p.drct is not null and valid >= :sts and valid < :ets
        {tlimit}"""
        )
        sqlargs["level"] = kwargs["level"]
    with get_sqlalchemy_conn(database) as conn:
        df = read_sql(sql, conn, params=sqlargs, index_col=None)
    if not df.empty:
        # Make valid column timezone aware
        df["valid"] = df["valid"].dt.tz_localize(timezone.utc)
    # If sknt or drct are null, we want to set the other to null as well
    df.loc[pd.isnull(df["drct"]), "sknt"] = np.nan
    df.loc[pd.isnull(df["sknt"]), "drct"] = np.nan

    return df


def _make_textresult(station, df, **kwargs):
    """Generate a text table of windrose information

    Args:
      station (str): the station identifier
      df (pd.DataFrame): The dataframe with data
      units (str): the units of the `sknt` values
      nsector (int): number of sectors to divide rose into
      sname (str): the station name
      monthinfo (dict): information on month limiting
      hourinfo (dict): information on hour limiting
      level (int): in case of RAOB, which level do we care for
      bins (list): values to bin the wind speeds
      tzname (str): Time zone for the report.

    Returns:
      str of information"""
    if df.empty:
        return "No Data Found"
    wu = WINDUNITS[kwargs.get("units", "mph")]
    bins = kwargs.get("bins")
    if not hasattr(bins, "units"):
        bins = wu["bins"] * wu["units"]
        if kwargs.get("level") is not None:
            bins = RAOB_BINS[kwargs.get("units", "mph")] * wu["units"]
    # Effectively filters out the nulls
    df2 = df[df["drct"] >= 0]
    speed = df2["sknt"].values * mpunits("knots")
    direction = df2["drct"].values * mpunits("degree")
    calm_percent, dir_centers, table = histogram(
        speed, direction, bins, kwargs.get("nsector", 36)
    )
    sn = kwargs.get("sname", f"(({station}))")
    res = (
        "# Windrose Data Table (Percent Frequency) " f"for {sn} ({station})\n"
    )
    res += (
        f"# Observations Used/Missing/Total: {len(df2.index)}/"
        f"{len(df.index) - len(df2.index)}/{len(df.index)}\n"
    )
    res += f"# {_time_domain_string(df, kwargs.get('tzname'))}\n"
    res += f"# Time Limiter: {_make_timelimit_string(kwargs)}\n"
    res += f"# Wind Speed Units: {wu['label']}\n"
    if kwargs.get("level") is not None:
        res += f"# RAOB Pressure (hPa) Level: {kwargs['level']}\n"
    res += (
        f"# Generated {utc():%d %b %Y %H:%M} UTC, "
        "contact: akrherz@iastate.edu\n"
    )
    res += "# First value in table is CALM\n"
    cols = ["Direction", "Calm"]
    # Print out Speed Bins
    for i, val in enumerate(bins.m):
        maxval = (
            "+"
            if i == bins.m.shape[0] - 1
            else f" {(bins.m[i + 1] - 0.1):4.1f}"
        )
        cols.append(f"{val:4.1f}{maxval}")

    delta = dir_centers.m[1] - dir_centers.m[0]
    res += ",".join([f"{c:9s}" for c in cols]) + "\n"
    for i, val in enumerate(dir_centers.m):
        minval = val - delta / 2.0
        if minval < 0:
            minval += 360.0
        maxval = np.min([360, val + delta / 2.0 - 1])
        ll = np.round(calm_percent.m, 2) if i == 0 else ""
        res += f"{minval:03.0f}-{maxval:03.0f}  ,{str(ll):9s},"
        res += ",".join(
            [f"{table.m[i, j]:9.3f}" for j in range(bins.m.shape[0])]
        )
        res += "\n"
    return res


def _time_domain_string(df, tzname):
    """Custom time label option."""
    sts = df["valid"].min().to_pydatetime()
    ets = df["valid"].max().to_pydatetime()
    timeformat = "%d %b %Y %I:%M %p"
    if tzname is not None:
        sts = sts.astimezone(ZoneInfo(tzname))
        ets = ets.astimezone(ZoneInfo(tzname))
    if tzname == "UTC":
        timeformat = "%d %b %Y %H:%M"
    return (
        f"{sts.strftime(timeformat)} - {ets.strftime(timeformat)} "
        f"{'' if tzname is None else tzname}"
    )


def _make_plot(station, df, **kwargs):
    """Generate a matplotlib windrose plot

    Args:
      station (str): station identifier
      df (pd.DataFrame): observations
      drct (list): list of wind directions
      units (str): units of wind speed
      nsector (int): number of bins to use for windrose
      rmax (float): radius of the plot
      hours (list): hour limit for plot
      month (list): month limit for plot
      sname (str): station name
      level (int): RAOB level in hPa of interest
      bins (list): values for binning the wind speeds
      tzname (str): Time zone this plot is produced in.
      cmap (colormap): Matplotlib colormap to use.

    Returns:
      matplotlib.Figure
    """
    wu = WINDUNITS[kwargs.get("units", "mph")]
    # Filters the missing values
    df2 = df[df["drct"] >= 0]
    direction = df2["drct"].values * mpunits("degree")
    if "speed" in df2.columns:
        speed = df2["speed"].values * wu["units"]
    else:
        speed = df2["sknt"].values * mpunits("knots")
    bins = kwargs.get("bins")
    if not hasattr(bins, "units"):
        bins = wu["bins"] * wu["units"]
        if kwargs.get("level") is not None:
            bins = RAOB_BINS[kwargs.get("units", "mph")] * wu["units"]
    if len(df2.index) < 5:
        wp = WindrosePlot()
        wp.ax.text(
            0.5,
            0.5,
            "Not Enough Data For Plot.",
            ha="center",
            transform=wp.ax.transAxes,
        )
        return wp.fig
    wp = plot(
        direction,
        speed,
        bins=bins,
        nsector=kwargs.get("nsector", 36),
        rmax=kwargs.get("rmax"),
        cmap=kwargs.get("cmap"),
    )

    # Now we put some fancy debugging info on the plot
    tlimit = _make_timelimit_string(kwargs)
    sn = kwargs.get("sname", f"(({station}))")
    level = kwargs.get("level")
    sl = "" if level is None else f" @{level} hPa"
    label = (
        f"[{station}] {sn}{sl}\n"
        f"Windrose Plot {tlimit}\n"
        f"Time Bounds: {_time_domain_string(df, kwargs.get('tzname'))}"
    )
    fitbox(wp.fig, label, 0.14, 0.99, 0.92, 0.99, ha="left")
    label = (
        "Summary\n"
        f"obs count: {len(df.index)}\n"
        f"Missing: {len(df.index) - len(df2.index)}\n"
        f"Avg Speed: {speed.m.mean():.1f} {kwargs.get('units', 'mph')}"
    )
    wp.fig.text(0.96, 0.11, label, ha="right", fontsize=14)
    if not kwargs.get("nogenerated", False):
        wp.fig.text(
            0.02,
            0.1,
            f"Generated: {utc():%d %b %Y}",
            verticalalignment="bottom",
            fontsize=14,
        )
    # Denote the direction blowing from
    lbl = (
        f"Calm values are < {bins.m[0]:.1f} {kwargs.get('units', 'mph')}\n"
        "Arrows indicate wind direction."
    )
    wp.fig.text(0.02, 0.125, lbl, va="bottom")

    return wp.fig


def windrose(station, **kwargs):
    """Utility function that generates a windrose plot

    Args:
      station (str): station identifier to search database for
      database (str,optional): database name to look for data within
      months (list,optional): optional list of months to limit plot to
      hours (list,optional): optional list of hours to limit plot to
      sts (datetime,optional): start datetime
      ets (datetime,optional): end datetime
      units (str,optional): units to plot values as, default to `mph`.
      nsector (int,optional): number of bins to devide the windrose into
      justdata (boolean,optional): if True, write out the data only
      sname (str,optional): The name of this station, if not specified it will
        default to the ((`station`)) identifier
      sknt (list,optional): A list of wind speeds in knots already generated
      drct (list,optional): A list of wind directions (deg N) already generated
      valid (list,optional): A list of valid datetimes (with tzinfo set), used
        in the case of providing sknt and drct.
      level (int,optional): In case of RAOB, which level interests us (hPa)
      bins (list,optional): bins to use for the wind speed
      tzname (str,optional): Time zone to use for the plot.
      cmap (cmap,optional): Matplotlib colormap to pass to barplot.
      limit_by_doy (bool,optional): Use the `sts` and `ets` to define a period
        of days each year to limit the data by. Default `false`.

    Returns:
      matplotlib.Figure instance or textdata
    """
    wu = WINDUNITS[kwargs.get("units", "mph")]
    if kwargs.get("sts") is None:
        kwargs["sts"] = datetime(1970, 1, 1)
    if kwargs.get("ets") is None:
        kwargs["ets"] = datetime(2050, 1, 1)
    sknt = kwargs.get("sknt")
    drct = kwargs.get("drct")
    if sknt is None or drct is None:
        df = _get_data(
            station,
            **kwargs,
        )
    else:
        df = pd.DataFrame(
            {"sknt": sknt, "drct": drct, "valid": kwargs.get("valid")}
        )
    # Make sure our bins have units
    bins = kwargs.get("bins")
    if not hasattr(bins, "units") and bins:
        kwargs["bins"] = bins * wu["units"]
    # Convert wind speed into the units we want here
    if df["sknt"].max() > 0:
        df["speed"] = (df["sknt"].values * mpunits("knots")).to(wu["units"]).m
    if kwargs.get("justdata", False):
        return _make_textresult(station, df, **kwargs)

    return _make_plot(station, df, **kwargs)
