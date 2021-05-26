"""Test GINI"""

from pyiem.util import get_test_file
from pyiem.nws import gini


def test_getirramp():
    """Make sure get_irramp works"""
    d = gini.get_ir_ramp()
    assert len(d) == 256


def test_conus():
    """Test processing a national product"""
    sat = gini.GINIZFile(get_test_file("TIGN02", fponly=True))
    assert sat.archive_filename() == "GOES_SUPER_IR_201509281745.png"
    assert sat.awips_grid() == 0
    assert sat.metadata["map_projection"] == 5


def test_gini():
    """check GINI Processing of Goes East VIS parsing"""
    sat = gini.GINIZFile(get_test_file("TIGH05", fponly=True))
    assert sat.archive_filename() == "GOES_HI_WV_201507161745.png"
    assert str(sat) == "TIGH05 KNES 161745 Line Size: 560 Num Lines: 520"
    assert sat.awips_grid() == 208
