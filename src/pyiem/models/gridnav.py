"""Grid Navigation Metadata."""

from typing import Optional, Union, cast

import numpy as np
from affine import Affine
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pyproj import CRS, Proj


class CartesianGridNavigation(BaseModel):
    """Navigation for cartesian grid with (0,0) in lower left.

    The `left_edge` and `bottom_edge` are the only required fields. The
    rest are optional, but you need to have enough information to define
    the grid, ie provide `dx` and `dy` or `nx` and `ny`.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    crs: Union[str, CRS] = Field(
        default="EPSG:4326",
        description="The coordinate reference system of the grid",
    )
    left_edge: float = Field(
        default=...,
        description="The left edge of the grid in projection units",
    )
    bottom_edge: float = Field(
        default=...,
        description="The bottom edge of the grid in projection units",
    )
    top_edge: Optional[float] = Field(
        default=None,
        description="The top edge of the grid in projection units",
    )
    right_edge: Optional[float] = Field(
        default=None,
        description="The right edge of the grid in projection units",
    )
    dx: Optional[float] = Field(
        default=None,
        description="The grid cell width in projection units",
        gt=0,
    )
    dy: Optional[float] = Field(
        default=None,
        description="The grid cell height in projection units",
        gt=0,
    )
    nx: Optional[int] = Field(
        default=None,
        description="The number of grid cells in the x direction",
        gt=0,
    )
    ny: Optional[int] = Field(
        default=None,
        description="The number of grid cells in the y direction",
        gt=0,
    )

    @property
    def x_points(self) -> np.ndarray:
        """These are the centers of the cells in the x direction."""
        return np.arange(cast(int, self.nx)) * cast(float, self.dx) + self.left

    @property
    def y_points(self) -> np.ndarray:
        """These are the centers of the cells in the y direction."""
        return (
            np.arange(cast(int, self.ny)) * cast(float, self.dy) + self.bottom
        )

    @property
    def x_edges(self) -> np.ndarray:
        """These are the edges of the x cells (n=NX + 1)."""
        return (
            np.arange(cast(int, self.nx) + 1) * cast(float, self.dx)
            + self.left_edge
        )

    @property
    def y_edges(self) -> np.ndarray:
        """These are the edges of the y cells (n=NY + 1)."""
        return (
            np.arange(cast(int, self.ny) + 1) * cast(float, self.dy)
            + self.bottom_edge
        )

    @property
    def left(self) -> float:
        """The centroid of the left most grid cell."""
        return self.left_edge + (cast(float, self.dx) / 2.0)

    @property
    def right(self) -> float:
        """The centroid of the right most grid cell."""
        return self.right_edge - (cast(float, self.dx) / 2.0)

    @property
    def bottom(self) -> float:
        """The centroid of the bottom most grid cell."""
        return self.bottom_edge + (cast(float, self.dy) / 2.0)

    @property
    def top(self) -> float:
        """The centroid of the top most grid cell."""
        return cast(float, self.top_edge) - (cast(float, self.dy) / 2.0)

    @property
    def affine(self):
        """Return the affine transformation."""
        return Affine(
            cast(float, self.dx),
            0,
            self.left_edge,
            0,
            cast(float, self.dy),
            self.bottom_edge,
        )

    @property
    def affine_image(self):
        """Return the transformation associated with upper left origin."""
        return Affine(
            cast(float, self.dx),
            0,
            self.left_edge,
            0,
            0 - cast(float, self.dy),
            cast(float, self.top_edge),
        )

    @model_validator(mode="before")
    @classmethod
    def complete_definition(cls, values):
        """Use information that was provided to compute other fields."""
        # We have required fields left_edge, bottom_edge
        # Require that either dx/dy is provided or nx/ny is provided
        if values.get("top_edge") is None:
            values["top_edge"] = values["bottom_edge"] + (
                values["ny"] * values["dy"]
            )
        if values.get("right_edge") is None:
            values["right_edge"] = values["left_edge"] + (
                values["nx"] * values["dx"]
            )
        if values.get("dx") is None:
            values["dx"] = (values["right_edge"] - values["left_edge"]) / (
                values["nx"]
            )
        if values.get("dy") is None:
            values["dy"] = (values["top_edge"] - values["bottom_edge"]) / (
                values["ny"]
            )
        # Be a bit more careful here that our grid generates a near integer
        for key, spacing, edges in [
            ("nx", "dx", ["left_edge", "right_edge"]),
            ("ny", "dy", ["bottom_edge", "top_edge"]),
        ]:
            if values.get(key) is not None:
                continue
            nn = (values[edges[1]] - values[edges[0]]) / values[spacing]
            if abs(nn - int(nn)) > 0.01:
                msg = f"Computed {key} is not approximately an integer"
                raise ValueError(msg)
            values[key] = int(nn)

        return values

    def find_ij(
        self, lon: float, lat: float
    ) -> tuple[Optional[int], Optional[int]]:
        """Find the grid cell that contains the given lon/lat (EPSG: 4326)."""
        x, y = Proj(self.crs)(lon, lat)  # skipcq
        if (
            x < self.left_edge
            or x >= self.right_edge
            or y < self.bottom_edge
            or y >= self.top_edge
        ):
            return None, None
        i = int((x - self.left_edge) / self.dx)
        j = int((y - self.bottom_edge) / self.dy)
        return i, j
