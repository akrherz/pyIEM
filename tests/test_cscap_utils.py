"""test cscap_utils."""
import tempfile
import os

from pyiem import cscap_utils as csu


def test_cleanvalue():
    """see what we can do with cleaning strings"""
    assert abs(10.54 - csu.cleanvalue("10.54%")) < 0.01
    assert csu.cleanvalue("Did NOt Collect") == "did not collect"
    assert csu.cleanvalue("<0.2") == "< 0.2"
    assert csu.cleanvalue(" ") is None
    assert csu.cleanvalue("NA") == "n/a"
    assert abs(csu.cleanvalue("10") - 10.0) < 0.0001
    csu.cleanvalue("QQQ")
    assert "QQQ" in csu.CLEANVALUE_COMPLAINED


def test_missing_config():
    """Test that we can deal with a missing file."""
    with tempfile.NamedTemporaryFile() as tmp:
        tmpfn = tmp.name
    csu.CONFIG_FN = tmpfn
    cfg = csu.get_config()
    assert cfg is None
    csu.save_config({})


def test_config():
    """Make sure we exercise the config logic as things get hairy"""
    (_, tmpfn) = tempfile.mkstemp()
    # create bogus config file
    cfg = dict(a="a", b="b")
    # Write config to bogus file
    csu.save_config(cfg, tmpfn)
    # Attempt to load it back now
    cfg = csu.get_config(tmpfn)
    assert cfg is not None
    os.unlink(tmpfn)


def test_translateyears():
    """See that we can translate years properly"""
    x = csu.translate_years("X ('07-'17)")
    assert x[0] == 2007
    x = csu.translate_years("X ('98-'06)")
    assert x[0] == 1998
    assert x[-1] == 2006
    x = csu.translate_years("X ('14, '15, '16, '17)")
    assert x[0] == 2014
    assert x[-1] == 2017
    x = csu.translate_years("X ('06)")
    assert x[0] == 2006
