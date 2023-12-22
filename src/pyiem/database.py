"""Database helpers."""
# stdlib
import getpass
from contextlib import contextmanager

# third party
import numpy as np
import psycopg
from psycopg.adapt import Dumper
from psycopg.rows import dict_row
from sqlalchemy import create_engine

# NB: Careful of cyclic imports here...
from pyiem.exceptions import NewDatabaseConnectionFailure

# Map system users back to something supported by akrherz/iem-database repo
USERNAME_MAPPER = {
    "apache": "nobody",
    "www-data": "nobody",
    "akrherz": "mesonet",
    "meteor_ldm": "ldm",
}


class _FloatDumper(Dumper):
    """Prevent NaN from reaching the database."""

    def dump(self, obj):
        """Opinionated dumper."""
        if np.isnan(obj):
            return None
        return str(obj).encode()


# Adapters for Python to PostgreSQL
psycopg.adapters.register_dumper(float, _FloatDumper)
psycopg.adapters.register_dumper(np.float32, _FloatDumper)
psycopg.adapters.register_dumper(np.float64, _FloatDumper)
psycopg.adapters.register_dumper(np.int64, _FloatDumper)


def get_dbconnstr(name, **kwargs) -> str:
    """Create a database connection string/URI.

    Args:
      name (str): the database name to connect to.
      **kwargs: any additional arguments to pass to psycopg.connect
        user (str): the database user to connect as
        host (str): the database host to connect to
        port (int): the database port to connect to
        connect_timeout (int): Connection timeout in seconds, default 30.
    Returns:
      str
    """
    user = kwargs.get("user")
    if user is None:
        user = USERNAME_MAPPER.get(getpass.getuser(), getpass.getuser())
    host = kwargs.get("host")
    if host is None:
        host = f"iemdb-{name}.local"
    port = kwargs.get("port")
    if port is None:
        port = 5432

    # 15 seconds found to be a bit tight for local ISU congestion
    return (
        f"postgresql://{user}@{host}:{port}/{name}?"
        f"connect_timeout={kwargs.get('connect_timeout', 30)}&"
        f"gssencmode={kwargs.get('gssencmode', 'disable')}&"
    )


def get_dbconn(database="mesosite", user=None, host=None, port=5432, **kwargs):
    """Helper function with business logic to get a database connection

    Note that this helper could return a read-only database connection if the
    connection to the primary server fails.

    Args:
      database (str,optional): the database name to connect to.
        default: mesosite
      user (str,optional): hard coded user to connect as, default: current user
      host (str,optional): hard coded hostname to connect as,
        default: iemdb.local
      port (int,optional): the TCP port that PostgreSQL is listening
        defaults to 5432
      password (str,optional): the password to use.

    Returns:
      psycopg database connection
    """
    dsn = get_dbconnstr(database, user=user, host=host, port=port, **kwargs)
    attempt = 0
    conn = None
    while attempt < 3:
        attempt += 1
        try:
            conn = psycopg.connect(dsn)
            # FIXME make this opinionated to return a default row_factory
            # conn.row_factory = dict_row
            break
        except Exception as exp:
            if attempt == 3:
                raise NewDatabaseConnectionFailure(str(exp)) from exp
    return conn


def get_dbconnc(
    database="mesosite", user=None, host=None, cursor_name=None, **kwargs
):
    """Helper function to get a database connection + dict_row cursor.

    Note that this helper could return a read-only database connection if the
    connection to the primary server fails.

    Args:
      database (str,optional): the database name to connect to.
        default: mesosite
      user (str,optional): hard coded user to connect as, default: current user
      host (str,optional): hard coded hostname to connect as,
        default: iemdb.local
      cursor_name (str,optional): name of the cursor to create
      port (int,optional): the TCP port that PostgreSQL is listening
        defaults to 5432
      password (str,optional): the password to use.

    Returns:
      psycopg2 database connection
      psycopg2 database cursor
    """
    conn = get_dbconn(database, user=user, host=host, **kwargs)
    conn.row_factory = dict_row
    return conn, conn.cursor(cursor_name)


@contextmanager
def get_sqlalchemy_conn(text, **kwargs):
    """An auto-disposing sqlalchemy context-manager helper.

    This is used for when we really do not want to manage having pools of
    database connections open.  So this isn't something that is fast!

    Args:
        text (str): the database to connect to, passed to get_dbconnstr
        **kwargs: any additional arguments to pass to get_dbconnstr
    """
    # Le Sigh
    connstr = get_dbconnstr(text, **kwargs).replace(
        "postgresql",
        "postgresql+psycopg",
    )
    engine = create_engine(connstr)
    try:
        # Unsure if this is trouble or not.
        with engine.connect() as conn:
            yield conn
    finally:
        engine.dispose()
