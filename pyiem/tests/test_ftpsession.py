"""Unit tests for our ftpsession client"""
import unittest
from mock import patch

from pyiem.ftpsession import FTPSession


class FTPSessionTest(unittest.TestCase):
    """Test, we shall"""

    @patch('pyiem.ftpsession.FTP_TLS')
    def test_simple(self, mockftp):
        """Walk, before we run with tests"""
        mock_ftp_obj = mockftp()
        session = FTPSession('bogus', 'bogus', 'bogus')
        session.pwd()
        assert mock_ftp_obj.login.called
        session.close()
        self.assertTrue(session.conn is None)
