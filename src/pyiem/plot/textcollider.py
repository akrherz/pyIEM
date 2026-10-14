"""Rectangle-based label collision tracking used by ``plot_values``."""

import numpy as np


class TextCollider:
    """Track claimed label boxes (display pixels) and test new ones.

    Each claimed box carries a priority (zorder).  A candidate collides only
    with claimed boxes of equal or higher priority, so higher priority labels
    drawn later are never culled by lower priority ones drawn earlier.
    """

    def __init__(self):
        """Constructor."""
        self._boxes = np.empty((0, 4), dtype=float)  # x0, y0, x1, y1
        self._zorders = np.empty(0, dtype=float)

    def __len__(self):
        """Number of claimed boxes."""
        return len(self._zorders)

    def collides(self, bbox, zorder, xpad=0.0, ypad=0.0) -> bool:
        """Does ``bbox`` (x0, y0, x1, y1) overlap a claimed box?

        Both boxes are inflated by the padding, so the minimum clear gap
        between two accepted labels is ``2 * pad``.
        """
        if not len(self):
            return False
        x0, y0, x1, y1 = bbox
        b = self._boxes
        hit = (
            (self._zorders >= zorder)
            & (x0 - xpad < b[:, 2] + xpad)
            & (x1 + xpad > b[:, 0] - xpad)
            & (y0 - ypad < b[:, 3] + ypad)
            & (y1 + ypad > b[:, 1] - ypad)
        )
        return bool(hit.any())

    def claim(self, bbox, zorder):
        """Record a box as occupied."""
        self._boxes = np.vstack([self._boxes, np.asarray(bbox, dtype=float)])
        self._zorders = np.append(self._zorders, zorder)

    def try_claim(self, bbox, zorder, xpad=0.0, ypad=0.0) -> bool:
        """Claim the box unless it collides, returning if it was claimed."""
        if self.collides(bbox, zorder, xpad, ypad):
            return False
        self.claim(bbox, zorder)
        return True
