"""Test pyiem.tracker."""
# pylint: disable=redefined-outer-name
import datetime
from datetime import timezone

import pytest
from pyiem.tracker import TrackerEngine, loadqc
from pyiem.network import Table as NetworkTable
from pyiem.util import get_dbconn


@pytest.fixture
def pcursor():
    """Database cursor."""
    dbconn = get_dbconn("portfolio")
    return dbconn.cursor()


@pytest.fixture
def icursor():
    """Database cursor."""
    dbconn = get_dbconn("iem")
    return dbconn.cursor()


def test_loadqc(pcursor):
    """Make sure we exercise the loadqc stuff"""
    q = loadqc()
    assert not q
    q = loadqc(cursor=pcursor)
    assert not q
    pcursor.execute(
        """
        INSERT into tt_base(s_mid, sensor, status, entered) VALUES
        ('BOGUS', 'tmpf', 'OPEN', '2019-03-27')
    """
    )
    q = loadqc(cursor=pcursor, date=datetime.date(2019, 3, 27))
    assert q


def test_workflow(pcursor, icursor):
    """Test that we can do stuff!"""
    sid1 = "XXX"
    sid2 = "YYY"
    pnetwork = "xxxxxx"
    nt = NetworkTable(None)
    nt.sts[sid1] = dict(
        name="XXX Site Name", network="IA_XXXX", tzname="America/Chicago"
    )
    nt.sts[sid2] = dict(
        name="YYY Site Name", network="IA_XXXX", tzname="America/Chicago"
    )
    valid = datetime.datetime.utcnow()
    valid = valid.replace(tzinfo=timezone.utc)
    threshold = valid - datetime.timedelta(hours=3)
    obs = {
        sid1: {"valid": valid},
        sid2: {"valid": valid - datetime.timedelta(hours=6)},
    }
    # Create dummy iem_site_contacts
    pcursor.execute(
        """
        INSERT into iem_site_contacts
        (portfolio, s_mid, email) VALUES (%s, %s, %s)
    """,
        (pnetwork, sid1, "akrherz@localhost"),
    )
    pcursor.execute(
        """
        INSERT into iem_site_contacts
        (portfolio, s_mid, email) VALUES (%s, %s, %s)
    """,
        (pnetwork, sid2, "root@localhost"),
    )
    # Create some dummy tickets
    pcursor.execute(
        """
        INSERT into tt_base (portfolio, s_mid, subject,
        status, author) VALUES (%s, %s, %s, %s, %s) RETURNING id
    """,
        (pnetwork, sid1, "FIXME PLEASE OPEN", "OPEN", "mesonet"),
    )
    pcursor.execute(
        """
        INSERT into tt_base (portfolio, s_mid, subject,
        status, author) VALUES (%s, %s, %s, %s, %s) RETURNING id
    """,
        (pnetwork, sid1, "FIXME PLEASE CLOSED", "CLOSED", "mesonet"),
    )
    tracker = TrackerEngine(icursor, pcursor)
    tracker.process_network(obs, pnetwork, nt, threshold)
    tracker.send_emails(really_send=False)
    assert len(tracker.emails) == 1

    tracker.emails = {}
    obs[sid1]["valid"] = valid - datetime.timedelta(hours=6)
    obs[sid2]["valid"] = valid
    tracker.process_network(obs, pnetwork, nt, threshold)
    tracker.send_emails(really_send=False)
    assert len(tracker.emails) == 2

    tracker.emails = {}
    obs[sid1]["valid"] = valid - datetime.timedelta(hours=6)
    obs[sid2]["valid"] = valid
    tracker.process_network(obs, pnetwork, nt, threshold)
    tracker.send_emails(really_send=False)
    assert not tracker.emails
