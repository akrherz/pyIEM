"""See if we can do stuff with the network"""

import pytest
from pyiem import network


def create_entries(cursor):
    """With each test"""
    cursor.execute(
        """
        INSERT into stations(id, name, network, online)
        VALUES ('BOGUS', 'BOGUS NAME', 'BOGUS', 't')
        RETURNING iemid
    """
    )
    iemid = cursor.fetchone()[0]
    cursor.execute(
        """
        INSERT into station_attributes(iemid, attr, value)
        VALUES (%s, 'A', 'AA'), (%s, 'B', 'BB')
    """,
        (iemid, iemid),
    )
    cursor.execute(
        """
        INSERT into stations(id, name, network, online)
        VALUES ('BOGUS2', 'BOGUS2 NAME', 'BOGUS', 't')
    """
    )
    cursor.execute(
        """
        INSERT into stations(id, name, network, online)
        VALUES ('BOGUS3', 'BOGUS3 NAME', 'BOGUS2', 'f')
    """
    )


@pytest.mark.parametrize("database", ["mesosite"])
def test_basic(dbcursor):
    """ basic test of constructor """
    create_entries(dbcursor)
    nt = network.Table("BOGUS", cursor=dbcursor)
    assert len(nt.sts.keys()) == 2

    nt = network.Table(["BOGUS", "BOGUS2"], cursor=dbcursor)
    assert len(nt.sts.keys()) == 2

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
