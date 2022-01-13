"""See which colors we don't have covered."""

from pyiem.nws.vtec import NWS_COLORS, get_ps_string
from pyiem.util import get_dbconn


def main():
    """Go."""
    pgconn = get_dbconn("postgis")
    cursor = pgconn.cursor()
    # Old stuff may not have colors anymore...
    cursor.execute(
        "SELECT phenomena, significance, count(*) from warnings "
        "WHERE issue > '2020-01-01' "
        "GROUP by phenomena, significance ORDER by count DESC"
    )
    for row in cursor:
        key = f"{row[0]}.{row[1]}"
        if key not in NWS_COLORS:
            print(f"{get_ps_string(row[0], row[1])}({key}) count:{row[2]}")


if __name__ == "__main__":
    main()
