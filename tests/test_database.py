"""Testing of pyiem.database"""
# pylint: disable=cell-var-from-loop

# third party
import pytest
import psycopg2
from pyiem import database


def test_get_dbconn_for_user(monkeypatch):
    """Test this works."""
    for ins, outs in zip(
        ["apache", "akrherz", "mesonet_ldm", "xyz"],
        ["nobody", "mesonet", "ldm", "xyz"],
    ):
        monkeypatch.setattr("getpass.getuser", lambda: ins)
        res = database.get_dbconnstr("bogus")
        assert res.find(outs) > 0


def test_get_sqlalchemy():
    """Test that we can do a contextmanager with this API."""
    with database.get_sqlalchemy_conn("coop") as conn:
        assert conn is not None


@pytest.mark.parametrize("dbname", ["mos", "hads", "iemre", "postgis"])
def test_get_dbconn(dbname):  # noqa
    """Does our code work for various database names."""
    pgconn = database.get_dbconn(dbname)
    assert pgconn is not None


def test_get_dbconn_bad():
    """Test that we raise a warning."""
    with pytest.warns(
        UserWarning, match="database connection failure"
    ), pytest.raises(psycopg2.OperationalError):
        database.get_dbconn("bogus")


def test_get_dbconn_failover():
    """See if failover works?"""
    with pytest.warns(
        UserWarning, match="database connection failure"
    ), pytest.raises(psycopg2.OperationalError):
        database.get_dbconn("mesosite", host="b")
