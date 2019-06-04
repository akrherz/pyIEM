"""Testing of util."""
import datetime
import string
import random
from io import BytesIO
from collections import OrderedDict
import mock

import pytest
import pytz
import numpy as np
from pyiem import util


@pytest.fixture
def cursor():
    """Return a database cursor."""
    return util.get_dbconn('mesosite').cursor()


def test_logger():
    """Can we emit logs."""
    log = util.logger()
    assert log is not None


def test_find_ij():
    """Can we find_ij()."""
    xgrid, ygrid = np.meshgrid(np.arange(10), np.arange(10))
    i, j = util.find_ij(xgrid, ygrid, 4, 4)
    assert i == 4
    assert j == 4


def test_ssw():
    """Does pyiem.util.ssw work?"""
    with mock.patch('sys.stdout', new=BytesIO()) as fake_out:
        util.ssw("Hello Daryl!")
        assert fake_out.getvalue() == b'Hello Daryl!'
        fake_out.seek(0)
        util.ssw(b"Hello Daryl!")
        assert fake_out.getvalue() == b'Hello Daryl!'
        fake_out.seek(0)
        util.ssw(u"Hello Daryl!")
        assert fake_out.getvalue() == b'Hello Daryl!'
        fake_out.seek(0)


def test_utc():
    """Does the utc() function work as expected."""
    answer = datetime.datetime(2017, 2, 1, 2, 20).replace(tzinfo=pytz.UTC)
    res = util.utc(2017, 2, 1, 2, 20)
    assert answer == res
    answer = datetime.datetime.utcnow().replace(tzinfo=pytz.UTC)
    assert answer.year == util.utc().year


def test_get_autoplot_context():
    """See that we can do things."""
    form = dict(station='AMW', network='IA_ASOS', type2='bogus',
                t=15, type3=['max-high', 'bogus', 'min-high'])
    form['type'] = 'max-low'
    pdict = OrderedDict([
                            ('max-high', 'Maximum High'),
                            ('avg-high', 'Average High'),
                            ('min-high', 'Minimum High'),
                            ('max-low', 'Maximum Low')])
    cfg = dict(arguments=[
        dict(type='station', name='station', default='IA0000'),
        dict(type='select', name='type', default='max-high',
             options=pdict),
        dict(type='select', name='type2', default='max-high',
             options=pdict),
        dict(type='select', name='type3', default='max-high',
             options=pdict, multiple=True),
        dict(type='select', name='type4', default='max-high',
             options=pdict, multiple=True, optional=True),
        dict(type='select', name='type5', default='max-high',
             options=pdict),
        dict(type='int', name='threshold', default=-99),
        dict(type='int', name='t', default=9, min=0, max=10),
        dict(type='date', name='d', default='2011/11/12'),
        dict(type='datetime', name='d2', default='2011/11/12 0000',
             max='2017/12/12 1212', min='2011/01/01 0000'),
        dict(type='year', name='year', default='2011', optional=True),
        dict(type='float', name='f', default=1.10)])
    ctx = util.get_autoplot_context(form, cfg)
    assert ctx['station'] == 'AMW'
    assert ctx['network'] == 'IA_ASOS'
    assert isinstance(ctx['threshold'], int)
    assert ctx['type'] == 'max-low'
    assert ctx['type2'] == 'max-high'
    assert isinstance(ctx['f'], float)
    assert ctx['t'] == 9
    assert ctx['d'] == datetime.date(2011, 11, 12)
    assert ctx['d2'] == datetime.datetime(2011, 11, 12)
    assert 'year' not in ctx
    assert 'bogus' not in ctx['type3']
    assert 'type4' not in ctx

    form = dict(zstation='DSM')
    cfg = dict(arguments=[
        dict(type='zstation', name='station', default='DSM',
             network='IA_ASOS')])
    ctx = util.get_autoplot_context(form, cfg)
    assert ctx['network'] == 'IA_ASOS'


def test_backoff():
    """Do the backoff of a bad func"""
    def bad():
        """Always errors"""
        raise Exception("Always Raises :)")
    res = util.exponential_backoff(bad, _ebfactor=0)
    assert res is None


def test_grid_bounds():
    """Can we compute grid bounds correctly"""
    lons = np.arange(-100, -80, 0.1)
    lats = np.arange(29, 51, 0.2)
    (x0, y0, x1, y1) = util.grid_bounds(lons, lats, [-96, 32, -89, 40])
    assert x0 == 41
    assert x1 == 111
    assert y0 == 16
    assert y1 == 56
    (lons, lats) = np.meshgrid(lons, lats)
    (x0, y0, x1, y1) = util.grid_bounds(lons, lats, [-96, 32, -89, 40])
    assert x0 == 40
    assert x1 == 110
    assert y0 == 15
    assert y1 == 55


def test_noaaport_text():
    """See that we do what we expect with noaaport text processing"""
    data = util.get_test_file('WCN.txt')
    res = util.noaaport_text(data)
    assert res[:11] == "\001\r\r\n098 \r\r\n"
    assert res[-9:] == "SMALL\r\r\n\003"


def test_vtecps():
    """Can we properly handle the vtecps form type"""
    cfg = dict(arguments=[
        dict(type='vtec_ps', name='v1', default='TO.W',
             label='VTEC Phenomena and Significance 1'),
        dict(type='vtec_ps', name='v2', default='TO.A', optional=True,
             label='VTEC Phenomena and Significance 2'),
        dict(type='vtec_ps', name='v3', default=None, optional=True,
             label='VTEC Phenomena and Significance 3'),
        dict(type='vtec_ps', name='v4', default='FL.Y', optional=True,
             label='VTEC Phenomena and Significance 4'),
        dict(type='vtec_ps', name='v5', default='UNUSED', optional=True,
             label='VTEC Phenomena and Significance 5')])
    form = dict(phenomenav1='SV', significancev1='A',
                phenomenav4='TO', significancev4='W')
    ctx = util.get_autoplot_context(form, cfg)
    # For v1, we were explicitly provided by from the form
    assert ctx['phenomenav1'] == 'SV'
    assert ctx['significancev1'] == 'A'
    # For v2, optional is on, so our values should be None
    assert ctx.get('phenomenav2') is None
    # For v3, should be None as well
    assert ctx.get('phenomenav3') is None
    # For v4, we provided a value via form
    assert ctx['significancev4'] == 'W'
    # For v5, we have a bad default set
    assert ctx.get('phenomenav5') is None


def test_properties(cursor):
    """ Try the properties function"""
    tmpname = ''.join(
        random.choice(string.ascii_uppercase + string.digits)
        for _ in range(7)
    )
    tmpval = ''.join(
        random.choice(string.ascii_uppercase + string.digits)
        for _ in range(7)
    )
    cursor.execute("""
    INSERT into properties(propname, propvalue) VALUES (%s, %s)
    """, (tmpname, tmpval))
    prop = util.get_properties(cursor)
    assert isinstance(prop, dict)
    assert prop[tmpname] == tmpval


def test_drct2text():
    """ Test conversion of drct2text """
    assert util.drct2text(360) == "N"
    assert util.drct2text(90) == "E"
    # A hack to get move coverage
    for i in range(360):
        util.drct2text(i)
