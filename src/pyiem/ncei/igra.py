"""Processing of NCEI IGRA2.2 data.

---------------------
Header Record Format:
---------------------

---------------------------------
Variable   Columns  Type
---------------------------------
HEADREC       1-  1  Character
ID            2- 12  Character
YEAR         14- 17  Integer
MONTH        19- 20  Integer
DAY          22- 23  Integer
HOUR         25- 26  Integer
RELTIME      28- 31  Integer
NUMLEV       33- 36  Integer
P_SRC        38- 45  Character
NP_SRC       47- 54  Character
LAT          56- 62  Integer
LON          64- 71  Integer
-------------------------------

---------------------
Data Record Format:
---------------------

-------------------------------
Variable        Columns Type
-------------------------------
LVLTYP1         1-  1   Integer
LVLTYP2         2-  2   Integer
ETIME           4-  8   Integer
PRESS          10- 15   Integer
PFLAG          16- 16   Character
GPH            17- 21   Integer
ZFLAG          22- 22   Character
TEMP           23- 27   Integer
TFLAG          28- 28   Character
RH             29- 33   Integer
DPDP           35- 39   Integer
WDIR           41- 45   Integer
WSPD           47- 51   Integer
-------------------------------
"""

from datetime import datetime, timedelta
from typing import Optional

from pydantic import ValidationError
from shapely.geometry import Point

from pyiem.models.igra import SoundingHeader, SoundingModel, SoundingRecord
from pyiem.reference import igra2icao
from pyiem.util import LOG, utc


class Sounding:
    """Encapsulate a sounding."""

    def __init__(self, header: SoundingHeader, records: list[SoundingRecord]):
        """Create a Sounding object."""
        self.model: SoundingModel = SoundingModel(
            header=header,
            records=records,
        )

    def sql(self, txn, overwrite=False):
        """Do the database insert.

        Args:
            txn (psycopg2.cursor): Database cursor
            overwrite (bool): Should we overwrite existing data?
        """
        icao = igra2icao[self.model.header.station]
        txn.execute(
            "select fid from raob_flights where station = %s and valid = %s",
            (icao, self.model.header.valid),
        )
        if txn.rowcount == 0:
            txn.execute(
                "INSERT into raob_flights(station, valid) VALUES (%s, %s) "
                "RETURNING fid",
                (icao, self.model.header.valid),
            )
        elif not overwrite:
            LOG.info(
                "Skipping %s[%s] as record exists",
                icao,
                self.model.header.valid,
            )
            return
        fid = txn.fetchone()["fid"]
        # Delete any existing data
        table = f"raob_profile_{self.model.header.valid.year}"
        txn.execute(
            f"DELETE from {table} where fid = %s",
            (fid,),
        )
        tropo_level = None
        for record in self.model.records:
            # levelcode came from the rucsounding days
            # 9 is surface data
            # 4 is mandatory level
            # 5 is unsure
            levelcode = 5
            if record.lvltyp2 == 1:
                levelcode = 9
            if record.lvltyp1 == 1:
                levelcode = 4
            if record.lvltyp2 == 2:  # tropopause
                tropo_level = record.press
            txn.execute(
                f"""
    INSERT into {table} (fid, ts, levelcode, pressure, height, tmpc, dwpc,
    drct, smps) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """,
                (
                    fid,
                    record.valid,
                    levelcode,
                    record.press,
                    record.gph,
                    record.temp,
                    record.dewp,
                    record.wdir,
                    record.wspd,
                ),
            )
        txn.execute(
            """
    UPDATE raob_flights SET release_time = %s, ingested_at = now(),
    tropo_level = %s, computed = 'f' WHERE fid = %s""",
            (self.model.header.release_valid, tropo_level, fid),
        )
        LOG.info(
            "Added %s records for %s[%s][fid:%s]",
            len(self.model.records),
            icao,
            self.model.header.valid,
            fid,
        )


def parse_header(text: str) -> SoundingHeader:
    """Compute all the things."""
    station = text[1:12].strip()
    year = int(text[13:17])
    month = int(text[18:20])
    day = int(text[21:23])
    hour = int(text[24:26])
    valid = utc(year, month, day, hour)
    rlshh = int(text[27:29])
    rlsmm = int(text[29:31])
    release_valid = valid
    if text[27:31] != "9999":
        release_valid = valid.replace(hour=rlshh, minute=rlsmm)
        if rlshh > hour:
            # Yesterday
            release_valid = release_valid - timedelta(hours=24)
    lat = int(text[55:62])
    lon = int(text[63:71])
    return SoundingHeader(
        station=station,
        valid=valid,
        release_valid=release_valid,
        p_src=text[37:45].strip(),
        np_src=text[46:54].strip(),
        geom=Point(lon, lat),
    )


def compute_time(release_valid: datetime, etime: str):
    """Compute the valid time."""
    # etime is MMMSS with a negative number being missing
    if etime[0] == "-":
        return None
    seconds = int(etime[-2:])
    minutes = 0
    if len(etime) > 2:
        minutes = int(etime[:-2])
    return release_valid + timedelta(minutes=minutes, seconds=seconds)


def convert_pressure(text: str) -> float:
    """Convert the pressure value."""
    pressure = float(text) / 100.0
    if pressure < 0:
        return None
    return pressure


def convert_height(text: str) -> int:
    """Convert the height value."""
    height = int(text)
    if height < 0:
        return None
    return height


def calc_dewp(tmpc: Optional[float], text: str) -> Optional[float]:
    """Compute the dewpoint from the dew point depression."""
    dpdp = convert_float(text)
    if tmpc is None or dpdp is None:
        return None
    return tmpc - dpdp


def convert_float(
    text: str, gt: Optional[float] = None, lt: Optional[float] = None
) -> Optional[float]:
    """Convert the temperature value."""
    val = float(text) / 10.0
    if (
        val < -100
        or (gt is not None and val <= gt)
        or (lt is not None and val >= lt)
    ):
        return None
    return val


def convert_wind(text: str) -> Optional[int]:
    """Convert the wind value."""
    wind = int(text)
    if wind < 0:
        return None
    return wind


def process_sounding(text: str) -> Sounding:
    """Process the IGRA sounding text."""
    header = None
    records = []
    for line in text.strip().split("\n"):
        if header is None:
            header = parse_header(line)
            continue
        tmpc = convert_float(line[22:27].strip())
        record = {
            "lvltyp1": int(line[0:1]),
            "lvltyp2": int(line[1:2]),
            "valid": compute_time(header.release_valid, line[3:8].strip()),
            "press": convert_pressure(line[9:15]),
            "pflag": line[15:16],
            "gph": convert_height(line[16:21].strip()),
            "zflag": line[21:22],
            "temp": tmpc,
            "tflag": line[27:28],
            "rh": convert_float(line[28:33].strip(), gt=0, lt=104),
            "dewp": calc_dewp(tmpc, line[34:39].strip()),
            "wdir": convert_wind(line[40:45].strip()),
            "wspd": convert_float(line[46:51].strip()),
        }
        try:
            records.append(SoundingRecord(**record))
        except ValidationError as exp:
            LOG.info("Record: %s failed valdiation: %s", record, exp)
    return Sounding(header, records)


def process_ytd(filename: str):
    """Process the YTD file on NCEI's webserver."""
    msg = ""
    with open(filename) as fh:
        for line in fh:
            if line.strip() == "":
                continue
            if line.startswith("#"):
                if msg:
                    yield process_sounding(msg)
                msg = line
            else:
                msg += line
    if msg:
        yield process_sounding(msg)
