"""Is our reference hackery usable."""

# Third party
from pyproj import Transformer
import pytest
import numpy as np

# Local
from pyiem import reference


def test_reference():
    """Can we import everything from our API."""
    for name in reference._onthefly_dict:
        res = getattr(reference, name, None)
        # is a dictionary
        assert isinstance(res, dict)
        # has keys
        assert res.keys()


@pytest.mark.parametrize("epsg", reference.EPSG)
def test_projections(epsg):
    """Test that the EPSG shortcuts actually are right!"""
    trans = Transformer.from_crs(4326, epsg, always_xy=True)
    pyproj_res = trans.transform(-94, 42)
    cartopy_crs = reference.EPSG[epsg]
    cartopy_res = cartopy_crs.transform_points(
        reference.EPSG[4326],
        np.array(
            [
                -94,
            ]
        ),
        np.array(
            [
                42,
            ]
        ),
    )
    assert np.allclose(pyproj_res, cartopy_res[0][:2])
