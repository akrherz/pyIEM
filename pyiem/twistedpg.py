"""
module twistedpg.py
Author: Federico Di Gregorio
http://twistedmatrix.com/pipermail/twisted-python/2006-April/012955.html
"""

from psycopg2 import connect
from psycopg2 import connect as _2connect
from psycopg2.extensions import connection as _2connection
from psycopg2.extras import DictCursor

del connect


def connect(*args, **kwargs):
    """Proxy connect with an additional kwarg set"""
    kwargs["connection_factory"] = connection
    return _2connect(*args, **kwargs)


class connection(_2connection):
    def cursor(self):
        # DictCursor allows for both integer and key based row access
        return _2connection.cursor(self, cursor_factory=DictCursor)
