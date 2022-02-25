<!-- markdownlint-configure-file {"MD024": { "siblings_only": true } } -->
# Changelog

All notable changes to this library are documented in this file.

## **1.11.0** (25 Feb 2022)

### API Changes

- Deprecate windrose plot `draw_logo` as the constructor can now handle this
within the standardized `figure` constructor.

### New Features

- Add `util.get_sqlalchemy_conn` helper to reduce IEM biolerplate.
- Parse `snow depth` from CLI products (#15).

### Bug Fixes

- Correct for some edge cases found with parsing `ICE STORM` LSR remarks.
- Improve robustness of `DV` SHEF encoding parsing.
- Remove some abiquity with how the `windrose` plot legend specifies ranges.
- Support parsing `DY` SHEF time encoding.
- [SHEF] Workaround multiple `DH2400` values in a message.

## **1.10.0** (24 Jan 2022)

### API Changes

- For `pyiem.plot.geoplot.fill_ugcs` changed `nocbar` kwarg to `draw_colorbar`.
- Remove confusing `pyiem.nws.product.VTECProduct.db_year` attribute (#534).
- Change the default log level to `WARNING` for non-interactive shells and to
`INFO` for interactive shells (#541).

### New Features

- Add `pyiem.plot.geoplot.MapPlot` kwarg of `axes_position` to control where
the main axes is placed on the figure.
- Python versions 3.8 through 3.10 are now actively tested and supported.
- Added `pyiem.util.get_dbconnstr` helper to return a database connection
string details.

### Bug Fixes

- Correct logic for VTEC year referenced in links (#534).
- Fix ambiguous situation around the New Year's that could have two VTEC
ETNs active at the same time (#533).
- Improve logic for "concerning" headline parsing from MCD/MPDs (#528).
- Cross checked IEM VTEC database and created missing `NWS_COLORS` entries,
which cross references VTEC codes to NWS WaWA map colors.
- The NWS has an ongoing issue (2017-present) with disseminating truncated
Tsuanmi products.  These truncated products are dups to non-truncated ones.
Special code was added to abort processing of these when found.
- A pandas 1.4.0 API problem was fixed.

## **1.9.0** (13 Dec 2021)

### API Changes

- Replaced `cartopy` usage with a custom axes class that manages a `matplotlib` axes along with a `pyproj` CRS instance.  Aspects of using internal attributes within `pyiem.plot.MapPlot` are perhaps broken downstream, but I know of no users of this API other than myself (#514).
- Removed deprecated `pyiem.cscap_utils.get_sites_client`.  It would be nice to migrate this to updated Google API, but classic Google vaporware and such API does not exist.
- Removed unused `pyiem.mrms.get_fn`.
- Usage of `descartes` was removed as it was un-necessary for this library.

### New Features

- Added IEM specific ability to pass autoplot contexts into plotting and set things like the resolution and map sector (#519).

### Bug Fixes

- Addressed upcoming Shapely 2.0 deprecations.

## **1.8.0** (20 Oct 2021)

### API Changes

- `pyiem.nws.product.TextProduct#get_product_id` now includes the `BBB` field in the return string, when specified within the parsed text.  This is necessary to fully describe products that may be issued twice within the same minute.
- Removed the hacky `iemdb2.local` database failover concept that hopefully nobody else was somehow using.
- Previously announced deprecations of `pyiem.nws.lsr.LSR.tweet` and `pyiem.plot.geoplot.windrose` formally removed.
- Announce deprecation of `pyiem.cscap_utils.get_sites_client` in v1.9.0.

### New Features

- A pure python SHEF decoder `pyiem.nws.products.shef` (#496).
- Updated bundled NWS zones database to valid cira 10 Sep 2021.

### Bug Fixes

- Improved logic for determination of TOR/FFW Emergency events by considering the tags as well (#491).

## **1.7.0** (2 Sep 2021)

### API Changes

- Update `MapPlot.drawcities()` to no longer use `minarea` as a filter on
which cities are potentially labeled on the map.  The bundled dataset was
updated on use a different [upstream source](https://geodata.lib.berkeley.edu/catalog/stanford-bx729wr3020).
- Remove internal loading support of pickled pandas DataFrames. Twas bad idea.
- `pyiem.nws.ugc.UGC.name` is no longer allowed to be `None`.

### New Features

- Add `SPS.<state>` channel for SPS Products.
- Add `pyiem.plot.util.ramp2df` to load a bundled color ramp into a DataFrame.
- Implement a parser of the WPC Excessive Rainfall Outlook (#13).
- For VTEC events with hydro forecast points, the `twitter_media` generated URL points to AHPS's flood forecast image.
- Python 3.7+ is now routinely tested.

### Bug Fixes

- Account for another SPC PTS edge case, le sigh.
- Gracefully handle a one or two point `polygon` attempt from a NWS Product.
- Removed hard-coded cartopy data path (#492).
- Rewrite SPC PTS parsing (again), but this time use @deeplycloudy suggested "Winding" algorithm.

## **1.6.0** (26 May 2021)

### API Changes

- Moved `pyiem.plot.geoplot.load_geodf` to `pyiem.util.load_geodf`.
- Removed `day` attribute from `pyiem.nws.products.spcpts.SPCPTS` class as it
was not accurate.
- Introduced `pyiem.geom_util` to house generally useful geometry operations.

### New Features

- Storm Prediction Center outlook parser now uses internal WFO geometries to
compute which WFOs are impacted by an outlook.
- Introduce `util.web2ldm`, which does a common IEM workflow of taking some
web resource, downloading it, and inserting into LDM.
- Introduce `pyiem.htmlgen` helpers for generating HTML, of all things.
- Add IEM threading accounting into `pyiem.network.Table`.
- Support provision of a `cmap` to windrose plotting and have a more pleasing
default set of colors.
- Register default `psycopg2` adapters to hopefully prevent `np.nan` from
reaching the database.

### Bug Fixes

- Matplotlib 3.4 is generally supported with `pytest-mpl` tests passing.
- NWS County Warning Areas geometries updated to 10 Nov 2020 release.
- Corrected time stamp parsing for NBS MOS data at 21, 22, and 23Z.
- Fix overlay of Hawaii on `nws` sector `GeoPlot` when the resolution is
not the default.
- Correct PIREP location parsing to use nautical miles vs miles (#442).
- Differentiate between TAF visibility over 6 miles and that of 6 miles. This
is currently hard coded as 6.01. (#449)
- For now, silently not allow one point lines in SPC PTS processing.

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
