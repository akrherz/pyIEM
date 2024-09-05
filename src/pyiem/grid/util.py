"""pyIEM grid utilities."""

import numpy as np


def grid_smear(grid: np.ndarray, shift: int = 4) -> np.ndarray:
    """Smear data around to fill in masked values (likely near coastlines).

    Args:
        grid: 2D numpy array
        shift: number of pixels to smear the data around by in each direction

    Returns:
        2D numpy array with smeared data
    """
    # Pad grid
    padded = np.ma.masked_all(
        (grid.shape[0] + shift * 2, grid.shape[1] + shift * 2)
    )
    # set values from inbound grid
    padded[shift:-shift, shift:-shift] = grid

    # shift the grid by shift pixels in each direction to fill in the padded
    for xorigin in [0, shift * 2]:
        for yorigin in [0, shift * 2]:
            xslice = slice(xorigin, xorigin + grid.shape[0])
            yslice = slice(yorigin, yorigin + grid.shape[1])
            padded[xslice, yslice] = np.ma.where(
                np.logical_and(padded[xslice, yslice].mask, ~grid.mask),
                grid,
                padded[xslice, yslice],
            )

    return padded[shift:-shift, shift:-shift]
