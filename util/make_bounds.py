"""Generate the _ccw files used in pyIEM."""

from pyiem.plot import MapPlot
from pyiem.util import get_dbconn
from shapely.wkb import loads
from shapely.geometry import Polygon, MultiPolygon
from descartes.patch import PolygonPatch
import numpy as np


def main():
    """Go Main Go."""
    DBCONN = get_dbconn("postgis")
    cursor = DBCONN.cursor()

    cursor.execute(
        """
        SELECT
            ST_Transform(
                ST_Simplify(
                    ST_Union(ST_Transform(the_geom,2163)),
                    500.),
                4326) from states
        WHERE state_abbr in ('IA', 'IL', 'IN')
    ---    where state_abbr in ('MI','WI', 'IL', 'IN', 'OH', 'KY', 'MO', 'KS',
    ---    'NE', 'SD', 'ND', 'MN', 'IA')
    """
    )

    m = MapPlot("iowa")
    lons = np.linspace(-110, -70, 50)
    lats = np.linspace(28, 52, 50)
    vals = np.linspace(0, 50, 50)
    m.contourf(lons, lats, vals, vals)

    # """
    for row in cursor:
        multipoly = MultiPolygon([loads(row[0], hex=True)])
        for geo in multipoly.geoms:
            if geo.area < 1:
                continue
            (lons, lats) = geo.exterior.xy
            print("Masking with geo... %s %s" % (geo.area, len(lons)))

            ar = list(zip(lons, lats))
            ar.reverse()
            np.save("iailin_ccw.npy", ar)
            # mask_outside_polygon(ar, ax=m.ax)
            poly = PolygonPatch(Polygon(ar), fc="r", zorder=10000)
            m.ax.add_patch(poly)
    # """
    m.postprocess(filename="test.png")


if __name__ == "__main__":
    main()
