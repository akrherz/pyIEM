"""A class representing an observation stored in the IEM database"""
import warnings
import datetime
import math

import metpy.calc as mcalc
from metpy.units import units as munits
import pytz

# Not including iemid, valid
CURRENT_COLS = ['tmpf', 'dwpf', 'drct', 'sknt', 'indoor_tmpf', 'tsf0', 'tsf1',
                'tsf2', 'tsf3', 'rwis_subf', 'scond0', 'scond1', 'scond2',
                'scond3', 'pday', 'c1smv', 'c2smv', 'c3smv', 'c4smv', 'c5smv',
                'c1tmpf', 'c2tmpf', 'c3tmpf', 'c4tmpf', 'c5tmpf', 'pres',
                'relh', 'srad', 'vsby', 'phour', 'gust', 'raw', 'alti',
                'mslp', 'qc_tmpf', 'qc_dwpf', 'rstage', 'ozone', 'co2',
                'pmonth', 'skyc1', 'skyc2', 'skyc3', 'skyc4', 'skyl1', 'skyl2',
                'skyl3', 'skyl4', 'pcounter', 'discharge', 'p03i', 'p06i',
                'p24i', 'max_tmpf_6hr', 'min_tmpf_6hr', 'max_tmpf_24hr',
                'min_tmpf_24hr', 'battery', 'water_tmpf',
                'ice_accretion_1hr', 'ice_accretion_3hr', 'ice_accretion_6hr',
                'wxcodes', 'feel', 'peak_wind_gust', 'peak_wind_drct',
                'peak_wind_time']

# Not including iemid, day
SUMMARY_COLS = ['max_tmpf', 'min_tmpf', 'max_sknt', 'max_gust', 'max_sknt_ts',
                'max_gust_ts', 'max_dwpf', 'min_dwpf', 'pday', 'pmonth',
                'snow', 'snowd', 'max_tmpf_qc', 'min_tmpf_qc', 'pday_qc',
                'snow_qc', 'snoww', 'max_drct', 'max_srad', 'coop_tmpf',
                'coop_valid', 'et_inch', 'srad_mj', 'max_water_tmpf',
                'min_water_tmpf', 'max_rh', 'min_rh', 'avg_sknt',
                'vector_avg_drct', 'min_feel', 'avg_feel', 'max_feel']


def bounded(val, floor, ceiling):
    """Make sure this is not NaN and between some value."""
    val = float(val)
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
    sql = """UPDATE summary s SET
    max_water_tmpf = coalesce(%(max_water_tmpf)s,
        greatest(max_water_tmpf, %(water_tmpf)s)),
    min_water_tmpf = coalesce(%(min_water_tmpf)s,
        least( min_water_tmpf, %(water_tmpf)s)),
    max_tmpf = coalesce(%(max_tmpf)s,
        greatest(max_tmpf, %(tmpf)s)),
    max_dwpf = coalesce(%(max_dwpf)s,
        greatest(max_dwpf, %(dwpf)s)),
    min_tmpf = coalesce(%(min_tmpf)s,
        least(min_tmpf, %(tmpf)s)),
    min_dwpf = coalesce(%(min_dwpf)s,
        least(min_dwpf, %(dwpf)s)),
    min_feel = coalesce(%(min_feel)s,
        least(min_feel, %(feel)s)),
    max_feel = coalesce(%(max_feel)s,
        greatest(max_feel, %(feel)s)),
    max_sknt = greatest(%(max_sknt)s, max_sknt, %(sknt)s),
    max_gust = greatest(%(max_gust)s, max_gust, %(gust)s),
    max_sknt_ts = (CASE WHEN %(sknt)s > max_sknt or %(max_sknt)s > max_sknt
        or (max_sknt is null and %(sknt)s > 0)
        THEN coalesce(%(max_sknt_ts)s, %(valid)s)::timestamptz
        ELSE max_sknt_ts END),
    max_gust_ts = (CASE WHEN %(gust)s > max_gust or %(max_gust)s > max_gust
        or (max_gust is null and %(gust)s > 0)
        THEN coalesce(%(max_gust_ts)s, %(valid)s)::timestamptz
        ELSE max_gust_ts END),
    pday = coalesce(%(pday)s, pday),
    pmonth = coalesce(%(pmonth)s, pmonth),
    snow = coalesce(%(snow)s, snow),
    snowd = coalesce(%(snowd)s, snowd),
    snoww = coalesce(%(snoww)s, snoww),
    max_drct = coalesce(%(max_drct)s, max_drct),
    max_srad = coalesce(%(max_srad)s, max_srad),
    coop_tmpf = coalesce(%(coop_tmpf)s, coop_tmpf),
    coop_valid = %(coop_valid)s, et_inch = %(et_inch)s,
    max_rh = greatest(%(max_rh)s, %(relh)s, max_rh),
    min_rh = least(%(min_rh)s, %(relh)s, min_rh),
    srad_mj = %(srad_mj)s,
    avg_sknt = coalesce(%(avg_sknt)s, avg_sknt),
    vector_avg_drct = coalesce(%(vector_avg_drct)s, vector_avg_drct)
    WHERE s.iemid = %(iemid)s and
    s.day = date(%(valid)s at time zone %(tzname)s)
    """
    txn.execute(sql, data)
    return txn.rowcount


class Observation(object):
    """ my observation object """

    def __init__(self, station, network, valid):
        """
        Constructor for the Observation
        @param station is a string of the station ID
        @param network is a string of the network for this station
        @param valid is a datetime object with tzinfo set
        """
        if valid.tzinfo is None:
            warnings.warn("tzinfo is not set on valid, defaulting to UTC")
            valid = valid.replace(tzinfo=pytz.UTC)
        self.data = {'station': station,
                     'network': network,
                     'valid': valid,
                     }
        for col in CURRENT_COLS:
            self.data[col] = None
        for col in SUMMARY_COLS:
            self.data[col] = None

    def load(self, txn):
        """
        Load the current observation for this site and time
        """
        if not self.compute_iemid(txn):
            return False
        sql = """SELECT * from current c, summary s WHERE
        s.iemid = c.iemid and s.iemid = %(iemid)s and
        s.day = date(%(valid)s at time zone %(tzname)s) and
        c.valid = %(valid)s"""
        txn.execute(sql, self.data)
        if txn.rowcount < 1:
            return False
        row = txn.fetchone()
        for key in row.keys():
            if key not in ['valid', ]:
                self.data[key] = row[key]
        return True

    def calc(self):
        """Compute things not usually computed"""
        if (self.data['relh'] is None and
                None not in [self.data['tmpf'], self.data['dwpf']]):
            self.data['relh'] = bounded(mcalc.relative_humidity_from_dewpoint(
                self.data['tmpf'] * munits.degF,
                self.data['dwpf'] * munits.degF
            ).to(munits.percent).magnitude, 0.5, 100.5)
        if (self.data['dwpf'] is None and
                None not in [self.data['tmpf'], self.data['relh']] and
                self.data['relh'] >= 1 and self.data['relh'] <= 100):
            self.data['dwpf'] = bounded(mcalc.dewpoint_rh(
                self.data['tmpf'] * munits.degF,
                self.data['relh'] * munits.percent
            ).to(munits.degF).magnitude, -100., 100.)
        if (self.data['feel'] is None and
                None not in [self.data['tmpf'], self.data['relh'],
                             self.data['sknt']]):
            self.data['feel'] = bounded(mcalc.apparent_temperature(
                 self.data['tmpf'] * munits.degF,
                 self.data['relh'] * munits.percent,
                 self.data['sknt'] * munits.knots
            ).to(munits.degF).magnitude, -150., 200.)

    def compute_iemid(self, txn):
        """Load in what our metadata is to save future queries"""
        if 'iemid' in self.data:
            return True
        txn.execute("""
        SELECT iemid, tzname from stations where id = %(station)s and
        network = %(network)s
        """, self.data)
        if txn.rowcount == 0:
            return False
        row = txn.fetchone()
        self.data['iemid'] = row[0]
        self.data['tzname'] = row[1]
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
        peak_wind_time = %(peak_wind_time)s
        WHERE c.iemid = %(iemid)s and %(valid)s >= c.valid """
        if not skip_current:
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
            peak_wind_time) VALUES(
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
            %(peak_wind_time)s
            )
            """
            txn.execute(sql, self.data)

        rowcount = summary_update(txn, self.data)
        if rowcount != 1:
            # Create a new entry
            localvalid = self.data['valid'].astimezone(
                pytz.timezone(self.data['tzname']))
            # we don't want dates into the future as this will foul up others
            if localvalid.date() > datetime.date.today():
                return False
            txn.execute("""
                INSERT into summary_""" + str(localvalid.year) + """
                (iemid, day) VALUES (%s, %s)
            """, (self.data['iemid'], localvalid.date()))
            # try once more
            rowcount = summary_update(txn, self.data)
            if rowcount != 1:
                return False

        return True
