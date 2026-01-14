<!-- markdownlint-configure-file {"MD024": { "siblings_only": true } } -->
# Changelog

All notable changes to this library are documented in this file.

## Unreleased Version

### API Changes

- Clarify in CI environment that ``fiona`` is not an actual dependency.

### New Features

- Added crude bounds checking within `pyiem.observation` to prevent out of
  reasonable bounds data from going to the database.
- Update CI testing to include python=3.14

### Bug Fixes

- Increase whitespace forgiveness of DSM parser.

## **1.26.0** (9 Dec 2025)

### API Changes

- Enforce a SHEF data model limit of 8 characters for a station identifier.
- Ween off `domain=` nomenclature for the default IEMRE domain.

### New Features

- Add an IEMRE `CONUS` alias that points back to the default domain="".
- Add IEM autoplot alias option to allow for legacy variable migration.

### Bug Fixes

- Account for a corrupted HRRR bufkit file found in MTArchive.
- Correct LSR location parsing for Guam and Pago Pago.

## **1.25.0** (30 Sep 2025)

### API Changes

- Change `NoDataFound` exception in `iemapp` to HTTP status 422.
- Mark `pyiem.util.{get_dbconn*,get_sqlalchemy_conn}` for removal in 1.26.0
- Remove `pyiem.plot.use_agg.plt` (pyplot) as it is a walking memory leak.
- Remove `pyiem.prism` per previous deprecation.
- Rename `pyiem.nws.products.vtec.skip_con` to `is_skip_con` (meh, internal).
- Support TAF Collectives by changing `prod.data: TAFReport` to
  `prod.data: list[TAFReport]` (#913).

### New Features

- Add `method=head` option to `archive_fetch` so to do quick checks.
- Drop `nh3` requirement.
- Support `BECMG`, `PROB30`, and `PROB40` TAF forecast elements (#1104).
- Support more TAF quirks and poor formatting.

### Bug Fixes

- Account for `python-metar` edge case with peak wind time being in the future.
- Correct TAF parsing edge case when segment has no equals.
- Demote a SHEF warning for a poorly encoded paired depth value.
- Fix edge case with empty scripts in autoplot vtecps type.
- Prevent unknown UGC from causing a full database write failure (#1097).
- Rework XSS detection within `webutil.iemapp`.
- Update bundled NWS CWAs (18 Mar 2025) (#1100).
- Workaround a spacing issue within LSRs that may not be fixed upstream.

## **1.24.0** (26 Jun 2025)

### API Changes

- Bundled IEM website template migrated to Bootstrap 5.
- Define `PRISM800` grid navigation for updated PRISM 800m grid.
- Mark `pyiem.prism` for removal in next release.
- Move `get_product_id()` up one class level to `WMOProduct`.
- Reclassify LSR `LANDSLIDE` typetext to code `x` (debris flow).
- Reclassify LSR `SNOW/ICE DMG` typetext to code `5` (ice related).
- Update LSR web links within Jabber messages per new
  [IEM LSR App](https://mesonet.agron.iastate.edu/lsr/).

### New Features

- Add `iailmo` (Iowa + Illinois + Missouri) `MapPlot` sector.
- Add `sa` IEMRE domain per DEP needs akrherz/iem#1173.
- Bundle a docutils based CSS to improve the iemapp help rendered HTML.
- Bundle GeoDataframes of discontinued NWS UGC Counties/Zones.  Add
  `discontinued=bool` option to `MapPlot.fill_ugcs()` to enable.
- Forgive encoded space as `+` in datetime to autoplot context.
- Introduce `appmode` flag on IEM template to control default CSS/JS inclusion.
- Introduce `pyiem.ncei.ghcnh` to process NCEI GHCNh data.
- Introduce `pyiem.ncei.igra` to process NCEI IGRA2.2 Data (#1036).
- Introduce `pyiem.nws.products.metar_util` with `metar_from_dict` helper to
  create METAR strings from dicts of data.
- Remove null byte 0x00 from WMO Products.
- Support new MCD most probabe tags (#1042).
- VTEC events are now created in the unfortunate case of a missed expansion
  or creation product in the time series.  This is a life choice made in the
  face of increasing NWS dissemination problems.

### Bug Fixes

- Account for empty strings in `vtec_ps` autoplot form type.
- Correct fontscale calculation.
- Correct offset calculation in SIGMETs.
- Correct timezone offsets for some Atlantic timezones.
- Correct web links for SPC day 2,3 convective outlook.
- Correct metadata for a number of NCEI IGRA2 sites.
- Correct SIGMET offset computation to use nautical miles.
- Fix appending `product_id` to IEM Access summary table for DSM parsing.
- Fix CWA parsing issue when lat/lon box is found.
- Fix SPC Day2 outlook link.
- Implement better conditioning on inbound text for `WMOProduct#unixtext`
- Improve multi-line PIREP report join when there is no front spaces.
- Update NCEP MRMS base URL for real-time downloads.
- Use text product issuance time, in leiu of ambiguity with invalid VTEC
  series (ie issuance was missing).

## **1.23.0** (1 Mar 2025)

### API Changes

- Drop `summary` database table processing of `max_tmpf_qc`, `min_tmpf_qc`,
  `pday_qc`, and `snow_qc`.  These are ill-designed and unused.
- Drop poorly designed `iemdb` support within `webutil.iemapp`.
- Internal refactor of `WMOProduct` timestamp processing in parent class.

### New Features

- Add `text` `pattern` support within `get_autoplot_context`.
- Bundle NWS AWIPS geodatabase valid 18 March 2025 (#1017).
- Introduce `database.sql_helper` as a hacky attempt to ease my ignorance
  with psycopg + sqlalchemy + pandas usage.
- Introduce `database.with_sqlalchemy_conn` decorator helper.
- Introduce `util.ddhhmm2datetime` helper to convert a WMO header timestamp
  to a UTC timestamp.
- Support decorated `webutil.iemapp` functions that return generators.
- Write DSM product_id to IEMAccess summary table.

### Bug Fixes

- Add color for Cold Weather Advisory (AFEEEE).
- Constrain FEMA Region 9 to CA, NV, AZ (#1007).
- Improve solar radiation summary table update within IEMAccess.
- Prevent `UGCProvider` from constantly reloading from database (#1010).
- Skip PDS cross-check for watches from Hawaii.
- Wordsmith message for Snow Squall Warnings (#1013).

## **1.22.1** (14 Jan 2025)

### API Changes

- Map `runner` user to `mesonet` for CI database support.
- Refactored PIREP data model to `pyiem.models.pirep`.

### New Features

- Add `nwsice` color ramp per suggestion.
- Retain reference to `CGIModel` schema as `environ["_cgimodel_schema"]`.
- Parse flight level within PIREPs (#1003).
- Use `akrherz/iem_database:test_data` container for integration tests.

### Bug Fixes

- Attempt more robust NWS product headline gleaning.

## **1.22.0** (2 Jan 2025)

### API Changes

- Add `pyiem.reference.StationAttributes` class to hold database attribute
  keys used.
- Discontinue raw SPS product text within the database.
- Ensure raw text products into `WMOProduct` end with a line feed.
- Move VTEC `SE` phenomena out of the default WFO jabber channels.
- Replace `requests` usage with `httpx`.
- Stop postprocessing the `MapPlot` figure into 8bit colorspace.

### New Features

- Add `allowed_as_list` option to `iemapp()` helper to stop lists.
- Add `pyiem.grid.nav` with IEM grid information in a fancy form.
- Add `MapPlot.imshow` with some optimized panel plotting.
- Add maximum risk threshold within SPC outlook message (#969).
- Add `pyiem.era5land` with IEM grid reference information.
- Add `pyiem.stage4` with grid reference information.
- Add support for plotting by FEMA Regions.
- Assign base WFO jabber channel to Tsunami Warnings (#978).
- Improvements for IEM netcdf grid navigation and handling.
- Include simple table of un-plotted states for `MapPlot(sector="nws")` #967.
- Introduce `radar_ptype` color ramp and `draw_radar_ptype_legend` for
generating plots of HRRR ptype.

### Bug Fixes

- Accomodate ancient LSRs using `TRACE` as the magnitude field.
- Add nounce to LSR autoplot link to prevent some ugliness around a NWS issue.
- Correct `MapPanel` GIS worldfile logic as upper left is center of grid cell.
- Ensure geometries going into masking helper are CCW, to mask outside of.
- Improve dev experience using `ugc.UGCProvider` (#980).
- Fix grid and affine definitions for IEMRE and MRMS.
- Properly check USDM service response prior to parsing it.
- Refine which `MWW` products are not defaulted into the main WFO Channels,
  those being VTEC codes `SC`, `MF`, and `GL`.
- Require valid wind speed and direction values going into `windrose_utils`.
- Support parsing `CLI` products circa 2007 with a bad space.
- Use more exact grid naviation for `pyiem.prism`, fixes off-by-one.

## **1.21.0** (6 Sep 2024)

### API Changes

- Discontinue persisting text product into {mcd,mpd} table storage.
- Discontinue storage of text product into sigmets, use `product_id` instead.
- Raise `IncompleteWebRequest` exception when autoplot datetime parsing fails.

### New Features

- Add `_check_dueling_tropics` VTEC check looking for TR+HU overlap (#930).
- Add IEMRE DOMAINS to support upcoming expansion.
- Add `pyiem.grid.util.grid_smear` to shift masked data to fill in missing.
- Allow `iemapp(memcachexpire)` to be a callable, called back with environ.
- Cross check WCNs against watch database storage for PDS status (#925).
- For `iemapp` if the `memcachekey=` callable returns `None`, the check of
memcache is short circuited.
- Store `product_id` for PIREPs and do some faked AFOS assignments to help.
- Support SPC afternoon Day 3 outlook (cycle assigned as 20) (#936).
- Support VTEC significance addition of Extreme Heat (XH) (#953).

### Bug Fixes

- Fix and refactor SPC `saw` parsing of watch replacement number.
- Pop kwargs `fig` on `MapPlot`.
- Use less confusing landing page at WPC for ERO.
- Use `round` instead of `int` to compute zonal stats grid navigation.

## **1.20.0** (31 May 2024)

### API Changes

- Change storage logic of SBW to not include `CAN` polygons in the case of
a CAN/CON combination update (#888).
- Depend on `docutils` for reStructedText to HTML conversion.
- Don't generate jabber messages for LSR products with more than 4 LSRs (#901).
- `util.get_autoplot_context` can now raise `IncompleteWebRequest`.
- The VTEC/SBW database storage of raw NWS product text was discontinued.
Instead, raw ``product_id`` values are stored, which can be used against IEM
web services to get the raw text. (#857)

### New Features

- Account for common AM/PM typos and off-by-one year timestamps in NWS Prods.
- Add `backgroundcolor` option to `MapPlot.plot_values`.
- Add `comprehensive_climate_index` and `temperature_humidity_index`.
- Add `imgsrc_from_row` helper for SPC outlook link generation.
- Add `parse_commas` option to `webutil.ensure_list`, so to allow comma
delimited CGI params by default.
- For pydantic schema based ``iemapp``, keys like `wfo[]` go to `wfo`.
- Introduce some pydantic based validators for web requests, experimental...
- Store `product_signature` in sbw table (requires iem-database schema update).
- Support SPC corrections for MCDs so to prevent database dups.

### Bug Fixes

- Allow for pydantic field validation to work when there's legacy `year` vs
`year1` present.
- Correct generated LSR summary link to have timestamps in UTC.
- Correct handling of `is_emergency` when done within VTEC correction (#899).
- Correct `SKC` parsing within TAFs, level is now `None` in this case (#453).
- Don't allow CF6 data from "today" or the "future" to be parsed, if missing.
- Fix numeric instability with `pyiem.plot.centered_bins` (#871).
- Forward propagate sbw database storage of VTEC issuace (#862).
- Handle edge case with NWS text product having a polygon at the end without
a trailing newline (ancient text).
- Improve NWS Text Product signature logic so to more generally match what
looks like a signature (#865).
- Improved NWS MND header logic for timestamp retrieval.
- Make better life choices attempting to glean a NWS Text Product signature.
- Prevent situation in sbw database having polygon_begin > polygon_end (#862).
- Refactor VTEC/SBW storage logic to use `vtec_year` column and operate on the
parent table (#863).
- Update link to new NWPS website.

## **1.19.0** (4 Mar 2024)

### API Changes

- Drop `pyiem.nwnformat` as it is no longer used.
- Introduce `pyiem.wmo.WMOProduct` as a lightweight class for products that
need little default processing.  `pyiem.nws.product.TextProduct` inherits.
- Remove `import *` usage from `pyiem.plot`.  This was a bad daryl mistake.
- Require `pygrib` as we add some grib processing.
- Require `pyogrio` for faster geopandas shapefile reading.

### New Features

- Add `pyiem.iemre.grb2iemre` helper to reproject a grib message onto IEMRE.
- Add `pyiem.util.archive_fetch` helper to get IEM archived resources.
- Add VTEC storage of `product_ids` (#857).
- Sync NWS VTEC colors per IEM database cross-check review.
- Update bundled NWS zones database to 5 March 2024 release (#821).

### Bug Fixes

- Account for a common autoplot context timestamp typo.
- Add a hacky `gc.collect()` within `MapPlot#close` attempting to workaround
some matplotlib memory leaking.
- Constrain a VTEC database search for expiration times not infinitely into
the future.
- Fix `iemre.reproject2iemre` to return a masked_array and handle an input
masked array.
- Fix invalid `rtrim()` usage with `removesuffix()`.
- Fix off-by-one when `grid.zs` hits a mask right at the border.
- Fix placement of GU, AK, HI, PR inset axes for sector="nws" plot.
- Improve `setuptools_scm` plumbing to avoid runtime import.
- Remove hackish website telemetry writing from a thread.
- Support a variant `Trace` value specified in LSRs.

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
