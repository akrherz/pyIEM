"""A class representing an observation stored in the IEM database"""

import math
import warnings
from collections import UserDict
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import metpy.calc as mcalc
import numpy as np
import pandas as pd
from metpy.units import units as munits

# Track which columns are in the summary table for the null_ check below
SUMMARY_COLS = (
    "max_tmpf min_tmpf max_sknt max_gust max_sknt_ts max_gust_ts max_dwpf "
    "min_dwpf pday pmonth snow snowd "
    "snoww max_drct max_srad coop_tmpf coop_valid et_inch srad_mj avg_sknt "
    "vector_avg_drct avg_rh min_rh max_rh max_water_tmpf min_water_tmpf "
    "max_feel avg_feel min_feel min_rstage max_rstage report"
).split()

VALUE_BOUNDS = {
    "max_tmpf": (-100.0, 150.0),
    "min_tmpf": (-100.0, 150.0),
    "tmpf": (-100.0, 150.0),
    "max_water_tmpf": (-100.0, 212.0),  # could be some wild sensors
    "min_water_tmpf": (-100.0, 212.0),
    "coop_tmpf": (-100.0, 150.0),
    "dwpf": (-100.0, 150.0),
    "max_dwpf": (-100.0, 150.0),
    "min_dwpf": (-100.0, 150.0),
    "relh": (0.0, 101.0),  # Life choice
    "min_rh": (0.0, 101.0),
    "avg_rh": (0.0, 101.0),
    "max_rh": (0.0, 101.0),
    "feel": (-150.0, 200.0),
    "max_feel": (-150.0, 200.0),
    "avg_feel": (-150.0, 200.0),
    "min_feel": (-150.0, 200.0),
    "max_sknt": (0.0, 250.0),  # Life choice, but 255/256 is often bad
    "max_gust": (0.0, 250.0),
    "sknt": (0.0, 250.0),
    "max_drct": (0.0, 360.0),
    "drct": (0.0, 360.0),
    "srad": (0.0, 2000.0),
    "srad_mj": (0.0, 60.0),  # meh
    "pday": (0, 50.0),
    "pmonth": (0, 500.0),  # meh
    "snow": (0, 200.0),
    "snowd": (0, 2000.0),
    "et_inch": (0.0, 10.0),
}


def bounded(val, floor, ceiling):
    """Return val if is a finite number within [floor, ceiling], else None."""
    if val is None:
        return None
    # Fast path for floats and ints
    if isinstance(val, (float, int)):
        if not math.isfinite(val) or val < floor or val > ceiling:
            return None
        return val
    if isinstance(val, np.ndarray):
        if np.ma.is_masked(val):
            return None
        if val.size != 1:
            raise RuntimeError(f"Expected a single value ndarray {val}")
        val = val.item()
    # Fallback for other types (e.g., strings)
    try:
        val = float(val)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(val) or val < floor or val > ceiling:
        return None
    return val


class ObservationData(UserDict):
    """Opinionated dictionary that ensures some QC.

    What it does.
      - Returns `None` when asked for a key that does not exist.
      - Checks value bounds when set with a key that exists within VALUE_BOUNDS
    """

    def __getitem__(self, key: str) -> Any:
        """Return None for missing keys."""
        return self.data.get(key, None)

    def __setitem__(self, key: str, value: Any) -> None:
        """Set item with bounds checking."""
        if key in VALUE_BOUNDS:
            floor, ceiling = VALUE_BOUNDS[key]
            value = bounded(value, floor, ceiling)
        self.data[key] = value


def get_summary_table(valid):
    """Optimize the summary table we potentially use.

    Args:
      valid (datetime with time zone): Datetime

    Returns:
      str table to query
    """
    if valid is None:
        return "summary"
    if (valid.month == 12 and valid.day >= 30) or (
        valid.month == 1 and valid.day < 3
    ):
        return "summary"
    return f"summary_{valid.year}"


def summary_update(txn, data):
    """Updates the summary table and returns affected rows.

    Args:
      txn (psycopg.transaction)
      data (dict)

    Returns:
      int: affected rows count
    """
    # NB with the coalesce func, we prioritize if we have explicit max/min vals
    # But, some of these max values are not tru max daily values
    table = get_summary_table(data["valid"])
    dateconst = (
        " %(localdate)s "
        if data["_isdaily"]
        else " date(%(valid)s at time zone %(tzname)s) "
    )
    sql = f"""UPDATE {table} s SET
    max_water_tmpf = coalesce(%(max_water_tmpf)s,
        greatest(max_water_tmpf, %(water_tmpf)s)),
    min_water_tmpf = coalesce(%(min_water_tmpf)s,
        least(min_water_tmpf, %(water_tmpf)s)),
    max_tmpf = coalesce(%(max_tmpf)s,
        greatest(max_tmpf, %(max_tmpf_cond)s, %(tmpf)s)),
    max_dwpf = coalesce(%(max_dwpf)s,
        greatest(max_dwpf, %(dwpf)s)),
    min_tmpf = coalesce(%(min_tmpf)s,
        least(min_tmpf, %(min_tmpf_cond)s, %(tmpf)s)),
    min_dwpf = coalesce(%(min_dwpf)s, least(min_dwpf, %(dwpf)s)),
    min_feel = coalesce(%(min_feel)s, least(min_feel, %(feel)s)),
    max_feel = coalesce(%(max_feel)s, greatest(max_feel, %(feel)s)),
    max_sknt = greatest(%(max_sknt)s, max_sknt, %(sknt)s),
    max_gust = greatest(%(max_gust)s, max_gust, %(gust)s),
    max_sknt_ts = CASE WHEN %(sknt)s > max_sknt or %(max_sknt)s > max_sknt
            or (max_sknt is null and %(sknt)s > 0)
            THEN coalesce(%(max_sknt_ts)s, %(valid)s)::timestamptz
            ELSE max_sknt_ts END,
    max_gust_ts = CASE WHEN %(gust)s > max_gust or %(max_gust)s > max_gust
            or (max_gust is null and %(gust)s > 0)
            THEN coalesce(%(max_gust_ts)s, %(valid)s)::timestamptz
            ELSE max_gust_ts END,
    pday = coalesce(%(pday)s, pday),
    pmonth = coalesce(%(pmonth)s, pmonth),
    snow = coalesce(%(snow)s, snow),
    snowd = coalesce(%(snowd)s, snowd),
    snoww = coalesce(%(snoww)s, snoww),
    max_drct = coalesce(%(max_drct)s, max_drct),
    max_srad = greatest(%(max_srad)s, %(srad)s, max_srad),
    coop_tmpf = coalesce(%(coop_tmpf)s, coop_tmpf),
    coop_valid = coalesce(%(coop_valid)s, coop_valid),
    et_inch = %(et_inch)s,
    report = coalesce(%(report)s, report),
    max_rh = greatest(%(max_rh)s, %(relh)s, max_rh),
    min_rh = least(%(min_rh)s, %(relh)s, min_rh),
    max_rstage = greatest(%(max_rstage)s, %(rstage)s, max_rstage),
    min_rstage = least(%(min_rstage)s, %(rstage)s, min_rstage),
    srad_mj = coalesce(%(srad_mj)s, srad_mj),
    avg_sknt = coalesce(%(avg_sknt)s, avg_sknt),
    vector_avg_drct = coalesce(%(vector_avg_drct)s, vector_avg_drct)
    WHERE s.iemid = %(iemid)s and s.day = {dateconst}
    """
    txn.execute(sql, data)
    # Check to see if we have any hard coded nulls
    updates = []
    for col in data:
        if col.startswith("null_") and col[5:] in SUMMARY_COLS:
            updates.append(f"{col[5:]} = null")  # noqa
    if updates:
        txn.execute(
            f"UPDATE {table} s SET {', '.join(updates)} "
            f"WHERE s.iemid = %(iemid)s and s.day = {dateconst}",
            data,
        )

    return txn.rowcount


class Observation:
    """my observation object"""

    # NB: Keep positional argment order to limit API breakage
    def __init__(
        self,
        station: str = None,
        network: str = None,
        valid: datetime = None,
        iemid: int = None,
        tzname: str = None,
    ):
        """
        Constructor for the Observation.  Note you need to provide either
        a iemid + tzname or a station + network.

        Args:
          station (str): Station identifier
          network (str): Network identifier
          valid (datetime): Datetime object with tzinfo set or date.
          iemid (int): IEM internal identifier
          tzname (str): time zone string
        """
        # This is somewhat hacky to ensure that we *only* get date objects
        # to trigger the isdaily logic
        isdaily = valid.__class__.__name__ == "date"
        if not isdaily and getattr(valid, "tzinfo", None) is None:
            warnings.warn(
                "tzinfo is not set on valid, defaulting to UTC", stacklevel=1
            )
            if isinstance(valid, np.datetime64):
                valid = pd.Timestamp(valid).to_pydatetime()
            valid = valid.replace(tzinfo=timezone.utc)
        self.data: dict[str, Any] = ObservationData()
        self.data.update(
            {
                "station": station,
                "network": network,
                "iemid": iemid,
                "tzname": tzname,
                "valid": valid,
                "localdate": valid if isdaily else None,
                "_isdaily": isdaily,
            }
        )

    def load(self, txn):
        """
        Load the current observation for this site and time
        """
        if not self.compute_iemid(txn):
            return False
        table = get_summary_table(self.data["valid"])
        if self.data["_isdaily"]:
            sql = (
                f"SELECT * from {table} WHERE iemid = %(iemid)s and "
                "day = %(valid)s"
            )
        else:
            sql = (
                f"SELECT * from current c, {table} s WHERE s.iemid = c.iemid "
                "and s.iemid = %(iemid)s and "
                "s.day = date(%(valid)s at time zone %(tzname)s) and "
                "c.valid = %(valid)s"
            )
        txn.execute(sql, self.data)
        if txn.rowcount < 1:
            return False
        row = txn.fetchone()
        for key in row.keys():
            if key not in ["valid"]:
                self.data[key] = row[key]
        return True

    def calc(self):
        """Compute things not usually computed"""
        if self.data["relh"] is None and None not in [
            self.data["tmpf"],
            self.data["dwpf"],
        ]:
            self.data["relh"] = bounded(
                mcalc.relative_humidity_from_dewpoint(
                    self.data["tmpf"] * munits.degF,
                    self.data["dwpf"] * munits.degF,
                )
                .to(munits.percent)
                .magnitude,
                0.5,
                100.5,
            )
        if (
            self.data["dwpf"] is None
            and None not in [self.data["tmpf"], self.data["relh"]]
            and self.data["relh"] >= 1
            and self.data["relh"] <= 100
        ):
            self.data["dwpf"] = bounded(
                mcalc.dewpoint_from_relative_humidity(
                    self.data["tmpf"] * munits.degF,
                    self.data["relh"] * munits.percent,
                )
                .to(munits.degF)
                .magnitude,
                -100.0,
                100.0,
            )
        if self.data["feel"] is None and None not in [
            self.data["tmpf"],
            self.data["relh"],
        ]:
            # sknt is not a hard requirement
            sk = self.data["sknt"] if self.data["sknt"] is not None else np.nan
            self.data["feel"] = bounded(
                mcalc.apparent_temperature(
                    self.data["tmpf"] * munits.degF,
                    self.data["relh"] * munits.percent,
                    sk * munits.knots,
                    mask_undefined=False,  # less confusion this way
                )
                .to(munits.degF)
                .magnitude,
                -150.0,
                200.0,
            )

    def compute_iemid(self, txn):
        """Load in what our metadata is to save future queries"""
        # Require iemid and tzname be set
        if None not in [self.data["iemid"], self.data["tzname"]]:
            return True
        txn.execute(
            """
        SELECT iemid, tzname from stations where id = %(station)s and
        network = %(network)s
        """,
            self.data,
        )
        if txn.rowcount == 0:
            return False
        row = txn.fetchone()
        self.data["iemid"] = row["iemid"]
        self.data["tzname"] = row["tzname"]
        return True

    def save(self, txn, force_current_log=False, skip_current=False):
        """
        Save this observation to the database via a psycopg transaction
        @param txn is a psycopg transaction
        @param force_current_log boolean - make sure this observation goes to
        the current_log table in the case that it is old, this allows
        reprocessing by the METAR ingestor et al
        @param skip_current boolean - optionally skip updating the current
        table.  This is useful for partial obs
        @return: boolean if this updated one row each
        """
        if not self.compute_iemid(txn):
            return False
        self.calc()
        # Update current table
        sql = """UPDATE current c SET
        tmpf = %(tmpf)s,  dwpf = %(dwpf)s,  drct = %(drct)s,  sknt = %(sknt)s,
        tsf0 = %(tsf0)s, tsf1 = %(tsf1)s,
        tsf2 = %(tsf2)s,  tsf3 = %(tsf3)s,  rwis_subf = %(rwis_subf)s,
        scond0 = %(scond0)s,  scond1 = %(scond1)s,  scond2 = %(scond2)s,
        scond3 = %(scond3)s,  pday = %(pday)s,  c1smv = %(c1smv)s,
        c2smv = %(c2smv)s,  c3smv = %(c3smv)s,  c4smv = %(c4smv)s,
        c5smv = %(c5smv)s,  c1tmpf = %(c1tmpf)s,  c2tmpf = %(c2tmpf)s,
        c3tmpf = %(c3tmpf)s,  c4tmpf = %(c4tmpf)s,  c5tmpf = %(c5tmpf)s,
        pres = %(pres)s,  relh = %(relh)s,  srad = %(srad)s,  vsby = %(vsby)s,
        phour = %(phour)s,  gust = %(gust)s,  raw = %(raw)s,  alti = %(alti)s,
        mslp = %(mslp)s, rstage = %(rstage)s,
        pmonth = %(pmonth)s,  skyc1 = %(skyc1)s,  skyc2 = %(skyc2)s,
        skyc3 = %(skyc3)s,  skyc4 = %(skyc4)s,  skyl1 = %(skyl1)s,
        skyl2 = %(skyl2)s,  skyl3 = %(skyl3)s,  skyl4 = %(skyl4)s,
        pcounter = %(pcounter)s,  discharge = %(discharge)s,  p03i = %(p03i)s,
        p06i = %(p06i)s,  p24i = %(p24i)s,  max_tmpf_6hr = %(max_tmpf_6hr)s,
        min_tmpf_6hr = %(min_tmpf_6hr)s,  max_tmpf_24hr = %(max_tmpf_24hr)s,
        min_tmpf_24hr = %(min_tmpf_24hr)s, wxcodes = %(wxcodes)s,
        battery = %(battery)s, water_tmpf = %(water_tmpf)s,
        ice_accretion_1hr = %(ice_accretion_1hr)s,
        ice_accretion_3hr = %(ice_accretion_3hr)s,
        ice_accretion_6hr = %(ice_accretion_6hr)s,
        feel = %(feel)s, valid = %(valid)s,
        peak_wind_gust = %(peak_wind_gust)s,
        peak_wind_drct = %(peak_wind_drct)s,
        peak_wind_time = %(peak_wind_time)s,
        snowdepth = %(snowdepth)s, srad_1h_j = %(srad_1h_j)s,
        tsoil_4in_f = %(tsoil_4in_f)s, tsoil_8in_f = %(tsoil_8in_f)s,
        tsoil_16in_f = %(tsoil_16in_f)s, tsoil_20in_f = %(tsoil_20in_f)s,
        tsoil_32in_f = %(tsoil_32in_f)s, tsoil_40in_f = %(tsoil_40in_f)s,
        tsoil_64in_f = %(tsoil_64in_f)s, tsoil_128in_f = %(tsoil_128in_f)s,
        updated = now()
        WHERE c.iemid = %(iemid)s and %(valid)s >= c.valid """
        if not self.data["_isdaily"] and not skip_current:
            txn.execute(sql, self.data)
        if skip_current or (force_current_log and txn.rowcount == 0):
            sql = """INSERT into current_log
            (iemid, tmpf, dwpf, drct, sknt,
            tsf0, tsf1, tsf2, tsf3, rwis_subf, scond0, scond1, scond2, scond3,
            valid, pday, c1smv, c2smv, c3smv, c4smv, c5smv, c1tmpf, c2tmpf,
            c3tmpf, c4tmpf, c5tmpf, pres, relh, srad, vsby, phour, gust, raw,
            alti, mslp, rstage, pmonth, skyc1,
            skyc2, skyc3, skyc4, skyl1, skyl2, skyl3, skyl4, pcounter,
            discharge, p03i, p06i, p24i, max_tmpf_6hr, min_tmpf_6hr,
            max_tmpf_24hr, min_tmpf_24hr, wxcodes, battery,
            ice_accretion_1hr, ice_accretion_3hr, ice_accretion_6hr,
            water_tmpf, feel, peak_wind_gust, peak_wind_drct,
            peak_wind_time, snowdepth, srad_1h_j, tsoil_4in_f, tsoil_8in_f,
            tsoil_16in_f, tsoil_20in_f, tsoil_32in_f, tsoil_40in_f,
            tsoil_64in_f, tsoil_128in_f) VALUES(
            %(iemid)s, %(tmpf)s, %(dwpf)s, %(drct)s, %(sknt)s,
            %(tsf0)s, %(tsf1)s, %(tsf2)s, %(tsf3)s,
            %(rwis_subf)s, %(scond0)s, %(scond1)s, %(scond2)s, %(scond3)s,
            %(valid)s, %(pday)s, %(c1smv)s, %(c2smv)s, %(c3smv)s, %(c4smv)s,
            %(c5smv)s, %(c1tmpf)s, %(c2tmpf)s, %(c3tmpf)s, %(c4tmpf)s,
            %(c5tmpf)s, %(pres)s, %(relh)s, %(srad)s, %(vsby)s, %(phour)s,
            %(gust)s, %(raw)s, %(alti)s, %(mslp)s,
            %(rstage)s, %(pmonth)s, %(skyc1)s,
            %(skyc2)s, %(skyc3)s, %(skyc4)s, %(skyl1)s, %(skyl2)s, %(skyl3)s,
            %(skyl4)s, %(pcounter)s, %(discharge)s, %(p03i)s, %(p06i)s,
            %(p24i)s, %(max_tmpf_6hr)s, %(min_tmpf_6hr)s,
            %(max_tmpf_24hr)s, %(min_tmpf_24hr)s, %(wxcodes)s,
            %(battery)s,
            %(ice_accretion_1hr)s, %(ice_accretion_3hr)s,
            %(ice_accretion_6hr)s,
            %(water_tmpf)s, %(feel)s, %(peak_wind_gust)s, %(peak_wind_drct)s,
            %(peak_wind_time)s, %(snowdepth)s, %(srad_1h_j)s, %(tsoil_4in_f)s,
            %(tsoil_8in_f)s, %(tsoil_16in_f)s, %(tsoil_20in_f)s,
            %(tsoil_32in_f)s, %(tsoil_40in_f)s, %(tsoil_64in_f)s,
            %(tsoil_128in_f)s
            )
            """
            if not self.data["_isdaily"]:
                txn.execute(sql, self.data)

        rowcount = summary_update(txn, self.data)
        if rowcount != 1:
            tomorrow = date.today() + timedelta(days=1)
            if self.data["_isdaily"]:
                localvalid = self.data["valid"]
            else:
                # Create a new entry
                localvalid = (
                    self.data["valid"]
                    .astimezone(ZoneInfo(self.data["tzname"]))
                    .date()
                )
            # we don't want dates into the future as this will foul others
            if localvalid > tomorrow:
                return False
            txn.execute(
                f"INSERT into summary_{localvalid.year} "
                "(iemid, day) VALUES (%s, %s)",
                (self.data["iemid"], localvalid),
            )
            # try once more
            summary_update(txn, self.data)

        return True
