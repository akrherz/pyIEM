import psycopg2
import psycopg2.extras

def get_cursor(conn):
    """ Get a cursor from this connection """
    return conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

def cnc(dbname, host='iemdb', user=None):
    """ Helper function that returns a connection and cursor! """
    dsn = "dbname=%s host=%s" % (dbname, host)
    if user:
        dsn += " user=%s" % (user,)
    conn = psycopg2.connect(dsn)
    curs = get_cursor(conn)
    return conn, curs