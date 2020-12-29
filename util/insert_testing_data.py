"""Create some data for the scripts to chomp on."""
import datetime

from pyiem.util import get_dbconn, utc


def asos():
    """Create some ASOS data entries."""
    pgconn = get_dbconn("asos")
    cursor = pgconn.cursor()
    basevalid = utc(2015, 1, 1, 6)
    for s in range(360):
        valid = basevalid + datetime.timedelta(hours=s)
        # Keep the max speed at ~24kts
        sknt = s / 13.0
        drct = s
        cursor.execute(
            f"INSERT into t{valid.year} (station, valid, sknt, drct, "
            "report_type) VALUES ('AMW2', %s, %s, %s, 2)",
            (valid, sknt, drct),
        )
    cursor.close()
    pgconn.commit()


def main():
    """Go Main Go."""
    asos()


if __name__ == "__main__":
    main()
