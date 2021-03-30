# Changelog

All notable changes to this library are documented in this file.

## **1.5.0** (30 March 2021)

### API Changes

- Refactor mostly internal MapPlot feature plotting.  This library does not
have a public API promise, so alas.  Generally, this should not impact users
unless you were accessing internal geo-databases or using the bundled pickled
libraries directly.  This should be low impact as for example, my `iem`
code repo required no changes for this (#402).

### New Features

- Introduce a BUFKIT file reader.  `pyiem.nws.bufkit.read_bufkit` (#390).
- Generalized `MapPlot.fill_{ugcs,states,climdiv,etc}` now support provision
of colors via `color=` or combo of `fc=` and `ec=`.
- Introduce `pyarrow` as package requirement to read parquet files for
GeoPandas (#402).
- Support parsing and database storage of TAF information (#377).
- Update bundled NWS counties/zones to be current on 30 March 2021.
- Backend database storage for SPC Outlooks has changed, please see repo
akrherz/iem-database for current schema.

### Bug Fixes

- Update bundled `states` geographies to include territories of `AS`, `PR`,
`VI`, `GU`, and `MP`.
- Implement tweet message truncation for SPS messages (#393).
- Add CLI database storage of `snow_normal` (#396).
- Support database insert of multi-segment SPS products (#399).
- `MapPlot.fill_ugcs` was refactored to use generic `polygon_fill`.
- Correct how version is set during local development.
- Account for (E) usage in CLIRDU (#408).
- Rework how cartopy projections are handled (#418).

## **1.4.0** (9 March 2021)

The repo's `master` branch has been renamed `main`.

### API Changes

- While implementing the new NWS SVS, SVR, and TOR IBW tag changes (#253), the
attributes for the `pyiem.nws.product#TextProductSegment` attributes subtly
changed.  The `tornadodamagetag` attribute is now just `damagetag`.
- Centralize logo plotting logic, this is a small API break, but I don't
suspect folks are using this code path (fa1e2ce).

### New Features

- Special Weather Statements (SPS) products are now parsed for IBW tags (#253),
this required database schema updates with these products stored in an explicit
`sps` table.  See 
[akrherz/iem-database](https://github.com/akrherz/iem-database) repo.
- Add warnings back for when unknown HVTEC NWSLIs are found (#375).
- Introduce `rasterio` for faster imshow overlays of NEXRAD composites.
- Add `geoplot.MapPlot.overlay_roadcond` to overlay Iowa Winter Road
Conditions.
- Add `geoplot.MapPlot.overlay_nexrad` to overlay CONUS IEM NEXRAD mosaics.
- Add util helpers for `mm2inch` and `c2f` (#360).
- Add `pyiem.plot.layouts.{figure,figure_axis}` (#355).

### Bug Fixes

- Properly parse NWS products that use a UTC Mass News Disseminator headline
(#381).
- Fix contour gridding calculation for non-Plate Carree plots (#374).
- Major logic fix for how NWS fire weather zones are stored and used within
the library. Added `is_firewx` flag to `fill_ugcs` (#374).
- When self-intersecting polygons are found within NWS products, a
`buffer(0)` attempt is made to fix this (#378).
- Fix off-by-one length calculation issue for LSR tweets (#371).
- Fix CONUS masking logic such that features like Cape Code are not masked
out (#365).
- Account for invalid stray colons in CLI products (#364).
- Fix `ICE STORM` LSR magnitude gleaning for /16th of an inch values (#362).
- Fix PTS parsing regression (#358).
- Support integer lat/lon values in PIREPs (#357).
- Support AWIPS IDs that start with a number (#356).
