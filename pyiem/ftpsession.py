"""FTP Session"""
from ftplib import FTP_TLS  # requires python 2.7
import netrc
import logging
import os
import glob
import subprocess
import time

from pyiem.util import exponential_backoff


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
        except Exception as exp:
            logging.debug(exp)
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
                                     open(filename, 'rb'))
                os.unlink(filename)
        else:
            logging.debug("_put '%s' to '%s'",
                          localfn, remotefn)
            self.conn.storbinary('STOR %s' % (remotefn, ), open(localfn, 'rb'))
        return True

    def close(self):
        """ Good bye """
        try:
            self.conn.quit()
            self.conn.close()
        except Exception as exp:
            logging.debug(exp)
        finally:
            self.conn = None

    def chdir(self, path):
        """Change directory

        Args:
          path (str): The path (relative or absolute to change to
        """
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

    Returns:
      FTPSession
      list of success `True` or failures `False` matching filenames
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
    res = fs.put_files(remote_path, filenames, remotenames)
    return fs, res
