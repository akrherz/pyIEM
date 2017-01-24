"""FTP Session"""
from ftplib import FTP_TLS  # requires python 2.7
import logging
import os
import glob
import subprocess
from socket import error as socket_error
import random
import time


def exponential_backoff(func, *args, **kwargs):
    """ Exponentially backoff some function until it stops erroring"""
    for i in range(5):
        try:
            return func(*args, **kwargs)
        except socket_error as serr:
            logging.debug("%s/5 %s traceback: %s", i+1, func.__name__, serr)
            time.sleep((2 ** i) + (random.randint(0, 1000) / 1000))
        except Exception as exp:
            logging.debug("%s/5 %s traceback: %s", i+1, func.__name__, exp)
            time.sleep((2 ** i) + (random.randint(0, 1000) / 1000))
    return None


class FTPSession(object):
    """ Attempt to create some robustness and performance to FTPing """

    def __init__(self, server, username, password, tmpdir='/tmp', timeout=60):
        """Build a FTP session """
        self.conn = None
        self.server = server
        self.username = username
        self.password = password
        self.tmpdir = tmpdir
        self.timeout = timeout

    def _connect(self):
        """Connect to FTP server """
        if self.conn is not None:
            return
        logging.debug('Creating new connection to server %s', self.server)
        not_connected = True
        attempt = 1
        while not_connected and attempt < 6:
            try:
                self.conn = FTP_TLS(self.server, timeout=self.timeout)
                self.conn.login(self.username, self.password)
                self.conn.prot_p()
                not_connected = False
            except Exception as exp:
                logging.debug(exp)
                time.sleep(5)
                self.close()
            attempt += 1
        if not_connected is True:
            raise Exception("Failed to make FTP connection after 5 tries!")

    def _reconnect(self):
        """ First attempt to shut down connection and then reconnect """
        logging.debug('_reconnect() was called...')
        try:
            self.conn.quit()
            self.conn.close()
        except:
            pass
        finally:
            self.conn = None
        self._connect()

    def _put(self, path, localfn, remotefn):
        """ """
        self.chdir(path)
        sz = os.path.getsize(localfn)
        if sz > 14000000000:
            # Step 1 Split this big file into 14GB chunks, each file will have
            # suffix .aa then .ab then .ac etc
            basefn = os.path.basename(localfn)
            cmd = "split --bytes=14000M %s %s/%s." % (localfn, self.tmpdir,
                                                      basefn)
            subprocess.call(cmd, shell=True, stderr=subprocess.PIPE)
            files = glob.glob("%s/%s.??" % (self.tmpdir, basefn))
            for filename in files:
                suffix = filename.split(".")[-1]
                self.conn.storbinary('STOR %s.%s' % (remotefn, suffix),
                                     open(filename))
                os.unlink(filename)
        else:
            logging.debug("_put '%s' to '%s'",
                          localfn, remotefn)
            self.conn.storbinary('STOR %s' % (remotefn, ), open(localfn))
        return True

    def close(self):
        """ Good bye """
        try:
            self.conn.quit()
            self.conn.close()
        except:
            pass
        finally:
            self.conn = None

    def chdir(self, path):
        if self.pwd() == path.rstrip("/"):
            return
        self.conn.cwd("/")
        for dirname in path.split("/"):
            if dirname == '':
                continue
            bah = []
            self.conn.retrlines('NLST', bah.append)
            if dirname not in bah:
                logging.debug("Creating directory '%s'", dirname)
                self.conn.mkd(dirname)
            logging.debug("Changing to directory '%s'", dirname)
            self.conn.cwd(dirname)

    def pwd(self):
        """ Low friction function to get connectivity """
        self._connect()
        pwd = exponential_backoff(self.conn.pwd)
        if pwd is None:
            self._reconnect()
            pwd = exponential_backoff(self.conn.pwd)
        logging.debug("pwd() is currently '%s'", pwd)
        return pwd

    def put_file(self, path, localfn, remotefn):
        """ Put the File """
        res = exponential_backoff(self._put, path, localfn, remotefn)
        if not res:
            self._reconnect()
            res = exponential_backoff(self._put, path, localfn, remotefn)
            if not res:
                logging.error("Double Failure to upload filename: '%s'",
                              localfn)
                return False
        return True

    def put_files(self, path, localfns, remotefns):
        """ Put the File """
        res = []
        for localfn, remotefn in zip(localfns, remotefns):
            res.append(self.put_file(path, localfn, remotefn))
        return res
