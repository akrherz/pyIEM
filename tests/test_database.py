"""Testing of pyiem.database"""

# third party
import numpy as np
import pytest

from pyiem.database import (
    get_dbconn,
    get_dbconnc,
    get_dbconnstr,
    get_sqlalchemy_conn,
    sql_helper,
    with_sqlalchemy_conn,
)
from pyiem.exceptions import NewDatabaseConnectionFailure


def test_with_sqlalchemy_conn():
    """Test that we can do a contextmanager with this API."""

    @with_sqlalchemy_conn("coop")
    def foo(arg1, kwarg1=None, conn=None):
        assert arg1 == 1
        assert kwarg1 == 2
        assert conn is not None

    foo(1, kwarg1=2)


def test_sql_helper():
    """Test that we can do a contextmanager with this API."""
    sql = "SELECT * FROM {table} WHERE {limiter} state_abbr = :state"
    sql = sql_helper(sql, table="states", limiter="")
    assert str(sql).find(":state") > 0


def test_get_dbconnc_cursory_name():
    """Test getting with a cursor name set."""
    conn, cursor = get_dbconnc("mesosite", cursor_name="test")
    cursor.execute("SELECT 1 as test")
    assert cursor.rowcount == -1
    conn.close()


def test_get_dbconnc_cursory_noname():
    """Test getting with a cursor name set."""
    conn, cursor = get_dbconnc("mesosite")
    cursor.execute("SELECT 1 as test")
    assert cursor.rowcount == 1
    conn.close()


@pytest.mark.parametrize("database", ["coop"])
def test_dumper_float32(dbcursor):
    """Test that we can write a float32 to the database."""
    dbcursor.execute(
        "insert into alldata_ia(station, merra_srad) values (%s, %s) "
        "returning merra_srad",
        ("IA0000", np.float32(1.0)),
    )
    assert dbcursor.fetchone()["merra_srad"] == 1.0


def test_get_dbconn_for_user(monkeypatch):
    """Test this works."""
    for ins, outs in zip(
        ["apache", "akrherz", "mesonet_ldm", "xyz"],
        ["nobody", "mesonet", "ldm", "xyz"],
        strict=False,
    ):
        monkeypatch.setattr("getpass.getuser", lambda i=ins: i)
        res = get_dbconnstr("bogus")
        assert res.find(outs) > 0


def test_get_sqlalchemy():
    """Test that we can do a contextmanager with this API."""
    with get_sqlalchemy_conn("coop") as conn:
        assert conn is not None


@pytest.mark.parametrize("dbname", ["mos", "hads", "iemre", "postgis"])
def test_get_dbconn(dbname):  # noqa
    """Does our code work for various database names."""
    pgconn = get_dbconn(dbname)
    assert pgconn is not None


def test_get_dbconn_bad():
    """Test that we raise a warning."""
    with pytest.raises(NewDatabaseConnectionFailure):
        get_dbconn("bogus")


def test_get_dbconn_failover():
    """See if failover works?"""
    with pytest.raises(NewDatabaseConnectionFailure):
        get_dbconn("mesosite", host="b")
