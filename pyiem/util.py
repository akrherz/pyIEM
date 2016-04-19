# -*- coding: utf-8 -*-
"""Utility functions for pyIEM package

This module contains utility functions used by various parts of the codebase.
"""
import sys
import psycopg2
import netrc
from ftplib import FTP_TLS  # requires python 2.7
import time
import random
import os
import logging
from socket import error as socket_error
from pyiem.ftpsession import FTPSession


def exponential_backoff(func, *args, **kwargs):
    """ Exponentially backoff some function until it stops erroring"""
    msgs = []
    for i in range(5):
        try:
            return func(*args, **kwargs)
        except socket_error as serr:
            msgs.append("%s/5 %s traceback: %s" % (i+1, func.__name__, serr))
            time.sleep((2 ** i) + (random.randint(0, 1000) / 1000))
        except Exception, exp:
            msgs.append("%s/5 %s traceback: %s" % (i+1, func.__name__, exp))
            time.sleep((2 ** i) + (random.randint(0, 1000) / 1000))
        except:
            msgs.append("%s/5 uncaught exception, exiting!" % (i+1, ))
            break
    sys.stderr.write("\n".join(msgs) + "\n")
    return None


def mirror2box(local_path, remote_path, ftpserver='ftp.box.com',
               tmpdir='/tmp'):
    """Mirror logic to sync a directory to CyBox

    Up until this, I was using `lftp mirror` to make this happen, but it has
    some issues and can not automatically deal with 15+ GB files.

    Args:
      local_path (str): local directory to sync
      remote_path (str): remote directory to sync to
      ftpserver (str,optional): FTPS server to connect to
      tmpdir (str,optional): Where to write temporary files necessary to
        transfer 15+ GB files.
    """
    credentials = netrc.netrc().hosts[ftpserver]

    def _mirrordir(localdir, remotedir):
        """Do the mirror work for a given directory"""
        ftps = FTP_TLS(ftpserver)
        ftps.login(credentials[0], credentials[2])
        ftps.prot_p()

    basedir = None
    for root, dirs, files in os.walk(local_path, topdown=True):
        # Change Local Directory
        os.chdir(root)
        # Change Remote Directory


def send2box(filenames, remote_path, remotenames=None,
             ftpserver='ftp.box.com', tmpdir='/tmp', fs=None):
    """Send one or more files to CyBox

    Box has a filesize limit of 15 GB, so if we find any files larger than
    that, we shall split them into chunks prior to uploading.

    Args:
      filenames (str or list): filenames to upload
      remote_path (str): location to place the filenames
      remotenames (str or list): filenames to use on the remote FTP server
        should match size and type of filenames
      ftpserver (str): FTP server to connect to...
      tmpdir (str, optional): Temperary folder to if an individual file is over
        15 GB in size
    """
    credentials = netrc.netrc().hosts[ftpserver]
    if fs is None:
        fs = FTPSession(ftpserver, credentials[0], credentials[2],
                        tmpdir=tmpdir)
    if isinstance(filenames, str):
        filenames = [filenames, ]
    if remotenames is None:
        remotenames = filenames
    if isinstance(remotenames, str):
        remotenames = [remotenames, ]
    fs.put_files(remote_path, filenames, remotenames)
    return fs


def get_properties():
    """Fetch the properties set

    Returns:
      dict: a dictionary of property names and values (both str)
    """
    pgconn = psycopg2.connect(database='mesosite', host='iemdb', user='nobody')
    cursor = pgconn.cursor()
    cursor.execute("""SELECT propname, propvalue from properties""")
    res = {}
    for row in cursor:
        res[row[0]] = row[1]
    return res


def drct2text(drct):
    """Convert an degree value to text representation of direction.

    Args:
      drct (int or float): Value in degrees to convert to text

    Returns:
      str: String representation of the direction, could be `None`

    """
    if drct is None:
        return None
    # Convert the value into a float
    drct = float(drct)
    if drct > 360:
        return None
    text = None
    if drct >= 350 or drct < 13:
        text = "N"
    elif drct >= 13 and drct < 35:
        text = "NNE"
    elif drct >= 35 and drct < 57:
        text = "NE"
    elif drct >= 57 and drct < 80:
        text = "ENE"
    elif drct >= 80 and drct < 102:
        text = "E"
    elif drct >= 102 and drct < 127:
        text = "ESE"
    elif drct >= 127 and drct < 143:
        text = "SE"
    elif drct >= 143 and drct < 166:
        text = "SSE"
    elif drct >= 166 and drct < 190:
        text = "S"
    elif drct >= 190 and drct < 215:
        text = "SSW"
    elif drct >= 215 and drct < 237:
        text = "SW"
    elif drct >= 237 and drct < 260:
        text = "WSW"
    elif drct >= 260 and drct < 281:
        text = "W"
    elif drct >= 281 and drct < 304:
        text = "WNW"
    elif drct >= 304 and drct < 324:
        text = "NW"
    elif drct >= 324 and drct < 350:
        text = "NNW"
    return text


if __name__ == '__main__':
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    send2box(['util.py', 'plot.py'], '/bah1/bah2/', remotenames=['util2.py',
                                                                 'plot.py'])
    # mirror2box("/tmp/mytest", "mytest")
