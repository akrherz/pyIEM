"""
Processing of GINI formatted data found on NOAAPORT
"""
import struct
import math
import zlib
from datetime import timezone, datetime
import os

import pyproj
import numpy as np
from pyiem.util import LOG

DATADIR = os.sep.join([os.path.dirname(__file__), "../data"])
M_PI_2 = 1.57079632679489661923
M_PI = 3.14159265358979323846
RE_METERS = 6371200.0
ENTITIES = [
    "UNK",
    "UNK",
    "MISC",
    "JERS",
    "ERS",
    "POES",
    "COMP",
    "DMSP",
    "GMS",
    "METEOSAT",
    "GOES7",
    "GOES8",
    "GOES9",
    "GOES10",
    "GOES11",
    "GOES12",
    "GOES13",
    "GOES14",
    "GOES15",
]
LABELS = [
    "UNK",
    "UNK",
    "MISC",
    "JERS",
    "ERS",
    "POES",
    "COMP",
    "DMSP",
    "GMS",
    "METEOSAT",
    "GOES",
    "GOES",
    "GOES",
    "GOES",
    "GOES",
    "GOES",
    "GOES",
    "GOES",
    "GOES",
]
CHANNELS = [
    "",
    "VIS",
    "3.9",
    "WV",
    "IR",
    "12",
    "13.3",
    "1.3",
    "U8",
    "U9",
    "U10",
    "U11",
    "U12",
    "LI",
    "PW",
    "SKIN",
    "CAPE",
    "TSURF",
    "WINDEX",
]
for _u in range(22, 100):
    CHANNELS.append(f"U{_u}")
SECTORS = [
    "NHCOMP",
    "EAST",
    "WEST",
    "AK",
    "AKNAT",
    "HI",
    "HINAT",
    "PR",
    "PRNAT",
    "SUPER",
    "NHCOMP",
    "CCONUS",
    "EFLOAT",
    "WFLOAT",
    "CFLOAT",
    "PFLOAT",
]

AWIPS_GRID_GUESS = {
    "A": 207,
    "B": 203,
    "E": 211,
    "F": 0,
    "H": 208,
    "I": 204,
    "N": 0,
    "P": 210,
    "Q": 205,
    "W": 211,
}

AWIPS_GRID = {
    "TIGB": 203,
    "TIGE": 211,
    "TIGW": 211,
    "TIGH": 208,
    "TIGP": 210,
    "TIGA": 207,
    "TIGI": 204,
    "TIGQ": 205,
    "TICF": 201,
}


def uint24(data):
    """convert three byte data that represents an unsigned int"""
    u = int(struct.unpack(">B", data[0:1])[0]) << 16
    u += int(struct.unpack(">B", data[1:2])[0]) << 8
    u += int(struct.unpack(">B", data[2:3])[0])
    return u


def int24(data):
    """Convert to int."""
    u = int(struct.unpack(">B", data[0:1])[0] & 127) << 16
    u += int(struct.unpack(">B", data[1:2])[0]) << 8
    u += int(struct.unpack(">B", data[2:3])[0])
    if (struct.unpack(">B", data[0:1])[0] & 128) != 0:
        u *= -1
    return u


def get_ir_ramp():
    """Return a np 256x3 array of colors to use for IR"""
    fn = "%s/gini_ir_ramp.txt" % (DATADIR,)
    data = np.zeros((256, 3), np.uint8)
    for i, line in enumerate(open(fn)):
        tokens = line.split()
        data[i, :] = [int(tokens[0]), int(tokens[1]), int(tokens[2])]
    return data


class GINIZFile:
    """
    Deal with compressed GINI files, which are the standard on NOAAPORT
    """

    def __init__(self, fobj):
        """Create a GNIFile instance with a compressed file object

        Args:
          fobj (file): A fileobject
        """
        fobj.seek(0)
        # WMO HEADER
        self.wmo = (fobj.read(21)).strip().decode("utf-8")
        d = zlib.decompressobj()
        hdata = d.decompress(fobj.read())
        self.metadata = self.read_header(hdata[21:])
        self.init_projection()
        totsz = len(d.unused_data)
        # 5120 value chunks, so we need to be careful!
        sdata = b""
        chunk = b"x\xda"
        i = 0
        for part in d.unused_data.split(b"x\xda"):
            if part == b"" and i == 0:
                continue
            chunk += part
            try:
                sdata += zlib.decompress(chunk)
                i += 1
                totsz -= len(chunk)
                chunk = b"x\xda"
            except Exception:
                chunk += b"x\xda"
        if totsz != 0:
            LOG.warning("Totalsize left: %s", totsz)

        self.data = np.reshape(
            np.fromstring(sdata, np.int8),
            (self.metadata["numlines"] + 1, self.metadata["linesize"]),
        )

    def __str__(self):
        """return a string representation"""
        text = "%s Line Size: %s Num Lines: %s" % (
            self.wmo,
            self.metadata["linesize"],
            self.metadata["numlines"],
        )
        return text

    def awips_grid(self):
        """
        Return the awips grid number based on the WMO header
        """
        try1 = AWIPS_GRID.get(self.wmo[:4], None)
        if try1:
            return try1
        return AWIPS_GRID_GUESS.get(self.wmo[3], None)

    def current_filename(self):
        """
        Return a filename for this product, we'll use the format
        {SOURCE}_{SECTOR}_{CHANNEL}_{VALID}.png
        """
        return "%s_%s_%s.png" % (
            LABELS[self.metadata["creating_entity"]],
            SECTORS[self.metadata["sector"]],
            CHANNELS[self.metadata["channel"]],
        )

    def get_bird(self):
        """
        Return a string label for this satellite
        """
        return ENTITIES[self.metadata["creating_entity"]]

    def get_sector(self):
        """Return the sector."""
        return SECTORS[self.metadata["sector"]]

    def get_channel(self):
        """Return the channel."""
        return CHANNELS[self.metadata["channel"]]

    def archive_filename(self):
        """
        Return a filename for this product, we'll use the format
        {SOURCE}_{SECTOR}_{CHANNEL}_{VALID}.png
        """
        return ("%s_%s_%s_%s.png") % (
            LABELS[self.metadata["creating_entity"]],
            SECTORS[self.metadata["sector"]],
            CHANNELS[self.metadata["channel"]],
            self.metadata["valid"].strftime("%Y%m%d%H%M"),
        )

    def init_llc(self):
        """
        Initialize Lambert Conic Comformal
        """
        self.metadata["proj"] = pyproj.Proj(
            proj="lcc",
            lat_0=self.metadata["latin"],
            lat_1=self.metadata["latin"],
            lat_2=self.metadata["latin"],
            lon_0=self.metadata["lov"],
            a=6371200.0,
            b=6371200.0,
        )

        # s = 1.0
        # if self.metadata['proj_center_flag'] != 0:
        #    s = -1.0
        psi = M_PI_2 - abs(math.radians(self.metadata["latin"]))
        cos_psi = math.cos(psi)
        # r_E = RE_METERS / cos_psi
        alpha = math.pow(math.tan(psi / 2.0), cos_psi) / math.sin(psi)

        x0, y0 = self.metadata["proj"](
            self.metadata["lon1"], self.metadata["lat1"]
        )
        self.metadata["x0"] = x0
        self.metadata["y0"] = y0
        # self.metadata['dx'] *= alpha
        # self.metadata['dy'] *= alpha
        self.metadata["y1"] = y0 + (self.metadata["dy"] * self.metadata["ny"])

        (self.metadata["lon_ul"], self.metadata["lat_ul"]) = self.metadata[
            "proj"
        ](self.metadata["x0"], self.metadata["y1"], inverse=True)
        LOG.warning(
            (
                "lat1: %.5f y0: %5.f y1: %.5f lat_ul: %.3f "
                "lat_ur: %.3f lon_ur: %.3f alpha: %.5f dy: %.3f"
            ),
            self.metadata["lat1"],
            y0,
            self.metadata["y1"],
            self.metadata["lat_ul"],
            self.metadata["lat_ur"],
            self.metadata["lon_ur"],
            alpha,
            self.metadata["dy"],
        )

    def init_mercator(self):
        """
        Compute mercator projection stuff
        """
        self.metadata["proj"] = pyproj.Proj(
            proj="merc",
            lat_ts=self.metadata["latin"],
            x_0=0,
            y_0=0,
            a=6371200.0,
            b=6371200.0,
        )
        x0, y0 = self.metadata["proj"](
            self.metadata["lon1"], self.metadata["lat1"]
        )
        self.metadata["x0"] = x0
        self.metadata["y0"] = y0

        x1, y1 = self.metadata["proj"](
            self.metadata["lon2"], self.metadata["lat2"]
        )
        self.metadata["x1"] = x1
        self.metadata["y1"] = y1

        self.metadata["dx"] = (x1 - x0) / self.metadata["nx"]
        self.metadata["dy"] = (y1 - y0) / self.metadata["ny"]

        (self.metadata["lon_ul"], self.metadata["lat_ul"]) = self.metadata[
            "proj"
        ](self.metadata["x0"], self.metadata["y1"], inverse=True)

        LOG.warning(
            (
                "latin: %.2f lat_ul: %.3f lon_ul: %.3f "
                "y0: %5.f y1: %.5f dx: %.3f dy: %.3f"
            ),
            self.metadata["latin"],
            self.metadata["lat_ul"],
            self.metadata["lon_ul"],
            y0,
            y1,
            self.metadata["dx"],
            self.metadata["dy"],
        )

    def init_stereo(self):
        """
        Compute Polar Stereographic
        """
        self.metadata["proj"] = pyproj.Proj(
            proj="stere",
            lat_ts=60,
            lat_0=90,
            lon_0=self.metadata["lov"],
            x_0=0,
            y_0=0,
            a=6371200.0,
            b=6371200.0,
        )
        # First point!
        x0, y0 = self.metadata["proj"](
            self.metadata["lon1"], self.metadata["lat1"]
        )
        self.metadata["x0"] = x0
        self.metadata["y0"] = y0

        self.metadata["y1"] = y0 + (self.metadata["dy"] * self.metadata["ny"])
        (self.metadata["lon_ul"], self.metadata["lat_ul"]) = self.metadata[
            "proj"
        ](x0, self.metadata["y1"], inverse=True)

        LOG.warning(
            (
                "lon_ul: %.2f lat_ul: %.2f "
                "lon_ll: %.2f lat_ll: %.2f "
                " lov: %.2f latin: %.2f lat1: %.2f lat2: %.2f "
                "y0: %5.f y1: %.5f dx: %.3f dy: %.3f"
            ),
            self.metadata["lon_ul"],
            self.metadata["lat_ul"],
            self.metadata["lon1"],
            self.metadata["lat1"],
            self.metadata["lov"],
            self.metadata["latin"],
            self.metadata["lat1"],
            self.metadata["lat2"],
            y0,
            self.metadata["y1"],
            self.metadata["dx"],
            self.metadata["dy"],
        )

    def init_projection(self):
        """
        Setup Grid and projection details
        """
        if self.metadata["map_projection"] == 3:
            self.init_llc()
        elif self.metadata["map_projection"] == 1:
            self.init_mercator()
        elif self.metadata["map_projection"] == 5:
            self.init_stereo()
        else:
            LOG.warning(
                "Unknown Projection: %s", self.metadata["map_projection"]
            )

    def read_header(self, hdata):
        """read the header!"""
        meta = {}
        meta["source"] = struct.unpack("> B", hdata[0:1])[0]
        meta["creating_entity"] = struct.unpack("> B", hdata[1:2])[0]
        meta["sector"] = struct.unpack("> B", hdata[2:3])[0]
        meta["channel"] = struct.unpack("> B", hdata[3:4])[0]

        meta["numlines"] = struct.unpack(">H", hdata[4:6])[0]
        meta["linesize"] = struct.unpack(">H", hdata[6:8])[0]

        yr = 1900 + struct.unpack("> B", hdata[8:9])[0]
        mo = struct.unpack("> B", hdata[9:10])[0]
        dy = struct.unpack("> B", hdata[10:11])[0]
        hh = struct.unpack("> B", hdata[11:12])[0]
        mi = struct.unpack("> B", hdata[12:13])[0]
        ss = struct.unpack("> B", hdata[13:14])[0]
        # hs = struct.unpack("> B", hdata[14:15] )[0]
        meta["valid"] = datetime(yr, mo, dy, hh, mi, ss).replace(
            tzinfo=timezone.utc
        )
        meta["map_projection"] = struct.unpack("> B", hdata[15:16])[0]
        meta["proj_center_flag"] = struct.unpack("> B", hdata[36:37])[0] >> 7
        meta["scan_mode"] = struct.unpack("> B", hdata[37:38])[0]

        meta["nx"] = struct.unpack(">H", hdata[16:18])[0]
        meta["ny"] = struct.unpack(">H", hdata[18:20])[0]
        meta["res"] = struct.unpack(">B", hdata[41:42])[0]
        # Is Calibration Info included?
        # http://www.nws.noaa.gov/noaaport/document/ICD%20CH5-2005-1.pdf
        # page24
        # Mercator
        if meta["map_projection"] == 1:
            meta["lat1"] = int24(hdata[20:23])
            meta["lon1"] = int24(hdata[23:26])
            meta["lov"] = 0
            meta["dx"] = struct.unpack(">H", hdata[33:35])[0]
            meta["dy"] = struct.unpack(">H", hdata[35:37])[0]
            meta["latin"] = int24(hdata[38:41])
            meta["lat2"] = int24(hdata[27:30])
            meta["lon2"] = int24(hdata[30:33])
            meta["lat_ur"] = int24(hdata[55:58])
            meta["lon_ur"] = int24(hdata[58:61])
        # lambert == 3, polar == 5
        else:
            meta["lat1"] = int24(hdata[20:23])
            meta["lon1"] = int24(hdata[23:26])
            meta["lov"] = int24(hdata[27:30])
            meta["dx"] = uint24(hdata[30:33])
            meta["dy"] = uint24(hdata[33:36])
            meta["latin"] = int24(hdata[38:41])
            meta["lat2"] = 0
            meta["lon2"] = 0
            meta["lat_ur"] = int24(hdata[55:58])
            meta["lon_ur"] = int24(hdata[58:61])

        meta["dx"] = meta["dx"] / 10.0
        meta["dy"] = meta["dy"] / 10.0
        meta["lat1"] = meta["lat1"] / 10000.0
        meta["lon1"] = meta["lon1"] / 10000.0
        meta["lov"] = meta["lov"] / 10000.0
        meta["latin"] = meta["latin"] / 10000.0
        meta["lat2"] = meta["lat2"] / 10000.0
        meta["lon2"] = meta["lon2"] / 10000.0
        meta["lat_ur"] = meta["lat_ur"] / 10000.0
        meta["lon_ur"] = meta["lon_ur"] / 10000.0

        return meta
