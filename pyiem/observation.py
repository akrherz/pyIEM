"""A class representing an observation stored in the IEM database"""
import warnings

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
                'min_tmpf_24hr', 'presentwx', 'battery', 'water_tmpf']

# Not including iemid, day
SUMMARY_COLS = ['max_tmpf', 'min_tmpf', 'max_sknt', 'max_gust', 'max_sknt_ts',
                'max_gust_ts', 'max_dwpf', 'min_dwpf', 'pday', 'pmonth',
                'snow', 'snowd', 'max_tmpf_qc', 'min_tmpf_qc', 'pday_qc',
                'snow_qc', 'snoww', 'max_drct', 'max_srad', 'coop_tmpf',
                'coop_valid', 'et_inch', 'srad_mj', 'max_water_tmpf',
                'min_water_tmpf', 'max_rh', 'min_rh']


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
            valid = valid.replace(tzinfo=pytz.utc)
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
        sql = """SELECT * from current c, summary s, stations t WHERE
        t.iemid = s.iemid and s.iemid = c.iemid and t.id = %(station)s and
        t.network = %(network)s and
        s.day = date(%(valid)s at time zone t.tzname) and
        c.valid = %(valid)s"""
        txn.execute(sql, self.data)
        if txn.rowcount < 1:
            return False
        row = txn.fetchone()
        for key in row.keys():
            if key not in ['valid', ]:
                self.data[key] = row[key]
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
        min_tmpf_24hr = %(min_tmpf_24hr)s,  presentwx = %(presentwx)s,
        battery = %(battery)s, water_tmpf = %(water_tmpf)s, valid = %(valid)s
        FROM stations t WHERE t.iemid = c.iemid and t.id = %(station)s
        and t.network = %(network)s and %(valid)s >= c.valid """
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
            max_tmpf_24hr, min_tmpf_24hr, presentwx, battery,
            water_tmpf) VALUES(
            (SELECT iemid from stations where id = %(station)s and
            network = %(network)s), %(tmpf)s, %(dwpf)s, %(drct)s, %(sknt)s,
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
            %(max_tmpf_24hr)s, %(min_tmpf_24hr)s, %(presentwx)s,
            %(battery)s, %(water_tmpf)s
            )
            """
            txn.execute(sql, self.data)

        table = "summary_%s" % (self.data['valid'].year,)

        # Update summary table
        sql = """UPDATE """+table+""" s SET
max_water_tmpf = greatest(%(max_water_tmpf)s, max_water_tmpf, %(water_tmpf)s),
min_water_tmpf = least(%(min_water_tmpf)s, min_water_tmpf, %(water_tmpf)s),
        max_tmpf = greatest(%(max_tmpf)s, max_tmpf, %(tmpf)s),
        max_dwpf = greatest(%(max_dwpf)s, max_dwpf, %(dwpf)s),
        min_tmpf = least(%(min_tmpf)s, min_tmpf, %(tmpf)s),
        min_dwpf = least(%(min_dwpf)s, min_dwpf, %(dwpf)s),
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
        srad_mj = %(srad_mj)s
        FROM stations t WHERE t.iemid = s.iemid and
        s.day = date(%(valid)s at time zone t.tzname)
        and t.id = %(station)s and t.network = %(network)s"""
        txn.execute(sql, self.data)
        if txn.rowcount != 1:
            return False

        return True
