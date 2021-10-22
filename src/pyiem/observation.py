"""A class representing an observation stored in the IEM database"""
# pylint: disable=no-member
from collections import UserDict
import warnings
from datetime import timezone, date, timedelta
import math

try:
    from zoneinfo import ZoneInfo  # type: ignore
except ImportError:
    from backports.zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import metpy.calc as mcalc
from metpy.units import units as munits

# A nonsense default that is not None/SQL-null
SENTINEL = 99999


class ObDict(UserDict):  # pylint: disable=too-many-ancestors
    """Custom dictionary implementation.

    If the key starts with ``null_`` and is not defined, we return a sentinel.
    If the key is not defined, we return None.
    """

    def __getitem__(self, key):
        """Overriding a builtin."""
        if key.startswith("null_") and key not in self.data:
            return SENTINEL
        return self.data.get(key)


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


def bounded(val, floor, ceiling):
    """Make sure this is not NaN and between some value."""
    if val is None or np.ma.is_masked(val) or math.isnan(val):
        return None
    val = float(val)
    # belt and suspenders check here
    if math.isnan(val) or val < floor or val > ceiling:
        return None
    return val


def summary_update(txn, data):
    """Updates the summary table and returns affected rows.

    Args:
      txn (psycopg2.transaction)
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
    max_water_tmpf = case when %(null_max_water_tmpf)s is null then null
        else coalesce(%(max_water_tmpf)s,
            greatest(max_water_tmpf, %(water_tmpf)s)) end,
    min_water_tmpf = case when %(null_min_water_tmpf)s is null then null
        else coalesce(%(min_water_tmpf)s,
            least( min_water_tmpf, %(water_tmpf)s)) end,
    max_tmpf = case when %(null_max_tmpf)s is null then null
        else coalesce(%(max_tmpf)s,
            greatest(max_tmpf, %(max_tmpf_cond)s, %(tmpf)s)) end,
    max_dwpf = case when %(null_max_dwpf)s is null then null
        else coalesce(%(max_dwpf)s,
            greatest(max_dwpf, %(dwpf)s)) end,
    min_tmpf = case when %(null_min_tmpf)s is null then null
        else coalesce(%(min_tmpf)s,
            least(min_tmpf, %(min_tmpf_cond)s, %(tmpf)s)) end,
    min_dwpf = case when %(null_min_dwpf)s is null then null
        else coalesce(%(min_dwpf)s, least(min_dwpf, %(dwpf)s)) end,
    min_feel = case when %(null_min_feel)s is null then null
        else coalesce(%(min_feel)s, least(min_feel, %(feel)s)) end,
    max_feel = case when %(null_max_feel)s is null then null
        else coalesce(%(max_feel)s, greatest(max_feel, %(feel)s)) end,
    max_sknt = case when %(null_max_sknt)s is null then null
        else greatest(%(max_sknt)s, max_sknt, %(sknt)s) end,
    max_gust = case when %(null_max_gust)s is null then null
        else greatest(%(max_gust)s, max_gust, %(gust)s) end,
    max_sknt_ts = case when %(null_max_sknt_ts)s is null then null
        else (CASE WHEN %(sknt)s > max_sknt or %(max_sknt)s > max_sknt
            or (max_sknt is null and %(sknt)s > 0)
            THEN coalesce(%(max_sknt_ts)s, %(valid)s)::timestamptz
            ELSE max_sknt_ts END) end,
    max_gust_ts = case when %(null_max_gust_ts)s is null then null
        else (CASE WHEN %(gust)s > max_gust or %(max_gust)s > max_gust
            or (max_gust is null and %(gust)s > 0)
            THEN coalesce(%(max_gust_ts)s, %(valid)s)::timestamptz
            ELSE max_gust_ts END) end,
    pday = case when %(null_pday)s is null then null
        else coalesce(%(pday)s, pday) end,
    pmonth = case when %(null_pmonth)s is null then null
        else coalesce(%(pmonth)s, pmonth) end,
    snow = case when %(null_snow)s is null then null
        else coalesce(%(snow)s, snow) end,
    snowd = case when %(null_snowd)s is null then null
        else coalesce(%(snowd)s, snowd) end,
    snoww = case when %(null_snoww)s is null then null
        else coalesce(%(snoww)s, snoww) end,
    max_drct = case when %(null_max_drct)s is null then null
        else coalesce(%(max_drct)s, max_drct) end,
    max_srad = case when %(null_max_srad)s is null then null
        else coalesce(%(max_srad)s, max_srad) end,
    coop_tmpf = case when %(null_coop_tmpf)s is null then null
        else coalesce(%(coop_tmpf)s, coop_tmpf) end,
    coop_valid = %(coop_valid)s,
    et_inch = %(et_inch)s,
    report = coalesce(%(report)s, report),
    max_rh = case when %(null_max_rh)s is null then null
        else greatest(%(max_rh)s, %(relh)s, max_rh) end,
    min_rh = case when %(null_min_rh)s is null then null
        else least(%(min_rh)s, %(relh)s, min_rh) end,
    max_rstage = case when %(null_max_rstage)s is null then null
        else greatest(%(max_rstage)s, %(rstage)s, max_rstage) end,
    min_rstage = case when %(null_min_rstage)s is null then null
        else least(%(min_rstage)s, %(rstage)s, min_rstage) end,
    srad_mj = %(srad_mj)s,
    avg_sknt = case when %(null_avg_sknt)s is null then null
        else coalesce(%(avg_sknt)s, avg_sknt) end,
    vector_avg_drct = case when %(null_vector_avg_drct)s is null then null
        else coalesce(%(vector_avg_drct)s, vector_avg_drct) end
    WHERE s.iemid = %(iemid)s and s.day = {dateconst}
    """
    txn.execute(sql, data)
    return txn.rowcount


class Observation:
    """my observation object"""

    def __init__(self, station, network, valid):
        """
        Constructor for the Observation
        @param station is a string of the station ID
        @param network is a string of the network for this station
        @param valid is a datetime object with tzinfo set or date.
        """
        # This is somewhat hacky to ensure that we *only* get date objects
        # to trigger the isdaily logic
        isdaily = valid.__class__.__name__ == "date"
        if not isdaily and getattr(valid, "tzinfo", None) is None:
            warnings.warn("tzinfo is not set on valid, defaulting to UTC")
            if isinstance(valid, np.datetime64):
                valid = pd.Timestamp(valid).to_pydatetime()
            valid = valid.replace(tzinfo=timezone.utc)
        self.data = ObDict(
            {
                "station": station,
                "network": network,
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
            self.data["sknt"],
        ]:
            self.data["feel"] = bounded(
                mcalc.apparent_temperature(
                    self.data["tmpf"] * munits.degF,
                    self.data["relh"] * munits.percent,
                    self.data["sknt"] * munits.knots,
                    mask_undefined=False,  # less confusion this way
                )
                .to(munits.degF)
                .magnitude,
                -150.0,
                200.0,
            )

    def compute_iemid(self, txn):
        """Load in what our metadata is to save future queries"""
        if "iemid" in self.data:
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
        self.data["iemid"] = row[0]
        self.data["tzname"] = row[1]
        return True

    def save(self, txn, force_current_log=False, skip_current=False):
        """
        Save this observation to the database via a psycopg2 transaction
        @param txn is a psycopg2 transaction
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
        indoor_tmpf = %(indoor_tmpf)s,  tsf0 = %(tsf0)s,  tsf1 = %(tsf1)s,
        tsf2 = %(tsf2)s,  tsf3 = %(tsf3)s,  rwis_subf = %(rwis_subf)s,
        scond0 = %(scond0)s,  scond1 = %(scond1)s,  scond2 = %(scond2)s,
        scond3 = %(scond3)s,  pday = %(pday)s,  c1smv = %(c1smv)s,
        c2smv = %(c2smv)s,  c3smv = %(c3smv)s,  c4smv = %(c4smv)s,
        c5smv = %(c5smv)s,  c1tmpf = %(c1tmpf)s,  c2tmpf = %(c2tmpf)s,
        c3tmpf = %(c3tmpf)s,  c4tmpf = %(c4tmpf)s,  c5tmpf = %(c5tmpf)s,
        pres = %(pres)s,  relh = %(relh)s,  srad = %(srad)s,  vsby = %(vsby)s,
        phour = %(phour)s,  gust = %(gust)s,  raw = %(raw)s,  alti = %(alti)s,
        mslp = %(mslp)s,  qc_tmpf = %(qc_tmpf)s,  qc_dwpf = %(qc_dwpf)s,
        rstage = %(rstage)s,  ozone = %(ozone)s,  co2 = %(co2)s,
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
        snowdepth = %(snowdepth)s,
        updated = now()
        WHERE c.iemid = %(iemid)s and %(valid)s >= c.valid """
        if not self.data["_isdaily"] and not skip_current:
            txn.execute(sql, self.data)
        if skip_current or (force_current_log and txn.rowcount == 0):
            sql = """INSERT into current_log
            (iemid, tmpf, dwpf, drct, sknt, indoor_tmpf,
            tsf0, tsf1, tsf2, tsf3, rwis_subf, scond0, scond1, scond2, scond3,
            valid, pday, c1smv, c2smv, c3smv, c4smv, c5smv, c1tmpf, c2tmpf,
            c3tmpf, c4tmpf, c5tmpf, pres, relh, srad, vsby, phour, gust, raw,
            alti, mslp, qc_tmpf, qc_dwpf, rstage, ozone, co2, pmonth, skyc1,
            skyc2, skyc3, skyc4, skyl1, skyl2, skyl3, skyl4, pcounter,
            discharge, p03i, p06i, p24i, max_tmpf_6hr, min_tmpf_6hr,
            max_tmpf_24hr, min_tmpf_24hr, wxcodes, battery,
            ice_accretion_1hr, ice_accretion_3hr, ice_accretion_6hr,
            water_tmpf, feel, peak_wind_gust, peak_wind_drct,
            peak_wind_time, snowdepth) VALUES(
            %(iemid)s, %(tmpf)s, %(dwpf)s, %(drct)s, %(sknt)s,
            %(indoor_tmpf)s, %(tsf0)s, %(tsf1)s, %(tsf2)s, %(tsf3)s,
            %(rwis_subf)s, %(scond0)s, %(scond1)s, %(scond2)s, %(scond3)s,
            %(valid)s, %(pday)s, %(c1smv)s, %(c2smv)s, %(c3smv)s, %(c4smv)s,
            %(c5smv)s, %(c1tmpf)s, %(c2tmpf)s, %(c3tmpf)s, %(c4tmpf)s,
            %(c5tmpf)s, %(pres)s, %(relh)s, %(srad)s, %(vsby)s, %(phour)s,
            %(gust)s, %(raw)s, %(alti)s, %(mslp)s, %(qc_tmpf)s, %(qc_dwpf)s,
            %(rstage)s, %(ozone)s, %(co2)s, %(pmonth)s, %(skyc1)s,
            %(skyc2)s, %(skyc3)s, %(skyc4)s, %(skyl1)s, %(skyl2)s, %(skyl3)s,
            %(skyl4)s, %(pcounter)s, %(discharge)s, %(p03i)s, %(p06i)s,
            %(p24i)s, %(max_tmpf_6hr)s, %(min_tmpf_6hr)s,
            %(max_tmpf_24hr)s, %(min_tmpf_24hr)s, %(wxcodes)s,
            %(battery)s,
            %(ice_accretion_1hr)s, %(ice_accretion_3hr)s,
            %(ice_accretion_6hr)s,
            %(water_tmpf)s, %(feel)s, %(peak_wind_gust)s, %(peak_wind_drct)s,
            %(peak_wind_time)s, %(snowdepth)s
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
