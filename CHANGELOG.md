<!-- markdownlint-configure-file {"MD024": { "siblings_only": true } } -->
# Changelog

All notable changes to this library are documented in this file.

## **1.18.0** (29 Dec 2023)

### API Changes

- Add dependencies on `nh3` and `paste`.
- Raise `NewDatabaseConnectionFailure` from `pyiem.database.get_dbconn` for
all failures and stop emitting `UserWarning`.
- Raise `UnknownStationException` from `pyiem.util.get_autoplot_context` when
an unknown station is provided.
- Repurpose LSR type internal code `q` for `SNOW SQUALL`.

### New Features

- Add `#{state}wx` hash tags to NWS Local Storm Report social media posts.
- Add `cursor_name` option to `database.get_dbconnc`.
- Add `pyiem.iemre.reproject2iemre` helper to bring arbitrary grids onto IEMRE.
- Add `pyiem.util.{delete,set}_property` helpers.
- Introduce `pyiem.webutil.iemapp` decorator to do fancy things for IEM
mod_wsgi apps and remove downstream boilerplate.

### Bug Fixes

- [SHEF] Lines startig with ":" are double checked for slashes, before use.
- [SHEF] Ensure E message elements have a physical_element set.
- [SHEF] Fix `DD` modifier when we are crossing a month.
- [SHEF] Fix significant bug with Paired Values (ref SHEF Manual 7.4.6) not
properly computing magnitude for encoded float values.
- [SHEF] Forgive a random nan that keeps appearing in RRSRAH.
- [SHEF] Prevent extraneous "/" added to contination .A and .E messages.
- [SHEF] Support 0.001 encoding of Trace values.
- Allow for calm percentage plotting space in windrose with rmax set (#798).
- Fix `compute_wfos` method for SAW processor.
- Make presence of tabs in CLI products more forgiving.
- Refactor SHEF parsing such to better handle situations with time modifiers
being missing and enforce `SHEFElement` pydantic validation.

## **1.17.0** (18 Sep 2023)

### API Changes

- **MAJOR** Migration of database connections to psycopg 3, introduce
`get_dbconnc` to return a connection and dict_row cursor.  Currently,
`get_dbconn` will continue to return a default cursor, this may change in
the future (#754).
- Default to psycopg 3 for sqlalchemy connections.
- Drop `twython` and remove `pyiem.util.get_twitter` as both are defunct after
Twitter v1.1 removal.
- Fully drop `backports.zoneinfo` usage as we now require Python 3.9+.

### New Features

- Add `pyiem.util.get_dbconnc` helper to return a connection + cursor.
- Add some AFOS product definitions for various NHC recon products.
- `htmlgen/station_select` was updated to include offline stations by default.
- Updated bundled NWS GIS to 19 Sep 2023 release (#734).

### Bug Fixes

- Fix Jabber message generation for SPC Day4-8 Convective Outlooks.
- Misc improvements to NWS CLI product parsing.
- Require IBW tag confirmation before declaring a TOR,FFW product as an
emergency, for products 2023 and onward.
- [SHEF] Account for corrupted timestamp generating a traceback.
- Upper case LSR `typetext` in Jabber channel usage.

## **1.16.0** (14 Jul 2023)

### API Changes

- Convert marine LSR types that are used on land to legacy codes (#729).
- Dropped python=3.8 support/testing as xarray has moved on.
- Removed `pyiem.cscap_utils` as it was not maintained.
- Removed `pyiem.twistedpg` as it was a glorious hack and no longer needed.
- SPC/WPC outlook geometry is now the actual threshold specific geometry. A
corresponding `geometry_layers` multipolygon now exists to hold the non cookie
cutted polygon (#738).

### New Features

- Add bling to jabber messages generated from PNS Damage Surveys.
- Add Impact Based Warning tags to jabber channels in the form of
`<phenomena>.<significance>.<tag>` (#11).
- Add parser for Wind/Temps Aloft Forecast product (AWIPSID: FD) (#713).
- Add `twitter_media` for LSR jabber messages.
- Improve METAR parsing to better preserve integer `degF`` temperatures (#740).
- Persist Summary LSR product identifier to database (akrherz/pyWWA#150).
- Support `type="state"` for autoplot context.
- Support Guam for NEXRAD overlays.
- Updated bundled NWS counties/zones to something circa March 2023.
- Validate `type=cmap` for `util.get_autoplot_context` (#709).

### Bug Fixes

- Correct VTEC `is_emergency` false positive spotted by Kyle Noël.
- Improve forgiveness of CLI parser some more.  Never ends.
- Improve robustness of `FLS` impacts bullet search.
- Prevent CF6 data from the future.
- [SHEF] Workaround `DV` months offset, which is ill-defined anyway.
- Support LSRs with mile units.
- Fix LSR `typetext` comparisons and ensure database uppercase entries.

## **1.15.0** (13 Feb 2023)

### API Changes

- Depend on package `defusedxml` for XML parsing.
- Depend on package `twython`.
- Depend on package `pymemcache` to support my hackish use of memcached.
- Quasi internal `MetarCollective.wind_message` was modified to also return the
wind speed in knots.
- Refactor internal testing `util.get_file_name` helper.
- Refactor `pyiem.util` database methods to `pyiem.database`.

### New Features

- Add flag (`plot_convention`) for windrose plots to change orientation of the
bars.  Engineers generally want bars oriented toward the direction the wind
is blowing toward, not from (#680).
- Add `isolated` parameter to `geoplot.plot_values` to allow label collision
to only be done against the plotted data in that iteration and not all data.
- Add `fill_{rfc,cwsu}` as available `MapPlot` methods.
- Add WPC XTEUS (national max/min temp) parser `pyiem.nws.products.xteus`.
- Fill out `pyiem.data.reference.prodDefinitions` based on what the IEM AFOS
database has.
- Fix state border zorder and allow `stateborderwidth` kwarg.
- Jabber channels for METAR wind gust alerts were enhanced (#683).
- Generate a TextProduct.warning message for a VTEC product that should contain
a polygon, but does not (#660).
- Introduce a natural earth background option for MapPlot (#304).
- Introduce hacky `sector="spherical_mercator"` that brings in ESRI basemaps
for the background.  My implementation stinks and will change (#304).
- Support `cartopy_offlinedata` version 0.20+.
- Support new CLI format diction from NWS Sacramento.
- Workaround autoplot context fun with mixed 3-4 character WFOs.

### Bug Fixes

- Account for `MapPlot` custom domain that crosses anti-meridian (#655).
- Add GU "Guam" to pyiem.reference.state_names.
- Allow non-conforming `DHMSG` within SHEF.
- Cleanup and improve windrose title / time filtering logic (#663).
- Correct VTEC database accounting issue for emergencies (#676).
- Correct VTEC database partitioning for difficult event spanning years.
- Draw mask on all known sectored plots.
- Increased default `pyiem.util.get_dbconn` connect timeout to 30 seconds.
- Polish SHEF parsing some with better error message and account for `...`
headlines.
- Reduce needless lat/lon precision with Jabber messages (#656).
- Remove hard coded `nobody` database user for some internal API calls.
- Remove matplotlib colormap shim and require matplotlib>=3.5.
- [SHEF] Make station ids longer than 8 chars non-fatal.
- Support geos 3.11 (#633).
- Support increased range and emit ValueError for too large range for
`pyiem.plot.pretty_bins` (#665).
- Update `UP` VTEC phenomena label to "Freezing Spray", remove `ZY`.

## **1.14.0** (15 Sep 2022)

### API Changes

- [SHEF] Permit one character SHEF physical codes (daryl gave up).
- [DS3505] Removed hacky metar/sql round trip code in NCEI ISH processor.
- [metarcollect] Break the internal API and storage for `iemid` and how
iemaccess gets updated to allow for downstream changes.
- [NetworkTable] Change internal data structure from dict to list for station
threading information (#645).
- [observation] Adjusted the constructor to allow some things to be optional
and allow manual provision of `iemid` and `tzname`.

### New Features

- Add support for upcoming Snow Squall Warning impact tags (#493).
- Attempt to resolve a NWS UGC code when storing a LSR to the database (#637).
- Enhance G-AIRMET processing to better define icing and not create airmet
entries for multiple-level freezing airmets (#628).
- Generalize autoplot context parsing for params starting with `_`.
- Support Center Weather Advisory (CWA) that uses lat/lon points.
- Update bundled NWS Counties/Zones to circa 13 Sep 2022 (#648).

### Bug Fixes

- [windrose] Cleanup the title and diagnostic for windrose plots.
- Allow trailing space in UGC encoding line (#652).
- Correct decoding of 12 UTC timestamp in MND header.
- Ensure CF6 weather codes go to the database verbatim without float conv.
- Fix G-AIRMET decoding of multiple freezing levels airmet.
- Workaround a specified 12 AM UTC timestamp in NWS text products.

## **1.13.0** (24 Jun 2022)

### API Changes

- Added `sqlalchemy` as a hard package requirement.
- `pyiem.nws.products.saw` no longer writes un-used SAW text to database.
- Refactor internal SHEF decoding such that `TextProduct` instance has a seat
at the table when some acceptable parsing failures can happen.  The functional
form of `process_messages_{a,b,e}` is now `TextProduct,str`.
- Refactor internal VTEC API for creating jabber messages.
- Refactor `windrose_utils` and remove the positional argument cruft.
- The XMPP channels assigned to VTEC products that are CONtinues, EXPires, or
CANcels was modified to append a `-ACT`ion to the channel in the case of the
channels prefixed by the `phenomena.significance`.  This will cut down on
the social media posts for products that are more mudane (#604).

### New Features

- Add alpha control to `draw_usdm`.
- Add database storage of `purge_time` for VTEC products (#616).
- Add parsing support for CWSU Center Weather Advisory (#573).
- Add option to `mcalc_feelslike` to support `mask_undefined`.
- Add `twitter_media` link for generic text products that have a polygon (#586).
- Add `limit_by_doy` option to `windrose_utils` to allow a day of year limit.
- Add parser for SPC Watch Probabilities (WWP) product (#595).
- Add basic parser for SPC SEL Product.
- Allow `pyiem.nws.nwsli` instance to be subscriptable for iterop.
- Support passing `linewidths` to `MapPlot.contourf`.

### Bug Fixes

- [SHEF] Catch invalid nan values.
- [windrose] Fixed logic bug when `limit_by_doy` was set and dates crossed
1 January.
- Added some jitter to plotting labels for side-by-side WFOs.
- Fixed f-string formatting issue in SAW jabber message generator.
- Fixed missing `ENH` and `MDT` from `spcpts.THRESHOLD_ORDER`.
- Fixed jabber/twitter message generation for a VTEC product with multiple
segments with the same vtec action (read tropical products).
- Heat index is now computed without the presence of wind info (#623).
- Improved logic behind `pyiem.plot.util.pretty_bins`, it no longer exactly
returns the specified number of bins, but tries to do the right thing!
- Increase remark trimming for LSR tweets for more length safety.
- Stopped back-computing affected WFOs based on the UGCs found in a VTEC
product.  This was causing more confusion than good (#615).
- Support CHUT, PWT timezones in NWS products.

## **1.12.0** (18 Mar 2022)

### API Changes

- Bring bundled NWS zones database to 22 March 2022 release (#531).

### New Features

- Add Guam to NWS WFO centric `pyiem.plot.geoplot.MapPlot`.
- Added VTEC product check for uniqueness of UGCs (#540).
- Introduce a Graphical AIRMET (G-AIRMET) decoder (#566).

### Bug Fixes

- Allow provision of already created `matplotlib.Figure` instance into the
standardized layout generator.

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
