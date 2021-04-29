"""util script to call `windrose` package"""
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from pandas.io.sql import read_sql
from metpy.units import units as mpunits
from pyiem.plot.util import fitbox
from pyiem.plot.windrose import histogram, plot, WindrosePlot
from pyiem.util import get_dbconn
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


def _get_timeinfo(arr, datepart, fullsize, tzname):
    """Convert the months/hours array provided into label text and SQL

    Args:
      arr (list): A list of ints
      datepart (str): the part to extract from the database timestamp
      fullsize (int): the size of specifying all dates
      tzname (str): The timezone to compute this limiter in.

    Returns:
      dict with keys `sqltext` and `labeltext`
    """
    sql = ""
    lbl = "All included"
    if len(arr) == 1:
        sql = " and extract(%s from valid%s) = %s " % (
            datepart,
            "" if tzname is None else " at time zone '%s'" % (tzname,),
            arr[0],
        )
        lbl = str(tuple(arr))
    elif len(arr) < fullsize:
        sql = (" and extract(%s from valid%s) in %s ") % (
            datepart,
            "" if tzname is None else " at time zone '%s'" % (tzname,),
            (str(tuple(arr))).replace("'", ""),
        )
        lbl = str(tuple(arr))
    return dict(sqltext=sql, labeltext=lbl)


def _get_data(station, database, sts, ets, monthinfo, hourinfo, level):
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
    # Query observations
    db = get_dbconn(database, user="nobody")
    rlimiter = ""
    if database == "asos":
        rlimiter = " and report_type = 2 "
    sql = (
        "SELECT sknt, drct, valid at time zone 'UTC' as valid "
        f"from alldata WHERE station = '{station}' "
        f"and valid > '{sts}' and valid < '{ets}' {monthinfo['sqltext']} "
        f"{hourinfo['sqltext']} {rlimiter}"
    )
    if level is not None:  # HACK!
        db = get_dbconn("postgis")
        # here comes another hack, stations with starting with _ are virtual
        stations = [station, "ZZZZ"]
        if station.startswith("_"):
            nt = NetworkTable("RAOB")
            stations = (
                nt.sts.get(station, {})
                .get("name", "X--YYY ZZZ")
                .split("--")[1]
                .strip()
                .split(" ")
            )
        sql = """SELECT p.smps * 1.94384 as sknt, p.drct,
        f.valid at time zone 'UTC' as valid from
        raob_flights f JOIN raob_profile p on (f.fid = p.fid) WHERE
        f.station in %s and p.pressure = %s and p.smps is not null
        and p.drct is not null and valid >= '%s' and valid < '%s'
        %s
        %s
        """ % (
            str(tuple(stations)),
            level,
            sts,
            ets,
            monthinfo["sqltext"],
            hourinfo["sqltext"],
        )
    df = read_sql(sql, db, index_col=None)
    if not df.empty:
        # Make valid column timezone aware
        df["valid"] = df["valid"].dt.tz_localize(timezone.utc)
    # If sknt or drct are null, we want to set the other to null as well
    df.loc[pd.isnull(df["drct"]), "sknt"] = None
    df.loc[pd.isnull(df["sknt"]), "drct"] = None

    return df


def _make_textresult(
    station,
    df,
    units,
    nsector,
    sname,
    monthinfo,
    hourinfo,
    level,
    bins,
    tzname,
):
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
    wu = WINDUNITS[units]
    if not hasattr(bins, "units"):
        bins = wu["bins"] * wu["units"]
        if level is not None:
            bins = RAOB_BINS[units] * wu["units"]
    # Effectively filters out the nulls
    df2 = df[df["drct"] >= 0]
    speed = df2["sknt"].values * mpunits("knots")
    direction = df2["drct"].values * mpunits("degree")
    calm_percent, dir_centers, table = histogram(
        speed, direction, bins, nsector
    )
    res = ("# Windrose Data Table (Percent Frequency) " "for %s (%s)\n") % (
        sname if sname is not None else "((%s))" % (station,),
        station,
    )
    res += ("# Observations Used/Missing/Total: %s/%s/%s\n") % (
        len(df2.index),
        len(df.index) - len(df2.index),
        len(df.index),
    )
    res += f"# {_time_domain_string(df, tzname)}\n"
    res += "# Hour Limiter: %s\n" % (hourinfo["labeltext"],)
    res += "# Month Limiter: %s\n" % (monthinfo["labeltext"],)
    res += "# Wind Speed Units: %s\n" % (wu["label"],)
    if level is not None:
        res += "# RAOB Pressure (hPa) Level: %s\n" % (level,)
    res += ("# Generated %s UTC, contact: akrherz@iastate.edu\n") % (
        datetime.utcnow().strftime("%d %b %Y %H:%M"),
    )
    res += "# First value in table is CALM\n"
    cols = ["Direction", "Calm"]
    # Print out Speed Bins
    for i, val in enumerate(bins.m):
        maxval = (
            "+"
            if i == bins.m.shape[0] - 1
            else " %4.1f" % (bins.m[i + 1] - 0.1,)
        )
        cols.append("%4.1f%s" % (val, maxval))

    delta = dir_centers.m[1] - dir_centers.m[0]
    res += ",".join(["%9s" % (c,) for c in cols]) + "\n"
    for i, val in enumerate(dir_centers.m):
        minval = val - delta / 2.0
        if minval < 0:
            minval += 360.0
        maxval = np.min([360, val + delta / 2.0 - 1])
        res += "%03i-%03i  ,%9s," % (
            minval,
            maxval,
            np.round(calm_percent.m, 2) if i == 0 else "",
        )
        res += ",".join(
            ["%9.3f" % (table.m[i, j],) for j in range(bins.m.shape[0])]
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
    return "%s - %s %s" % (
        sts.strftime(timeformat),
        ets.strftime(timeformat),
        "" if tzname is None else tzname,
    )


def _make_plot(
    station,
    df,
    units,
    nsector,
    rmax,
    hours,
    months,
    sname,
    level,
    bins,
    tzname,
    **kwargs,
):
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
    wu = WINDUNITS[units]
    # Filters the missing values
    df2 = df[df["drct"] >= 0]
    direction = df2["drct"].values * mpunits("degree")
    if "speed" in df2.columns:
        speed = df2["speed"].values * wu["units"]
    else:
        speed = df2["sknt"].values * mpunits("knots")
    if not hasattr(bins, "units"):
        bins = wu["bins"] * wu["units"]
        if level is not None:
            bins = RAOB_BINS[units] * wu["units"]
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
        nsector=nsector,
        rmax=rmax,
        cmap=kwargs.get("cmap"),
    )

    # Now we put some fancy debugging info on the plot
    tlimit = "[Time Domain: "
    if len(hours) == 24 and len(months) == 12:
        tlimit = ""
    if len(hours) < 24:
        if len(hours) > 4:
            tlimit += "%s-%s" % (
                datetime(2000, 1, 1, hours[0]).strftime("%-I %p"),
                datetime(2000, 1, 1, hours[-1]).strftime("%-I %p"),
            )
        else:
            for h in hours:
                tlimit += "%s," % (datetime(2000, 1, 1, h).strftime("%-I %p"),)
    if len(months) < 12:
        for h in months:
            tlimit += "%s," % (datetime(2000, h, 1).strftime("%b"),)
    if tlimit != "":
        tlimit += "]"
    label = ("[%s] %s%s\n" "Windrose Plot %s\n" "Time Bounds: %s") % (
        station,
        sname if sname is not None else "((%s))" % (station,),
        "" if level is None else " @%s hPa" % (level,),
        tlimit,
        _time_domain_string(df, tzname),
    )
    fitbox(wp.fig, label, 0.14, 0.99, 0.92, 0.99, ha="left")
    label = ("Summary\nobs count: %s\nMissing: %s\nAvg Speed: %.1f %s") % (
        len(df.index),
        len(df.index) - len(df2.index),
        speed.m.mean(),
        units,
    )
    wp.fig.text(0.96, 0.11, label, ha="right", fontsize=14)
    if not kwargs.get("nogenerated", False):
        wp.fig.text(
            0.02,
            0.1,
            "Generated: %s" % (datetime.now().strftime("%d %b %Y"),),
            verticalalignment="bottom",
            fontsize=14,
        )
    # Denote the direction blowing from
    lbl = ("Calm values are < %.1f %s\nArrows indicate wind direction.") % (
        bins.m[0],
        units,
    )
    wp.fig.text(0.02, 0.125, lbl, va="bottom")

    return wp.fig


def windrose(
    station,
    database="asos",
    months=np.arange(1, 13),
    hours=np.arange(0, 24),
    sts=datetime(1970, 1, 1),
    ets=datetime(2050, 1, 1),
    units="mph",
    nsector=36,
    justdata=False,
    rmax=None,
    sname=None,
    sknt=None,
    drct=None,
    valid=None,
    level=None,
    bins=None,
    tzname=None,
    **kwargs,
):
    """Utility function that generates a windrose plot

    Args:
      station (str): station identifier to search database for
      database (str,optional): database name to look for data within
      months (list,optional): optional list of months to limit plot to
      hours (list,optional): optional list of hours to limit plot to
      sts (datetime,optional): start datetime
      ets (datetime,optional): end datetime
      units (str,optional): units to plot values as
      nsector (int,optional): number of bins to devide the windrose into
      justdata (boolean,optional): if True, write out the data only
      sname (str,optional): The name of this station, if not specified it will
        default to the ((`station`)) identifier
      sknt (list,optional): A list of wind speeds in knots already generated
      drct (list,optional): A list of wind directions (deg N) already generated
      valid (list,optional): A list of valid datetimes (with tzinfo set)
      level (int,optional): In case of RAOB, which level interests us (hPa)
      bins (list,optional): bins to use for the wind speed
      tzname (str,optional): Time zone to use for the plot.
      cmap (cmap,optional): Matplotlib colormap to pass to barplot.

    Returns:
      matplotlib.Figure instance or textdata
    """
    monthinfo = _get_timeinfo(months, "month", 12, tzname)
    hourinfo = _get_timeinfo(hours, "hour", 24, tzname)
    wu = WINDUNITS[units]
    if sknt is None or drct is None:
        df = _get_data(station, database, sts, ets, monthinfo, hourinfo, level)
    else:
        df = pd.DataFrame({"sknt": sknt, "drct": drct, "valid": valid})
    # Make sure our bins have units
    if not hasattr(bins, "units") and bins:
        bins = bins * wu["units"]
    # Convert wind speed into the units we want here
    if df["sknt"].max() > 0:
        df["speed"] = (df["sknt"].values * mpunits("knots")).to(wu["units"]).m
    if justdata:
        return _make_textresult(
            station,
            df,
            units,
            nsector,
            sname,
            monthinfo,
            hourinfo,
            level,
            bins,
            tzname,
        )

    return _make_plot(
        station,
        df,
        units,
        nsector,
        rmax,
        hours,
        months,
        sname,
        level,
        bins,
        tzname,
        **kwargs,
    )
