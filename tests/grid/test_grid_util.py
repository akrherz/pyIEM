"""Test pyiem.grid.util"""

import numpy as np

from pyiem.grid.util import grid_smear


def test_grid_smear():
    """Test the smearing."""
    grid = np.ma.ones((10, 10)) * np.arange(10)
    # set value at 8,8 to missing
    grid[8, 8] = np.ma.masked
    grid2 = grid_smear(grid)
    assert grid2[8, 8] == 4
