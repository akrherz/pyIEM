"""Build Grid Navigation Metadata from the NetCDF file."""

from pyiem.models.gridnav import CartesianGridNavigation

_GRID_CONFIGS = {
    "IEMRE": {
        "left_edge": -126.0625,
        "bottom_edge": 22.9375,
        "dx": 0.125,
        "dy": 0.125,
        "nx": 488,
        "ny": 216,
    },
    "IEMRE_CHINA": {
        "left_edge": 69.9375,
        "bottom_edge": 14.9375,
        "dx": 0.125,
        "dy": 0.125,
        "nx": 560,
        "ny": 320,
    },
    "IEMRE_EUROPE": {
        "left_edge": -10.0625,
        "bottom_edge": 34.9375,
        "dx": 0.125,
        "dy": 0.125,
        "nx": 400,
        "ny": 280,
    },
    "IFC": {
        "left_edge": -97.1562505,
        "bottom_edge": 40.1312475,
        "dx": 0.004167,
        "dy": 0.004167,
        "nx": 1741,
        "ny": 1057,
    },
    # Lamely hardcoded for now
    "ERA5LAND": {
        "left_edge": -126.05,
        "bottom_edge": 22.95,
        "dx": 0.1,
        "dy": 0.1,
        "nx": 610,
        "ny": 270,
    },
    "ERA5LAND_CHINA": {
        "left_edge": 69.95,
        "bottom_edge": 14.95,
        "dx": 0.1,
        "dy": 0.1,
        "nx": 700,
        "ny": 400,
    },
    "ERA5LAND_EUROPE": {
        "left_edge": -10.05,
        "bottom_edge": 34.95,
        "dx": 0.1,
        "dy": 0.1,
        "nx": 500,
        "ny": 350,
    },
    "STAGE4": {
        "crs": (
            "+proj=stere +a=6371200 +b=6371200 +lat_0=90 "
            "+lon_0=-105 +lat_ts=60"
        ),
        "left_edge": -1_904_912.924,
        "bottom_edge": -7_619_986.180,
        "dx": 4_762.5,
        "dy": 4_762.5,
        "nx": 1121,
        "ny": 881,
    },
    "STAGE4_PRE2002": {
        "crs": (
            "+proj=stere +a=6371200 +b=6371200 +lat_0=90 "
            "+lon_0=-105 +lat_ts=60"
        ),
        "left_edge": -2_097_827.439,
        "bottom_edge": -7_622_315.608,
        "dx": 4_763.0,
        "dy": 4_763.0,
        "nx": 1160,
        "ny": 880,
    },
    "MRMS_IEMRE": {  # Specific to the IEM and not in general
        "left_edge": -126.0,
        "bottom_edge": 23.0,
        "dx": 0.01,
        "dy": 0.01,
        "nx": 6100,
        "ny": 2700,
    },
    "PRISM": {
        "left_edge": -125.0 - (1 / 24.0) / 2.0,
        "bottom_edge": 24.083333 - (1 / 24.0) / 2.0,
        "dx": 1 / 24.0,
        "dy": 1 / 24.0,
        "nx": 1405,
        "ny": 621,
    },
}


def get_nav(name: str, dom: str) -> CartesianGridNavigation:
    """Helper to remove some boilerplate for fetching gridnav."""
    extra = f"_{dom.upper()}" if dom != "" else ""
    key = f"{name.upper()}{extra}"
    return CartesianGridNavigation(**_GRID_CONFIGS[key])


def __getattr__(name: str):
    """Build stuff on the fly."""
    if name in _GRID_CONFIGS:
        return CartesianGridNavigation(**_GRID_CONFIGS[name])
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
