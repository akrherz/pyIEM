"""See if we can do stuff with the network"""
# stdlib
from datetime import date

import pytest
from pyiem import network


def create_entries(cursor):
    """With each test"""
    iemid = {}
    for station in ["BOGUS", "BOGUS2", "BOGUS3"]:
        cursor.execute(
            """
            INSERT into stations(id, name, network, online)
            VALUES (%s, 'BOGUS NAME', 'BOGUS', 't')
            RETURNING iemid
        """,
            (station,),
        )
        iemid[station] = cursor.fetchone()[0]
    cursor.execute(
        """
        INSERT into station_attributes(iemid, attr, value)
        VALUES (%s, 'A', 'AA'), (%s, 'B', 'BB')
    """,
        (iemid["BOGUS"], iemid["BOGUS"]),
    )
    args1 = (iemid["BOGUS"], iemid["BOGUS2"], "1893-01-01", "1999-12-31")
    args2 = (iemid["BOGUS"], iemid["BOGUS3"], "1999-12-31", "2021-01-01")
    cursor.execute(
        """
        INSERT into station_threading(iemid, source_iemid, begin_date,
        end_date) VALUES (%s, %s, %s, %s), (%s, %s, %s, %s)
    """,
        (*args1, *args2),
    )
    cursor.execute(
        """
        INSERT into stations(id, name, network, online)
        VALUES ('BOGUS3', 'BOGUS3 NAME', 'BOGUS2', 'f')
    """
    )


@pytest.mark.parametrize("database", ["mesosite"])
def test_basic(dbcursor):
    """basic test of constructor"""
    create_entries(dbcursor)
    nt = network.Table("BOGUS", cursor=dbcursor)
    assert len(nt.sts.keys()) == 3

    nt = network.Table(["BOGUS", "BOGUS2"], cursor=dbcursor)
    assert len(nt.sts.keys()) == 3

    nt = network.Table(["BOGUS", "BOGUS2"], cursor=dbcursor, only_online=False)
    assert len(nt.sts.keys()) == 3

    assert nt.sts["BOGUS"]["name"] == "BOGUS NAME"
    assert len(nt.sts["BOGUS"]["attributes"]) == 2
    assert not nt.sts["BOGUS2"]["attributes"]

    # kind of a lame test here without the local cursor
    nt = network.Table(["BOGUS", "BOGUS2"])
    assert not nt.sts.keys()

    nt = network.Table("BOGUS2", cursor=dbcursor)
    assert not nt.sts.keys()

    nt = network.Table("BOGUS", cursor=dbcursor)
    assert nt.get_threading_id("BOGUS", date(2000, 1, 1)) == "BOGUS3"
    assert nt.get_threading_id("BOGUS", date(2040, 1, 1)) is None
    assert nt.get_threading_id("AAA", date(2040, 1, 1)) is None
    assert nt.get_id_by_key("wont work", "ha") is None
