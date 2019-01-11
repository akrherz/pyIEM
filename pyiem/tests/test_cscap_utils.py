"""test cscap_utils."""
import tempfile
import os

from pyiem.cscap_utils import (translate_years, get_config, save_config,
                               cleanvalue)


def test_cleanvalue():
    """ see what we can do with cleaning strings"""
    assert abs(10.54 - cleanvalue("10.54%")) < 0.01
    assert cleanvalue('Did NOt Collect') == 'did not collect'
    assert cleanvalue('<0.2') == '< 0.2'
    assert cleanvalue(' ') is None


def test_config():
    """Make sure we exercise the config logic as things get hairy"""
    (_, tmpfn) = tempfile.mkstemp()
    # create bogus config file
    cfg = dict(a='a', b='b')
    # Write config to bogus file
    save_config(cfg, tmpfn)
    # Attempt to load it back now
    cfg = get_config(tmpfn)
    assert cfg is not None
    os.unlink(tmpfn)


def test_translateyears():
    """See that we can translate years properly"""
    x = translate_years("X ('07-'17)")
    assert x[0] == 2007
    x = translate_years("X ('98-'06)")
    assert x[0] == 1998
    assert x[-1] == 2006
    x = translate_years("X ('14, '15, '16, '17)")
    assert x[0] == 2014
    assert x[-1] == 2017
    x = translate_years("X ('06)")
    assert x[0] == 2006
