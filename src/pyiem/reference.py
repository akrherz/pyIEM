"""Reference values and dictionaries

No functional code found within this module, just a bunch of statics

.. data:: nwsli2state

    A dictionary mapping 2 letter NWSLI codes to their corresponding state
    two letter code.  For locations outside of the US, some of these are
    guesses on my part.

.. data:: nwsli2country

    A dictionary mapping 2 letter NWSLI codes to their correspionding two
    letter country code.  Some of these are sketchy.

"""

import os
import sys
from datetime import date

import pyproj

# Some z-order stuff for plotting
[
    Z_CF,
    Z_FILL,
    Z_FILL_LABEL,
    Z_CLIP,
    Z_CLIP2,
    Z_POLITICAL,
    Z_OVERLAY,
    Z_OVERLAY_LABEL,
    Z_OVERLAY2,
    Z_OVERLAY2_LABEL,
    Z_FRAME,
] = range(2, 13)

# IEM opinion on ISO 8601
ISO8601 = "%Y-%m-%dT%H:%M:%SZ"

TAF_VIS_OVER_6SM = 6.01
TRACE_VALUE = 0.0001
# Sentinel value for a VRB wind direction found in METARs
VARIABLE_WIND_DIRECTION = 0.0001
# https://github.com/twitter/twitter-text/tree/master/config
TWEET_CHARS = 280
TWEET_URL_CHARS = 23
TWITTER_RESOLUTION_INCH = (12.0, 6.75)

# Standized sizes for various plots generated
FIGSIZES = {
    "43": [10.24, 7.68],
    "86": [8, 6],
    "88": [8, 8],
    "96": [9, 6],
    "t": TWITTER_RESOLUTION_INCH,
    "169": [12.8, 7.2],
}
FIGSIZES_NAMES = {
    "43": "1024x768 (4:3)",
    "86": "800x600 (4:3)",
    "88": "800x800 (1:1)",
    "96": "900x600 (3:2)",
    "t": "Twitter Friendly (1200x675)",
    "169": "1280x720 (16:9)",
}

# Convenience
LATLON = pyproj.CRS.from_epsg(4326)
EPSG = {}
# 3467 Alaska Albers
for _epsg in [2163, 9311, 3857, 4326, 5070, 3467]:
    EPSG[_epsg] = pyproj.CRS.from_epsg(_epsg)

IA_WEST = -96.7
IA_EAST = -90.1
IA_NORTH = 43.61
IA_SOUTH = 40.37

MW_WEST = -104.2
MW_EAST = -80.1
MW_NORTH = 50.022
MW_SOUTH = 35.47

# We generally buffer things by 0.25
CONUS_WEST = -125.0
CONUS_EAST = -66.5
CONUS_NORTH = 49.75
CONUS_SOUTH = 24.25

SECTORS = {
    "conus": [CONUS_WEST, CONUS_EAST, CONUS_SOUTH, CONUS_NORTH],
    "cornbelt": [-99.0, -84.0, 37.17, 45.2],
    "highplains": [-108, -94, 40, 49.5],
    "iailin": [-97.5, -84.0, 37.0, 44.0],
    "iailmo": [-96.64, -87.5, 35.9, 43.6],
    "midwest": [MW_WEST, MW_EAST, MW_SOUTH, MW_NORTH],
    "northeast": [-87, -66, 36.5, 48],
    "sengland": [-76.7, -68.3, 39.5, 43.9],
    "northwest": [-126, -103.5, 41, 49.5],
    "southeast": [-95, -74, 24.5, 39],
    "southernplains": [-109, -88, 25.5, 40],
    "southwest": [-126, -103.5, 30.8, 41],
}
SECTORS_NAME = {
    "conus": "Contiguous US",
    "cornbelt": "Corn Belt US",
    "highplains": "High Plains",
    "iailin": "IA + IL + IN",
    "iailmo": "IA + IL + MO",
    "midwest": "Midwestern US",
    "northeast": "Northeastern US",
    "sengland": "Southern New England",
    "northwest": "Northwestern US",
    "southeast": "Southeast US",
    "southernplains": "Southern Plains US",
    "southwest": "Southwestern US",
}


# Labels for Station Attributes
class StationAttributes:
    """Used within mesosite station_attributes table."""

    CEILING = "CEILING"
    ERA5LAND_SOILTYPE = "ERA5LAND_SOILTYPE"
    FLOOR = "FLOOR"
    GHCNH_ID = "GHCNH_ID"
    HAS1MIN = "HAS1MIN"
    HAS_HML = "HAS_HML"
    HAS_PHOUR = "HAS_PHOUR"
    HASTAF = "HASTAF"
    IS_AWOS = "IS_AWOS"
    IS_CCOOP = "IS_CCOOP"
    MAPS_TO = "MAPS_TO"
    METAR_RESET_MINUTE = "METAR_RESET_MINUTE"
    NO_4INCH = "NO_4INCH"
    PEDTS = "PEDTS"
    SHEF_6HR_SRC = "SHEF_6HR_SRC"
    TRACKS_STATION = "TRACKS_STATION"
    WAS = "WAS"


txt2drct = {
    "N": 360,
    "North": 360,
    "NNE": 25,
    "NE": 45,
    "ENE": 70,
    "E": 90,
    "East": 90,
    "ESE": 115,
    "SE": 135,
    "SSE": 155,
    "S": 180,
    "South": 180,
    "SSW": 205,
    "SW": 225,
    "WSW": 250,
    "W": 270,
    "West": 270,
    "WNW": 295,
    "NW": 315,
    "NNW": 335,
}


hailsize = {
    "0.25": "pea",
    "0.50": "mothball",
    "0.75": "penny",
    "0.88": "nickel",
    "1.00": "quarter",
    "1.25": "half dollar",
    "1.50": "ping pong ball",
    "1.75": "golf ball",
    "2.00": "egg",
    "2.50": "tennis ball",
    "2.75": "baseball",
    "3.00": "teacup",
    "4.00": "grapefruit",
    "4.50": "softball",
}

# Lookup table for implementation dates of VTEC polygons
VTEC_POLYGON_DATES = {
    "DS.W": date(2018, 7, 5),
    "DS.Y": date(2018, 7, 5),
    "EW.W": date(2022, 1, 1),  # tbd
    "FA.W": date(2007, 10, 1),
    "FA.Y": date(2007, 10, 1),
    "FF.W": date(2007, 10, 1),
    "FL.A": date(2022, 1, 1),  # tbd
    "FL.W": date(2022, 1, 1),  # lolz
    "FL.Y": date(2022, 1, 1),  # lolz
    "MA.W": date(2007, 10, 1),
    "SQ.W": date(2022, 1, 1),  # tbd
    "SV.W": date(2007, 10, 1),
    "TO.W": date(2007, 10, 1),
}

# A dictionary mapping LSR textual types found in the raw LSR reports to a
# single character identifier.  This is done to simplify some backend stuff
# done with IEM Cow and the database.  This is very lame, but alas
lsr_events = {
    "BLOWING SNOW": "a",
    "DRIFTING SNOW": "a",
    "HIGH SUST WINDS": "A",
    "HIGH WIND": "A",
    "MRN HIGH WIND": "A",
    "MRN STRONG WIND": "A",
    "STRONG WIND GUST": "A",
    "DOWNBURST": "B",
    "FUNNEL CLOUD": "C",
    "FUNNEL": "C",
    "TSTM WND DMG": "D",
    "TREES DOWN": "D",
    "TSTM WIND DMG": "D",
    "FLOOD": "E",
    "FLOODING": "E",
    "FLASH FLOOD": "F",
    "MAJ FLASH FLD": "F",
    "TSTM WND GST": "G",
    "TSTM WIND": "G",
    "TSTM WIND GST": "G",
    "MRN TSTM WIND": "G",
    "MRN TSTMWIND": "G",
    "HAIL": "H",
    "MRN HAIL": "h",
    "MARINE HAIL": "h",
    "EXCESSIVE HEAT": "I",
    "HEAT": "I",
    "EXTREME HEAT": "I",
    "MRN HVY FZG SPRY": "i",
    "DENSE FOG": "J",
    "MRN DENSE FOG": "J",
    "FOG": "J",
    "VOG": "J",
    "FREEZING FOG": "J",
    "DENSE SMOKE": "j",
    "LIGHTNING STRIKE": "K",
    "MRN LIGHTNING": "K",
    "LIGHTNING": "L",
    "MARINE TSTM WND": "M",
    "DUST DEVIL": "m",
    "MARINE TSTM WIND": "M",
    "NON-TSTM WND GST": "N",
    "NON TSTM WND GST": "N",
    "NON-TSTM WND DMG": "O",
    "NON TSTM WND DMG": "O",
    "NON-TSTM DMG GST": "O",
    "NON TSTM DMG GST": "O",
    "NON-TSTM DMG": "O",
    "NON-TSTM WND": "O",
    "HIGH WINDS": "O",
    "WND DAMAGE": "O",
    "LANDSLIDE": "x",
    "RIP CURRENTS": "P",
    "RIP CURRENT": "P",
    "HIGH SURF": "P",
    "MISC MRN/SRF HZD": "P",
    "TROPICAL STORM": "Q",
    "SNOW SQUALL": "q",
    "HEAVY RAIN": "R",
    "RAIN": "R",
    "SNOW": "S",
    "LAKE-EFFECT SNOW": "S",
    "STORM TOTAL SNOW": "S",
    "SLEET": "s",
    "MODERATE SLEET": "s",
    "HEAVY SLEET": "s",
    "HEAVY SNOW": "S",
    "TORNADO": "T",
    "SNEAKER WAVE": "t",
    "WILDFIRE": "U",
    "FIRE": "U",
    "LAKESHORE FLOOD": "u",
    "AVALANCHE": "V",
    "COASTAL FLOOD": "v",
    "WALL CLOUD": "X",
    "DEBRIS FLOW": "x",
    "ICE JAM": "x",
    "ICE JAM FLOODING": "x",
    "WATER SPOUT": "W",
    "WATERSPOUT": "W",
    "LANDSPOUT": "W",
    "TSUNAMI": "y",
    "BLIZZARD": "Z",
    "VOLCANIC ASHFALL": "z",
    "VOLCANIC ASH": "z",
    "HURRICANE": "0",
    "TROPICAL CYCLONE": "0",
    "HURCN/TYPHOON": "0",
    "MRN HURCN/TYPH": "0",
    "STORM SURGE": "1",
    "STORM SURGE/TIDE": "1",
    "BLOWING DUST": "2",
    "DUST STORM": "2",
    "SPRINKLES - FEW": "3",
    "HIGH ASTR TIDES": "4",
    "ASTRON LOW TIDE": "4",
    "LOW ASTR TIDES": "4",
    "FREEZING RAIN": "5",
    "FREEZING DRIZZLE": "5",
    "ICE STORM": "5",
    "ICING ON ROADS": "5",
    "SNOW/ICE DMG": "5",
    "EXTREME COLD": "6",
    "COLD/WIND CHILL": "6",
    "FREEZE": "6",
    "FROST/FREEZE": "6",
    "EXTR WIND CHILL": "7",
    "EXT COLD/WND CHL": "7",
    "WIND CHILL": "7",
    "DROUGHT": "8",
    "SEICHE": "9",
}


offsets = {
    "GMT": 0,
    "UTC": 0,
    "CVT": 1,
    "CHDT": -9,
    "PWT": -9,
    "CHST": -10,
    "CHUT": -10,
    "LST": -10,
    "KOST": -11,
    "PONT": -11,
    "MHT": -12,
    "ADT": 3,
    "VDT": 3,
    "VST": 4,
    "EDT": 4,
    "AST": 4,
    "CDT": 5,
    "EST": 5,
    "MDT": 6,
    "CST": 6,
    "PDT": 7,
    "MST": 7,
    "AKDT": 8,
    "PST": 8,
    "HDT": 9,
    "AKST": 9,
    "HST": 10,
    "SST": 11,
    "PLT": -5,
    "GSST": -4,
}

wfo_dict = {
    "ABQ": {"name": "ALBUQUERQUE", "region": "SR"},
    "ABR": {"name": "ABERDEEN", "region": "CR"},
    "AFC": {"name": "ANCHORAGE", "region": "PR"},
    "AFG": {"name": "FAIRBANKS", "region": "PR"},
    "AJK": {"name": "JUNEAU", "region": "PR"},
    "AKQ": {"name": "WAKEFIELD", "region": "ER"},
    "ALY": {"name": "ALBANY", "region": "ER"},
    "AMA": {"name": "AMARILLO", "region": "SR"},
    "APX": {"name": "GAYLORD", "region": "CR"},
    "ARX": {"name": "LA_CROSSE", "region": "CR"},
    "BGM": {"name": "BINGHAMTON", "region": "ER"},
    "BIS": {"name": "BISMARCK", "region": "CR"},
    "BMX": {"name": "BIRMINGHAM", "region": "SR"},
    "BOI": {"name": "BOISE", "region": "WR"},
    "BOU": {"name": "DENVER", "region": "CR"},
    "BOX": {"name": "TAUNTON", "region": "ER"},
    "BRO": {"name": "BROWNSVILLE", "region": "SR"},
    "BTV": {"name": "BURLINGTON", "region": "ER"},
    "BUF": {"name": "BUFFALO", "region": "ER"},
    "BYZ": {"name": "BILLINGS", "region": "WR"},
    "CAE": {"name": "COLUMBIA", "region": "SR"},
    "CAR": {"name": "CARIBOU", "region": "ER"},
    "CHS": {"name": "CHARLESTON", "region": "SR"},
    "CLE": {"name": "CLEVELAND", "region": "ER"},
    "CRP": {"name": "CORPUS_CHRISTI", "region": "SR"},
    "CTP": {"name": "STATE_COLLEGE", "region": "ER"},
    "CYS": {"name": "CHEYENNE", "region": "CR"},
    "DDC": {"name": "DODGE_CITY", "region": "CR"},
    "DLH": {"name": "DULUTH", "region": "CR"},
    "DMX": {"name": "DES_MOINES", "region": "CR"},
    "DTX": {"name": "DETROIT", "region": "CR"},
    "DVN": {"name": "QUAD_CITIES_IA", "region": "CR"},
    "EAX": {"name": "KANSAS_CITY/PLEASANT_HILL", "region": "CR"},
    "EKA": {"name": "EUREKA", "region": "WR"},
    "EPZ": {"name": "EL_PASO_TX/SANTA_TERESA", "region": "SR"},
    "EWX": {"name": "AUSTIN/SAN_ANTONIO", "region": "SR"},
    "EYW": {"name": "KEY_WEST", "region": "SR"},
    "FFC": {"name": "PEACHTREE_CITY", "region": "SR"},
    "FGF": {"name": "EASTERN_NORTH_DAKOTA", "region": "CR"},
    "FGZ": {"name": "FLAGSTAFF", "region": "WR"},
    "FSD": {"name": "SIOUX_FALLS", "region": "CR"},
    "FWD": {"name": "DALLAS/FORT_WORTH", "region": "SR"},
    "GGW": {"name": "GLASGOW", "region": "WR"},
    "GID": {"name": "HASTINGS", "region": "CR"},
    "GJT": {"name": "GRAND_JUNCTION", "region": "CR"},
    "GLD": {"name": "GOODLAND", "region": "CR"},
    "GRB": {"name": "GREEN_BAY", "region": "CR"},
    "GRR": {"name": "GRAND_RAPIDS", "region": "CR"},
    "GSP": {"name": "GREENVILLE/SPARTANBURG", "region": "ER"},
    "GUM": {"name": "Guam", "region": "SR"},
    "GYX": {"name": "GRAY", "region": "ER"},
    "HFO": {"name": "HONOLULU", "region": "PR"},
    "HGX": {"name": "HOUSTON/GALVESTON", "region": "SR"},
    "HNX": {"name": "SAN_JOAQUIN_VALLEY/HANFORD", "region": "WR"},
    "HUN": {"name": "Huntsville", "region": "SR"},
    "ICT": {"name": "WICHITA", "region": "CR"},
    "ILM": {"name": "WILMINGTON", "region": "ER"},
    "ILN": {"name": "WILMINGTON", "region": "ER"},
    "ILX": {"name": "LINCOLN", "region": "CR"},
    "IND": {"name": "INDIANAPOLIS", "region": "CR"},
    "IWX": {"name": "NORTHERN_INDIANA", "region": "CR"},
    "JAN": {"name": "JACKSON", "region": "SR"},
    "JAX": {"name": "JACKSONVILLE", "region": "SR"},
    "JKL": {"name": "JACKSON", "region": "ER"},
    "JSJ": {"name": "San Juan", "region": "SR"},
    "LBF": {"name": "NORTH_PLATTE", "region": "CR"},
    "LCH": {"name": "LAKE_CHARLES", "region": "SR"},
    "LIX": {"name": "NEW_ORLEANS", "region": "SR"},
    "LKN": {"name": "ELKO", "region": "WR"},
    "LMK": {"name": "LOUISVILLE", "region": "CR"},
    "LOT": {"name": "CHICAGO", "region": "CR"},
    "LOX": {"name": "LOS_ANGELES/OXNARD", "region": "WR"},
    "LSX": {"name": "ST_LOUIS", "region": "CR"},
    "LUB": {"name": "LUBBOCK", "region": "SR"},
    "LWX": {"name": "BALTIMORE_MD/_WASHINGTON_DC", "region": "ER"},
    "LZK": {"name": "LITTLE_ROCK", "region": "SR"},
    "MAF": {"name": "MIDLAND/ODESSA", "region": "SR"},
    "MEG": {"name": "MEMPHIS", "region": "SR"},
    "MFL": {"name": "MIAMI", "region": "SR"},
    "MFR": {"name": "MEDFORD", "region": "WR"},
    "MHX": {"name": "NEWPORT/MOREHEAD_CITY", "region": "ER"},
    "MKX": {"name": "MILWAUKEE/SULLIVAN", "region": "CR"},
    "MLB": {"name": "MELBOURNE", "region": "SR"},
    "MOB": {"name": "MOBILE", "region": "SR"},
    "MPX": {"name": "TWIN_CITIES/CHANHASSEN", "region": "CR"},
    "MQT": {"name": "MARQUETTE", "region": "CR"},
    "MRX": {"name": "MORRISTOWN", "region": "SR"},
    "MSO": {"name": "MISSOULA", "region": "WR"},
    "MTR": {"name": "SAN_FRANCISCO", "region": "WR"},
    "OAX": {"name": "OMAHA/VALLEY", "region": "CR"},
    "OHX": {"name": "NASHVILLE", "region": "SR"},
    "OKX": {"name": "NEW_YORK", "region": "ER"},
    "OTX": {"name": "SPOKANE", "region": "WR"},
    "OUN": {"name": "NORMAN", "region": "SR"},
    "PAH": {"name": "PADUCAH", "region": "CR"},
    "PBZ": {"name": "PITTSBURGH", "region": "ER"},
    "PDT": {"name": "PENDLETON", "region": "WR"},
    "PHI": {"name": "MOUNT_HOLLY", "region": "ER"},
    "PIH": {"name": "POCATELLO/IDAHO_FALLS", "region": "WR"},
    "PQR": {"name": "PORTLAND", "region": "WR"},
    "PSR": {"name": "PHOENIX", "region": "WR"},
    "PUB": {"name": "PUEBLO", "region": "CR"},
    "RAH": {"name": "RALEIGH", "region": "ER"},
    "REV": {"name": "RENO", "region": "WR"},
    "RIW": {"name": "RIVERTON", "region": "WR"},
    "RLX": {"name": "CHARLESTON", "region": "ER"},
    "RNK": {"name": "BLACKSBURG", "region": "ER"},
    "SEW": {"name": "SEATTLE", "region": "WR"},
    "SGF": {"name": "SPRINGFIELD", "region": "CR"},
    "SGX": {"name": "SAN_DIEGO", "region": "WR"},
    "SHV": {"name": "SHREVEPORT", "region": "SR"},
    "SJT": {"name": "SAN_ANGELO", "region": "SR"},
    "SJU": {"name": "SAN_JUAN", "region": "SR"},
    "SLC": {"name": "SALT_LAKE_CITY", "region": "WR"},
    "STO": {"name": "SACRAMENTO", "region": "WR"},
    "TAE": {"name": "TALLAHASSEE", "region": "SR"},
    "TBW": {"name": "TAMPA_BAY_AREA/RUSKIN", "region": "SR"},
    "TFX": {"name": "GREAT_FALLS", "region": "WR"},
    "TOP": {"name": "TOPEKA", "region": "CR"},
    "TSA": {"name": "TULSA", "region": "WR"},
    "TWC": {"name": "TUCSON", "region": "WR"},
    "UNR": {"name": "RAPID_CITY", "region": "CR"},
    "VEF": {"name": "LAS_VEGAS", "region": "WR"},
}

# State bounds (buffered by 0.2 degrees)
#
# ! BE CAREFUL WITH ALASKA and Iowa
#
# with data as (
#    select state_abbr, st_extent(the_geom) as ext from states
#    GROUP by state_abbr)
#
# SELECT '"'||state_abbr||'": ['||
# round((ST_xmin(ext) - 0.2)::numeric, 2) ||', '||
# round((ST_ymin(ext) - 0.2)::numeric, 2) ||', '||
# round((ST_xmax(ext) + 0.2)::numeric, 2) ||', '||
# round((ST_ymax(ext) + 0.2)::numeric, 2) ||'],'
# from data ORDER by state_abbr ASC
#
state_bounds = {
    "AK": [-178.43, 50, -129.81, 70],  # manually adjusted
    "AL": [-88.67, 30.02, -84.69, 35.21],
    "AR": [-94.82, 32.80, -89.44, 36.70],
    "AS": [-171.05, -14.374, -169.4, -11.08],
    "AZ": [-115.02, 31.13, -108.85, 37.20],
    "CA": [-124.61, 32.33, -113.93, 42.21],
    "CO": [-109.26, 36.79, -101.84, 41.20],
    "CT": [-73.93, 40.79, -71.59, 42.25],
    "DC": [-77.32, 38.59, -76.71, 39.20],
    "DE": [-75.99, 38.25, -74.85, 40.04],
    "FL": [-87.83, 24.34, -79.83, 31.20],
    "GA": [-85.81, 30.16, -80.64, 35.20],
    "GU": [144.58, 13.2, 144.94, 13.7],
    "HI": [-160.45, 18.71, -154.61, 22.44],
    "IA": [IA_WEST, IA_SOUTH, IA_EAST, IA_NORTH],
    "ID": [-117.44, 41.79, -110.84, 49.20],
    "IL": [-91.71, 36.77, -87.30, 42.71],
    "IN": [-88.30, 37.57, -84.58, 41.96],
    "KS": [-102.25, 36.79, -94.39, 40.20],
    "KY": [-89.77, 36.30, -81.76, 39.35],
    "LA": [-94.24, 28.73, -88.62, 33.22],
    "MA": [-73.71, 41.04, -69.73, 43.09],
    "MD": [-79.69, 37.72, -74.85, 39.92],
    "ME": [-71.28, 42.86, -66.75, 47.66],
    "MI": [-90.62, 41.50, -82.22, 48.39],
    "MN": [-97.44, 43.30, -89.28, 49.58],
    "MO": [-95.97, 35.80, -88.90, 40.81],
    "MS": [-91.86, 29.97, -87.90, 35.20],
    "MT": [-116.25, 44.16, -103.84, 49.20],
    "NC": [-84.52, 33.64, -75.26, 36.79],
    "ND": [-104.25, 45.74, -96.35, 49.20],
    "NE": [-104.25, 39.80, -95.11, 43.20],
    "NH": [-72.76, 42.50, -70.51, 45.51],
    "NJ": [-75.76, 38.73, -73.69, 41.56],
    "NM": [-109.25, 31.13, -102.80, 37.20],
    "NV": [-120.21, 34.80, -113.84, 42.20],
    "NY": [-79.96, 40.30, -71.66, 45.22],
    "OH": [-85.02, 38.20, -80.32, 42.18],
    "OK": [-103.20, 33.42, -94.23, 37.20],
    "OR": [-124.77, 41.79, -116.26, 46.44],
    "PA": [-80.72, 39.52, -74.49, 42.47],
    "PR": [-67.24, 17.95, -65.59, 18.52],
    "RI": [-72.09, 40.95, -70.92, 42.22],
    "SC": [-83.55, 31.85, -78.35, 35.42],
    "SD": [-104.26, 42.28, -96.24, 46.15],
    "TN": [-90.51, 34.78, -81.45, 36.88],
    "TX": [-106.85, 25.64, -93.31, 36.70],
    "UT": [-114.25, 36.80, -108.84, 42.20],
    "VA": [-83.88, 36.34, -75.04, 39.67],
    "VI": [-65.16, 17.62, -64.51, 18.46],
    "VT": [-73.64, 42.53, -71.26, 45.22],
    "WA": [-124.93, 45.34, -116.72, 49.20],
    "WI": [-93.09, 42.29, -86.61, 47.20],
    "WV": [-82.84, 37.00, -77.52, 40.84],
    "WY": [-111.26, 40.79, -103.85, 45.21],
}

# WFO bounds
#
# ! BE CAREFUL WITH AFC, CHECK THE BOUNDS!
#
# with data as (
#    select wfo, st_extent(geom) as ext from ugcs
#    where end_ts is null GROUP by wfo)
# SELECT '"'||wfo||'": ['||
# round((ST_xmin(ext) - 0.2)::numeric, 2) ||', '||
# round((ST_ymin(ext) - 0.2)::numeric, 2) ||', '||
# round((ST_xmax(ext) + 0.2)::numeric, 2) ||', '||
# round((ST_ymax(ext) + 0.2)::numeric, 2) ||'],'
# from data WHERE length(wfo) = 3 ORDER by wfo ASC;
wfo_bounds = {
    "ABQ": [-109.25, 32.32, -102.80, 37.20],
    "ABR": [-102.20, 43.30, -95.90, 46.22],
    "AFC": [-179.35, 51.02, -139.81, 63.75],
    "AFG": [-177.40, 61.02, -140.80, 74.91],
    "AJK": [-144.22, 53.87, -129.78, 60.87],
    "AKQ": [-78.94, 35.61, -74.11, 38.90],
    "ALY": [-75.42, 41.24, -72.23, 44.32],
    "AMA": [-103.24, 34.55, -99.80, 37.20],
    "APX": [-87.17, 43.61, -82.06, 47.00],
    "ARX": [-93.25, 42.31, -89.40, 45.58],
    "BGM": [-77.95, 40.70, -74.16, 43.81],
    "BIS": [-104.25, 45.74, -97.81, 49.20],
    "BMX": [-88.62, 31.42, -84.69, 34.73],
    "BOI": [-120.31, 41.79, -113.73, 45.77],
    "BOU": [-107.07, 38.32, -101.85, 41.20],
    "BOX": [-73.27, 40.27, -68.90, 43.11],
    "BRO": [-99.65, 25.64, -95.79, 27.56],
    "BTV": [-76.04, 43.02, -71.27, 45.22],
    "BUF": [-80.05, 41.80, -74.67, 45.20],
    "BYZ": [-111.80, 43.82, -102.74, 47.06],
    "CAE": [-82.85, 32.60, -79.58, 35.27],
    "CAR": [-70.52, 43.30, -66.69, 47.66],
    "CHS": [-82.45, 30.91, -78.43, 33.71],
    "CLE": [-84.08, 40.04, -79.41, 42.68],
    "CRP": [-100.41, 26.88, -95.34, 29.30],
    "CTP": [-79.81, 39.52, -75.56, 42.20],
    "CYS": [-108.13, 40.80, -102.41, 43.70],
    "DDC": [-102.24, 36.79, -98.15, 39.33],
    "DLH": [-94.99, 45.18, -89.21, 48.91],
    "DMX": [-95.87, 40.37, -91.86, 43.70],
    "DTX": [-84.81, 41.51, -81.92, 44.39],
    "DVN": [-92.61, 39.99, -88.96, 42.88],
    "EAX": [-95.97, 37.83, -92.09, 40.80],
    "EKA": [-126.01, 38.47, -122.14, 42.20],
    "EPZ": [-109.25, 30.43, -104.61, 34.55],
    "EWX": [-101.96, 28.00, -96.36, 31.23],
    "FFC": [-85.80, 31.58, -81.80, 35.19],
    "FGF": [-100.05, 45.56, -94.21, 49.59],
    "FGZ": [-113.55, 33.28, -108.85, 37.20],
    "FSD": [-99.73, 42.01, -94.65, 44.83],
    "FWD": [-99.32, 30.26, -95.06, 34.19],
    "GGW": [-109.09, 46.34, -103.84, 49.20],
    "GID": [-100.42, 38.93, -97.17, 41.94],
    "GJT": [-111.11, 36.79, -105.98, 41.20],
    "GLD": [-103.37, 38.06, -99.40, 40.64],
    "GRB": [-90.52, 43.59, -86.09, 46.50],
    "GRR": [-87.35, 41.87, -83.93, 44.48],
    "GSP": [-84.24, 33.75, -79.98, 36.49],
    "GUM": [132.01, 4.48, 172.36, 20.75],
    "GYX": [-72.76, 42.50, -68.26, 46.18],
    "HFO": [-161.12, 18.05, -153.95, 23.10],
    "HGX": [-97.16, 27.46, -93.81, 31.79],
    "HNX": [-121.45, 34.59, -117.42, 38.38],
    "HPA": [-164.45, 14.72, -150.61, 26.44],
    "HUN": [-88.40, 33.66, -85.31, 35.61],
    "ICT": [-99.24, 36.80, -94.87, 39.42],
    "ILM": [-80.49, 32.60, -76.77, 35.15],
    "ILN": [-85.64, 38.12, -81.96, 41.02],
    "ILX": [-91.11, 38.37, -87.30, 41.43],
    "IND": [-87.96, 38.21, -84.60, 40.94],
    "IWX": [-87.30, 40.11, -83.68, 42.44],
    "JAN": [-92.34, 30.71, -88.05, 34.32],
    "JAX": [-83.51, 28.76, -79.78, 32.17],
    "JKL": [-85.26, 36.38, -81.77, 38.72],
    "KEY": [-83.49, 23.32, -79.34, 25.80],
    "LBF": [-102.99, 40.15, -98.10, 43.20],
    "LCH": [-94.93, 27.89, -90.88, 31.72],
    "LIX": [-92.02, 27.72, -87.74, 31.57],
    "LKN": [-119.53, 37.84, -113.84, 42.20],
    "LMK": [-87.34, 36.41, -83.63, 39.12],
    "LOT": [-89.89, 40.20, -86.70, 42.70],
    "LOX": [-123.09, 32.60, -117.40, 36.00],
    "LSX": [-93.04, 36.85, -88.49, 40.50],
    "LUB": [-103.26, 32.76, -99.79, 34.95],
    "LWX": [-80.01, 37.34, -75.57, 39.92],
    "LZK": [-94.67, 32.96, -90.55, 36.70],
    "MAF": [-105.55, 28.77, -100.46, 34.30],
    "MEG": [-91.35, 33.45, -87.72, 36.83],
    "MFL": [-83.12, 24.40, -78.83, 27.41],
    "MFR": [-126.25, 40.79, -119.04, 44.23],
    "MHX": [-78.40, 33.71, -74.59, 36.43],
    "MKX": [-90.63, 42.26, -86.82, 44.18],
    "MLB": [-82.16, 26.76, -78.85, 29.68],
    "MOB": [-89.54, 29.00, -85.78, 32.51],
    "MPX": [-96.65, 43.30, -90.48, 46.57],
    "MQT": [-90.64, 44.89, -83.27, 48.51],
    "MRX": [-86.07, 34.78, -81.41, 37.40],
    "MSO": [-117.26, 44.03, -111.15, 49.20],
    "MTR": [-125.31, 35.45, -120.01, 39.15],
    "NH1": [-120.67, -3.64, -76.81, 32.73],
    "NH2": [-98.09, 6.79, -54.78, 31.21],
    "OAX": [-98.51, 39.80, -94.71, 43.08],
    "OHX": [-88.58, 34.79, -84.46, 36.88],
    "OKX": [-74.96, 39.69, -71.19, 41.91],
    "ONA": [-80.72, 30.79, -64.79, 44.37],
    "ONP": [-131.31, 28.80, -116.31, 48.72],
    "OTX": [-121.72, 45.66, -114.76, 49.20],
    "OUN": [-100.25, 33.20, -95.47, 37.20],
    "PAH": [-91.88, 36.14, -86.57, 38.81],
    "PBZ": [-82.43, 38.76, -78.51, 41.83],
    "PDT": [-122.35, 43.06, -116.26, 47.80],
    "PHI": [-76.64, 38.02, -73.10, 41.56],
    "PIH": [-115.51, 41.79, -110.56, 45.91],
    "PPG": [-171.25, -14.57, -169.22, -10.88],
    "PQR": [-125.90, 43.15, -121.21, 46.99],
    "PSR": [-116.67, 31.84, -109.80, 34.52],
    "PUB": [-107.35, 36.79, -101.84, 39.58],
    "RAH": [-80.72, 34.35, -77.03, 36.74],
    "REV": [-121.53, 37.26, -117.10, 42.20],
    "RIW": [-111.35, 40.79, -105.81, 45.31],
    "RLX": [-83.54, 36.76, -79.15, 40.13],
    "RNK": [-82.12, 35.80, -78.04, 38.47],
    "SEW": [-126.52, 46.12, -120.45, 49.20],
    "SGF": [-95.29, 36.30, -90.82, 38.89],
    "SGX": [-118.91, 32.23, -115.75, 35.02],
    "SHV": [-95.87, 30.83, -91.67, 34.71],
    "SJT": [-102.58, 30.09, -98.21, 33.60],
    "SJU": [-68.20, 16.80, -63.80, 19.70],
    "SLC": [-114.25, 36.80, -109.67, 42.20],
    "STO": [-123.27, 36.93, -119.40, 41.38],
    "STU": [-171.92, -15.25, -168.55, -10.21],
    "TAE": [-86.60, 28.38, -82.68, 32.19],
    "TBW": [-84.25, 25.77, -80.74, 29.79],
    "TFX": [-114.27, 44.16, -108.04, 49.20],
    "TOP": [-98.13, 37.84, -94.86, 40.20],
    "TSA": [-97.26, 33.67, -93.10, 37.20],
    "TWC": [-113.53, 31.13, -108.85, 33.98],
    "UNR": [-106.22, 42.80, -99.33, 46.15],
    "VEF": [-118.99, 33.83, -112.33, 38.88],
}

fema_region_bounds = {
    1: [-73.93, 40.75, -66.69, 47.66],
    2: [-79.96, 17.48, -64.37, 45.21],
    3: [-83.88, 36.34, -74.50, 42.47],
    4: [-91.84, 24.76, -75.26, 39.34],
    5: [-97.43, 36.79, -80.32, 49.57],
    6: [-109.25, 25.65, -88.82, 37.20],
    7: [-104.26, 35.79, -88.91, 43.70],
    8: [-116.26, 36.79, -96.24, 49.20],
    9: [-124.6, 31.1, -108.8, 42.20],  # Just CA, AZ, NV
    10: [-179.43, 41.79, -110.85, 71.63],
}

# State FIPS
state_fips = {
    1: "AL",
    2: "AK",
    4: "AZ",
    5: "AR",
    6: "CA",
    8: "CO",
    9: "CT",
    10: "DE",
    11: "DC",
    12: "FL",
    13: "GA",
    15: "HI",
    16: "ID",
    17: "IL",
    18: "IN",
    19: "IA",
    20: "KS",
    21: "KY",
    22: "LA",
    23: "ME",
    24: "MD",
    25: "MA",
    26: "MI",
    27: "MN",
    28: "MS",
    29: "MO",
    30: "MT",
    31: "NE",
    32: "NV",
    33: "NH",
    34: "NJ",
    35: "NM",
    36: "NY",
    37: "NC",
    38: "ND",
    39: "OH",
    40: "OK",
    41: "OR",
    42: "PA",
    72: "PR",
    44: "RI",
    45: "SC",
    46: "SD",
    47: "TN",
    48: "TX",
    49: "UT",
    50: "VT",
    51: "VA",
    78: "VI",
    53: "WA",
    54: "WV",
    55: "WI",
    56: "WY",
}

IEMVARS = {
    "tmpf": {
        "name": "Air Temperature[F]",
        "type": "number",
        "description": "Air Temperature at 2m AGL",
    },
    "sknt": {
        "name": "Wind Speed[kt]",
        "type": "number",
        "description": "Wind Speed",
    },
    "gust": {
        "name": "Wind Gust[kt]",
        "type": "number",
        "description": "Wind Gust",
    },
    "drct": {
        "name": "Wind Direction[deg]",
        "type": "number",
        "description": "Wind Direction",
    },
    "local_valid": {
        "name": "Observation Valid",
        "type": "datetime",
        "description": "Observation Valid Time",
    },
    "utc_valid": {
        "name": "Observation Valid UTC",
        "type": "datetime",
        "description": "Observation Valid Time UTC",
    },
}
DATADIR = os.sep.join([os.path.dirname(__file__), "data", "reference"])

# The below are dynamically generated on-demand, but are hard coded here
# so that code introspection works.  Likely a better way!
shef_physical_codes = {}
shef_send_codes = {}
shef_english_units = {}
shef_standard_units = {}
shef_table7 = {}
state_names = {}
prodDefinitions = {}
ncei_state_codes = {}
nwsli2state = {}
nwsli2country = {}
name2pytz = {}
centertext = {}


class Wrapper:
    """Some Magic Here."""

    _onthefly_dict = [
        "igra2icao",
        "shef_english_units",
        "shef_standard_units",
        "shef_physical_codes",
        "shef_send_codes",
        "shef_table7",
        "state_names",
        "prodDefinitions",
        "ncei_state_codes",
        "nwsli2state",
        "nwsli2country",
        "name2pytz",
        "centertext",
    ]

    def __init__(self, wrapped):
        """Keep a reference."""
        self.__all__ = []
        self.wrapped = wrapped

    def _reader(self, name):
        """read dictionary."""
        res = {}
        with open(os.path.join(DATADIR, f"{name}.txt"), encoding="utf8") as fh:
            for line in fh:
                if line.strip() == "" or line.startswith("#"):
                    continue
                tokens = line.strip().split(" ", 1)
                res[tokens[0]] = tokens[1]
        return res

    def __getattr__(self, name):
        """Magic method to build dicts on-demand."""
        res = getattr(self.wrapped, name, None)
        # if empty dict and is something we can build on the fly, then do it
        if not res and name in self._onthefly_dict:
            val = self._reader(name)
            setattr(self.wrapped, name, val)
            return val
        return res


# shrug, workaround sphinx autodoc issue with my __getattr__ catchall above
__annotations__ = []
sys.modules[__name__] = Wrapper(sys.modules[__name__])
