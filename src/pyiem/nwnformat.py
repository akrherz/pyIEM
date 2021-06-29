"""Supports parsing of the NWNFormat

Which is a format used by the Texas Weather Sensors KCCI-TV Operates
"""
from datetime import timezone, datetime
import re
import math

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

import pyiem.reference as reference
import pyiem.util as util


def uv(sped, drct2):
    """Convert to u,v components."""
    dirr = drct2 * math.pi / 180.00
    s = math.sin(dirr)
    c = math.cos(dirr)
    u = round(-sped * s, 2)
    v = round(-sped * c, 2)
    return u, v


def dwpf(tmpf, relh):
    """
    Compute the dewpoint in F given a temperature and relative humidity
    """
    if tmpf is None or relh is None:
        return None

    tmpk = 273.15 + (5.00 / 9.00 * (tmpf - 32.00))
    dwpk = tmpk / (1 + 0.000425 * tmpk * -(math.log10(relh / 100.0)))
    return int(float((dwpk - 273.15) * 9.00 / 5.00 + 32))


def mydir(u, v):
    """TBR."""
    if v == 0:
        v = 0.000000001
    dd = math.atan(u / v)
    ddir = (dd * 180.00) / math.pi

    if u > 0 and v > 0:
        ddir = 180 + ddir
    elif u > 0 and v < 0:
        ddir = 360 + ddir
    elif u < 0 and v > 0:
        ddir = 180 + ddir
    return int(round(math.fabs(ddir), 0))


def feelslike(tmpf, relh, sped):
    """TBR."""
    if tmpf > 50:
        return heatidx(tmpf, relh)
    return wchtidx(tmpf, sped)


def heatidx(tmpf, relh):
    """TBR."""
    if tmpf < 70:
        return tmpf
    if tmpf > 140:
        return -99
    if relh == 0:
        return -99

    PR_HEAT = 61 + (tmpf - 68) * 1.2 + relh * 0.094
    if PR_HEAT < 77:
        return PR_HEAT

    t2 = tmpf * tmpf
    t3 = tmpf * tmpf * tmpf
    r2 = relh * relh
    r3 = relh * relh * relh

    return (
        17.423
        + 0.185212 * tmpf
        + 5.37941 * relh
        - 0.100254 * tmpf * relh
        + 0.00941695 * t2
        + 0.00728898 * r2
        + 0.000345372 * t2 * relh
        - 0.000814971 * tmpf * r2
        + 0.0000102102 * t2 * r2
        - 0.000038646 * t3
        + 0.0000291583 * r3
        + 0.00000142721 * t3 * relh
        + 0.000000197483 * tmpf * r3
        - 0.0000000218429 * t3 * r2
        + 0.000000000843296 * t2 * r3
        - 0.0000000000481975 * t3 * r3
    )


def wchtidx(tmpf, sped):
    """TBR."""
    if sped < 3 or tmpf > 50:
        return tmpf
    wci = math.pow(sped, 0.16)

    return 35.74 + 0.6215 * tmpf - 35.75 * wci + 0.4275 * tmpf * wci


class nwnformat:
    """TBR."""

    def __init__(self, do_avg_winds=True):
        """TBR."""
        self.error = 0
        self.do_avg_winds = do_avg_winds

        self.sid = None
        self.ts = None
        self.avg_sknt = None
        self.avg_drct = None
        self.drct = None
        self.drctTxt = None
        self.avg_drctTxt = None
        self.sped = None
        self.sknt = None
        self.rad = 0
        self.insideTemp = 460
        self.tmpf = None
        self.humid = None
        self.pres = None
        self.presTend = None
        self.pDay = 0.00
        self.pMonth = 0.00
        self.pRate = 0.00
        self.dwpf = None
        self.feel = None

        self.nhumid = 0
        self.xhumid = 0

        self.npres = 0
        self.xpres = 0

        self.xtmpf = None
        self.ntmpf = None
        self.xsped = None
        self.xdrct = None
        self.xdrctTxt = None
        self.xsrad = None

        self.strMaxLine = None
        self.strMinLine = None

        self.aSknt = []
        self.aDrct = []

    def setTS(self, newval):
        """Force a timestamp."""
        self.ts = datetime.strptime(newval, "%m/%d/%y %H:%M:%S")
        now = datetime.now()
        if (now - self.ts).total_seconds() > 7200:
            self.error = 101

    def avgWinds(self):
        """Vector averaging."""
        self.avg_sknt = int(float(sum(self.aSknt)) / float(len(self.aSknt)))
        utot = 0
        vtot = 0
        for s, d in zip(self.aSknt, self.aDrct):
            u, v = uv(s, d)
            if s > self.xsped:
                self.xsped = s * 1.150
                self.xdrct = d
                self.xdrctTxt = util.drct2text(d)

            utot += u
            vtot += v
        uavg = utot / float(len(self.aSknt))
        vavg = vtot / float(len(self.aSknt))
        self.avg_drct = mydir(uavg, vavg)
        self.avg_drctTxt = util.drct2text(self.avg_drct)

        self.aSknt = []
        self.aDrct = []

    def parseLineRT(self, tokens):
        """TBR."""
        if self.ts is None:
            _t = datetime.utcnow()
            _t = _t.replace(second=0, microsecond=0, tzinfo=timezone.utc)
            self.ts = _t.astimezone(ZoneInfo("America/Chicago"))
        lineType = tokens[2]
        if lineType == "Max":
            self.parseMaxLineRT(tokens)
        elif lineType == "Min":
            self.parseMinLineRT(tokens)
        else:
            _t = datetime.utcnow()
            _t = _t.replace(second=0, microsecond=0, tzinfo=timezone.utc)
            self.ts = _t.astimezone(ZoneInfo("America/Chicago"))
            self.parseCurrentLineRT(tokens)

    def parseMaxLineRT(self, tokens):
        """TBR."""
        self.xdrct = reference.txt2drct[tokens[4]]
        self.xdrctTxt = tokens[4]
        if len(tokens[5]) >= 5:
            t = re.findall("([0-9]+)(MPH|KTS)", tokens[5])[0]
            if t[1] == "MPH":
                self.xsped = int(t[0])

        if len(tokens[6]) == 4:
            self.xsrad = (
                int(re.findall("([0-9][0-9][0-9])[F,K]", tokens[6])[0]) * 10
            )

        if len(tokens[8]) == 4 or len(tokens[8]) == 3:
            self.xtmpf = int(tokens[8][:-1])

    def parseMinLineRT(self, tokens):
        """TBR."""
        if len(tokens[8]) == 4 or len(tokens[8]) == 3:
            if tokens[8][0] == "0":
                tokens[8] = tokens[8][1:]
            self.ntmpf = int(tokens[8][:-1])

    def parseCurrentLineRT(self, tokens):
        """TBR."""
        # ['M', '057', '09:57', '09/04/03', 'ESE', '01MPH', '058K', '460F',
        #  '065F', '070%', '30.34R', '00.00"D', '00.00"M', '00.00"R']
        # Don't forget about this lovely one!
        # ['M', '057', '09:57', '09/04/03', 'ESE', '01MPH', '058K', '460F',
        #  '0-5F', '070%', '30.34R', '00.00"D', '00.00"M', '00.00"R']
        if len(tokens[8]) == 4 or len(tokens[8]) == 3:
            if tokens[8][0] == "0":
                tokens[8] = tokens[8][1:]
            self.tmpf = int(tokens[8][:-1])

        self.drct = reference.txt2drct[tokens[4]]
        self.drctTxt = tokens[4]
        if self.do_avg_winds:
            self.aDrct.append(int(self.drct))

        if len(tokens[5]) >= 5:
            t = re.findall("([0-9]+)(MPH|KTS)", tokens[5])[0]
            if t[1] == "MPH":
                self.sped = int(t[0])
                self.sknt = round(float(self.sped) * 0.868976, 0)
            else:
                self.sknt = int(t[0])
                self.sped = round(self.sknt / 0.868976, 0)
        if self.do_avg_winds:
            self.aSknt.append(self.sknt)

        if len(tokens[6]) == 4:
            self.rad = (
                int(re.findall("([0-9][0-9][0-9])[F,K]", tokens[6])[0]) * 10
            )

        if len(tokens[9]) == 4:
            self.humid = int(re.findall("([0-9][0-9][0-9])%", tokens[9])[0])

        if len(tokens[10]) == 6:
            self.pres = float(re.findall("(.*).", tokens[10])[0])

        if len(tokens[11]) == 7:
            self.pDay = float(re.findall('(.*)"D', tokens[11])[0])

        if len(tokens[12]) == 7:
            self.pMonth = float(re.findall('(.*)"M', tokens[12])[0])

        if (
            self.tmpf > -50
            and self.tmpf < 120
            and self.humid > 5
            and self.humid < 100.1
        ):
            self.dwpf = dwpf(self.tmpf, self.humid)
            self.feel = feelslike(self.tmpf, self.humid, self.sped)
        else:
            self.dwpf = None
            self.feel = None

    def currentLine(self):
        """Return NWN formatted string for current ob

        Returns:
          str: A NWN format string"""
        return (
            "%s %03.0f  %5s %8s %-3s %02.0fMPH %03.0fK %03.0fF %03.0fF "
            '%03.0f%s %05.2f%s %05.2f"D %05.2f"M %05.2f"R\015\012'
        ) % (
            "A",
            self.sid,
            self.ts.strftime("%H:%M"),
            self.ts.strftime("%m/%d/%y"),
            self.drctTxt,
            self.sped,
            self.rad,
            self.insideTemp,
            self.tmpf,
            self.humid,
            "%",
            self.pres,
            self.presTend,
            self.pDay,
            self.pMonth,
            self.pRate,
        )

    def maxLine(self):
        """Return NWN formatted string for max ob

        Returns:
          str: A NWN format string"""
        return (
            "%s %03i  %5s %8s %-3s %02iMPH %03iK %03iF %03iF "
            '%03i%s %05.2f%s %05.2f"D %05.2f"M %05.2f"R\015\012'
        ) % (
            "A",
            self.sid,
            "Max ",
            self.ts.strftime("%m/%d/%y"),
            "N",
            self.xsped,
            self.rad,
            self.insideTemp,
            self.xtmpf,
            self.xhumid,
            "%",
            self.xpres,
            self.presTend,
            0,
            0,
            0,
        )

    def minLine(self):
        """Return NWN formatted string for min ob

        Returns:
          str: A NWN format string"""
        return (
            "%s %03i  %5s %8s %-3s %02iMPH %03iK %03iF %03iF %03i%s "
            '%05.2f" %05.2f"D %05.2f"M %05.2f"R\015\012'
        ) % (
            "A",
            self.sid,
            "Min ",
            self.ts.strftime("%m/%d/%y"),
            self.drctTxt,
            0,
            0,
            self.insideTemp,
            self.ntmpf,
            self.nhumid,
            "%",
            self.npres,
            0,
            0,
            0,
        )

    def sanityCheck(self):
        """Bounds Check."""
        if self.tmpf is None or self.tmpf < -100 or self.tmpf > 150:
            self.tmpf = 460
        if self.ntmpf is None or self.ntmpf < -100 or self.ntmpf > 150:
            self.ntmpf = 460
        if self.xtmpf is None or self.xtmpf < -100 or self.xtmpf > 150:
            self.xtmpf = 460
        if self.avg_sknt is None or self.avg_sknt < 0 or self.avg_sknt > 300:
            self.avg_sknt = 0
        if self.avg_drct is None or self.avg_drct < 0 or self.avg_drct > 360:
            self.avg_drct = 0
