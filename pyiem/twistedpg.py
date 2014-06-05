"""
module twistedpg.py
Author: Federico Di Gregorio
http://twistedmatrix.com/pipermail/twisted-python/2006-April/012955.html
"""

from psycopg2 import *
from psycopg2 import connect as _2connect
from psycopg2.extensions import connection as _2connection
from psycopg2.extras import RealDictCursor

del connect
def connect(*args, **kwargs):
    kwargs['connection_factory'] = connection
    return _2connect(*args, **kwargs)

class connection(_2connection):
    def cursor(self):
        return _2connection.cursor(self, cursor_factory=RealDictCursor)
