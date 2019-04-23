"""Unit tests for our ftpsession client"""
from mock import patch

from pyiem.ftpsession import FTPSession


@patch('pyiem.ftpsession.FTP_TLS')
def test_simple(mockftp):
    """Walk, before we run with tests"""
    mock_ftp_obj = mockftp()
    session = FTPSession('bogus', 'bogus', 'bogus')
    session.pwd()
    assert mock_ftp_obj.login.called
    session.close()
    assert session.conn is None
