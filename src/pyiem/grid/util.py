"""pyIEM grid utilities."""

import numpy as np


def grid_smear(grid: np.ndarray, pad: int = 4) -> np.ndarray:
    """Smear data around to fill in masked values (likely near coastlines).

    Args:
        grid: 2D numpy array
        pad: number of pixels to smear the data around by in each direction

    Returns:
        2D numpy array with smeared data
    """
    # Pad grid
    padded = np.ma.masked_all(
        (grid.shape[0] + pad * 2, grid.shape[1] + pad * 2)
    )
    # set values from inbound grid
    padded[pad:-pad, pad:-pad] = grid

    # shift the grid by 4 pixels in each direction to fill in the padded region
    for xorigin in [0, pad * 2]:
        for yorigin in [0, pad * 2]:
            xslice = slice(xorigin, xorigin + grid.shape[0])
            yslice = slice(yorigin, yorigin + grid.shape[1])
            padded[xslice, yslice] = np.ma.where(
                np.logical_and(padded[xslice, yslice].mask, ~grid.mask),
                grid,
                padded[xslice, yslice],
            )

    return padded[pad:-pad, pad:-pad]
