"""Utilities for the Daily Erosion Project"""
from __future__ import print_function
import datetime
import re

import pandas as pd
import numpy as np

# The bounds of the climate files we store on disk and processing
SOUTH = 36.0
WEST = -104.0
NORTH = 49.0
EAST = -80.5

YLD_CROPTYPE = re.compile(r"Crop Type #\s+(?P<num>\d+)\s+is (?P<name>[^\s]+)")
YLD_DATA = re.compile((r"Crop Type #\s+(?P<num>\d+)\s+Date = (?P<doy>\d+)"
                       r" OFE #\s+(?P<ofe>\d+)\s+yield=\s+(?P<yield>[0-9\.]+)"
                       r" \(kg/m\*\*2\) year= (?P<year>\d+)"))

def read_yld(filename):
    """read WEPP yld file with some local mods to include a year

    Args:
      filename (str): Filename to read

    Returns:
      pandas.DataFrame
    """
    data = open(filename).read()
    xref = {}
    for (cropcode, label) in YLD_CROPTYPE.findall(data):
        xref[cropcode] = label
    rows = []
    for (cropcode, doy, ofe, yld, year) in YLD_DATA.findall(data):
        date = datetime.date(int(year), 1, 1) + datetime.timedelta(
            days=(int(doy) - 1))
        rows.append(dict(
            valid=date,
            year=int(year),
            yield_kgm2=float(yld),
            crop=xref[cropcode],
            ofe=int(ofe)
            ))
    return pd.DataFrame(rows)


def read_slp(filename):
    """read WEPP slp file

    Args:
      filename (str): Filename to read

    Returns:
      list of slope profiles
    """
    lines = [a[:a.find("#")].strip() for a in open(filename)]
    segments = int(lines[5])
    res = [None]*segments
    xpos = 0
    elev = 0
    for seg in range(segments):
        line1 = lines[7 + seg * 2]
        (_pts, length) = [float(x) for x in line1.split()]
        line2 = lines[8 + seg * 2].replace(",", "")
        tokens = np.array([float(x) for x in line2.split()])
        xs = xpos + tokens[::2] * length
        slopes = tokens[1::2]
        ys = [elev]
        for i in range(1, len(slopes)):
            elev -= (xs[i] - xs[0]) * slopes[i-1]
            ys.append(elev)
        res[seg] = {'x': xs, 'slopes': slopes, 'y': ys}
        xpos += length
    return res


def read_man(filename):
    """Implements WEPP's INFILE.for for reading management file

    Args:
      filename (str): Filename to read

    Returns:
      dict of management info
    """
    res = {}
    # Step one make a array of any data
    lines = [a[:a.find("#")].strip() for a in open(filename)]
    res['manver'] = lines[0]
    res['iofe'] = int(lines[6])
    res['inyr'] = int(lines[7])
    res['ncrop'] = int(lines[13])
    res['crops'] = [None]*res['ncrop']
    linenum = 16
    for ncrop in range(res['ncrop']):
        res['crops'][ncrop] = {
            'crpnam': lines[linenum],
            'crpcomment': "\n".join(lines[linenum+1:linenum+4]),
            'iplant': int(lines[linenum+4])
            }
        linenum += 5
        if res['crops'][ncrop]['iplant'] == 1:
            # TODO
            linenum += 7
    linenum += 4
    res['nop'] = int(lines[linenum])
    linenum += 3
    res['operations'] = [None]*res['nop']
    for nop in range(res['nop']):
        res['operations'][nop] = {
            'scenam': lines[linenum],
            'scecomment': "\n".join(lines[linenum+1:linenum+4]),
            'iplant': int(lines[linenum+4])
            }
        linenum += 9
    linenum += 6
    res['nini'] = int(lines[linenum])
    res['ini'] = [None]*res['nini']
    linenum += 3
    for ini in range(res['nini']):
        res['ini'][ini] = {
            'scenam': lines[linenum],
            'scecomment': "\n".join(lines[linenum+1:linenum+4]),
            'iplant': int(lines[linenum+4])
            }
        linenum += 14
    linenum += 6

    res['nsurf'] = int(lines[linenum])
    res['surfeffects'] = [None]*res['nsurf']
    linenum += 6
    for surf in range(res['nsurf']):
        res['surfeffects'][surf] = {
            'scenam': lines[linenum],
            'scecomment': "\n".join(lines[linenum+1:linenum+4]),
            'iplant': int(lines[linenum+4]),
            'ntill': int(lines[linenum+5])
            }
        res['surfeffects'][surf]['tills'] = (
            [None]*res['surfeffects'][surf]['ntill'])
        linenum += 6
        for till in range(res['surfeffects'][surf]['ntill']):
            res['surfeffects'][surf]['tills'][till] = {
                'mdate': int(lines[linenum]),
                'op': int(lines[linenum+1]),
                'depth': float(lines[linenum+2]),
                'type': int(lines[linenum+3])
                }
            linenum += 4
        linenum += 4
    linenum += 2
    res['ncnt'] = int(lines[linenum])
    linenum += 7
    res['ndrain'] = int(lines[linenum])
    linenum += 7
    res['nmscen'] = int(lines[linenum])
    linenum += 4
    res['scens'] = [None]*res['nmscen']
    for scen in range(res['nmscen']):
        res['scens'][scen] = {
            'scenam': lines[linenum],
            'scecomment': "\n".join(lines[linenum+1:linenum+4]),
            'iplant': int(lines[linenum+4]),
            'ntype': int(lines[linenum+5]),
            'tilseq': int(lines[linenum+6]),
            'conseq': int(lines[linenum+7]),
            'drseq': int(lines[linenum+8]),
            'imngmt': int(lines[linenum+9]),
            }
        # print(("linenum: %s scen: %s iplant: %s imngmt: %s"
        #       ) % (linenum, scen, res['scens'][scen]['iplant'],
        #            res['scens'][scen]['imngmt']))
        if res['scens'][scen]['iplant'] == 1:
            if res['scens'][scen]['imngmt'] in [1, 3]:
                # Annual/Fallow Cropping system
                res['scens'][scen]['jdharv'] = int(lines[linenum+10])
                res['scens'][scen]['jdplt'] = int(lines[linenum+11])
                res['scens'][scen]['r1'] = float(lines[linenum+12])
                res['scens'][scen]['resmgt'] = int(lines[linenum+13])
                # print("resmgt is %s" % (res['scens'][scen]['resmgt'], ))
                if res['scens'][scen]['resmgt'] == 1:
                    res['scens'][scen]['jdherb'] = int(lines[linenum+14])
                    linenum += 15
                elif res['scens'][scen]['resmgt'] == 2:
                    res['scens'][scen]['jdburn'] = int(lines[linenum+14])
                    res['scens'][scen]['fbrna1'] = float(
                        lines[linenum+15].split()[0])
                    res['scens'][scen]['fbrno1'] = float(
                        lines[linenum+15].split()[1])
                    linenum += 16
                elif res['scens'][scen]['resmgt'] == 3:
                    res['scens'][scen]['jdslge'] = int(lines[linenum+14])
                    linenum += 15
                elif res['scens'][scen]['resmgt'] == 4:
                    res['scens'][scen]['jdcut'] = int(lines[linenum+14])
                    res['scens'][scen]['frcu1'] = int(lines[linenum+15])
                    linenum += 16
                elif res['scens'][scen]['resmgt'] == 5:
                    res['scens'][scen]['jdmove'] = int(lines[linenum+14])
                    res['scens'][scen]['frmov1'] = float(lines[linenum+14])
                    linenum += 16
                elif res['scens'][scen]['resmgt'] == 6:
                    linenum += 14
            else:
                # Perrenial Cropland
                res['scens'][scen]['jdharv'] = int(lines[linenum+10])
                res['scens'][scen]['jdplt'] = int(lines[linenum+11])
                res['scens'][scen]['jdstop'] = int(lines[linenum+12])
                res['scens'][scen]['r1'] = float(lines[linenum+13])
                res['scens'][scen]['mgtopt'] = int(lines[linenum+14])
                # print("mgtopt is %s" % (res['scens'][scen]['mgtopt'], ))
                if res['scens'][scen]['mgtopt'] == 1:
                    # Cutting
                    res['scens'][scen]['ncut'] = int(lines[linenum+15])
                    res['scens'][scen]['cuts'] = (
                        [None]*res['scens'][scen]['ncut'])
                    linenum += 16
                    for cut in range(res['scens'][scen]['ncut']):
                        res['scens'][scen]['cuts'][cut] = int(lines[linenum])
                        linenum += 1
                elif res['scens'][scen]['mgtopt'] == 2:
                    # Grazing
                    res['scens'][scen]['ncycle'] = int(lines[linenum+15])
                    res['scens'][scen]['cycles'] = (
                        [None]*res['scens'][scen]['ncycle'])
                    linenum += 16
                    for cycle in range(res['scens'][scen]['ncycle']):
                        res['scens'][scen]['cycles'][cycle] = {
                            'arr': lines[linenum],
                            'gday': int(lines[linenum+1]),
                            'gend': int(lines[linenum+2])
                        }
                        linenum += 1
                elif res['scens'][scen]['mgtopt'] == 3:
                    linenum += 15
        elif res['scens'][scen]['iplant'] == 2:
            pass
        linenum += 3
    linenum += 3
    res['mantitle'] = lines[linenum]
    res['mandesc'] = "\n".join(lines[linenum+1:linenum+4])
    linenum += 4
    res['nwsofe'] = int(lines[linenum])
    res['inindx'] = [None]*res['nwsofe']
    linenum += 1
    for idx in range(res['nwsofe']):
        res['inindx'][idx] = int(lines[linenum])
        linenum += 1
    res['nrots'] = int(lines[linenum])
    linenum += 1
    res['nyears'] = int(lines[linenum])
    res['rotations'] = [None]*res['nyears']
    linenum += 6
    for year in range(res['nyears']):
        res['rotations'][year] = [None]*res['nwsofe']
        for ofe in range(res['nwsofe']):
            res['rotations'][year][ofe] = {
                'plant': int(lines[linenum]),
                'yearindex': int(lines[linenum+1]),
                }
            linenum += 3

    return res


def read_cli(filename):
    """Read WEPP CLI File, Return DataFrame

    Args:
      filename (str): Filename to read

    Returns:
      pandas.DataFrame
    """
    rows = []
    dates = []
    lines = open(filename).readlines()
    linenum = 15
    while linenum < len(lines):
        (da, mo, year, breakpoints, tmax, tmin, rad, wvl, wdir,
         tdew) = lines[linenum].split()
        breakpoints = int(breakpoints)
        accum = 0
        times = []
        points = []
        for i in range(1, breakpoints + 1):
            (ts, accum) = lines[linenum + i].split()
            times.append(float(ts))
            points.append(float(accum))
        maxr = 0
        for i in range(1, len(times)):
            dt = times[i] - times[i-1]
            dr = points[i] - points[i-1]
            rate = (dr / dt)
            if rate > maxr:
                maxr = rate
        linenum += (breakpoints + 1)
        dates.append(datetime.date(int(year), int(mo), int(da)))
        rows.append({'tmax': float(tmax), 'tmin': float(tmin),
                     'rad': float(rad), 'wvl': float(wvl),
                     'wdir': float(wdir), 'tdew': float(tdew),
                     'maxr': maxr, 'bpcount': breakpoints,
                     'pcpn': float(accum)})

    return pd.DataFrame(rows, index=pd.DatetimeIndex(dates))


def read_env(filename, year0=2006):
    """Read WEPP .env file, return a dataframe

    Args:
      filename (str): Filename to read
      year0 (int,optional): The simulation start year minus 1

    Returns:
      pd.DataFrame
    """
    df = pd.read_table(filename,
                       skiprows=3, index_col=False, delim_whitespace=True,
                       header=None, na_values=['*******', '******'],
                       names=['day', 'month', 'year', 'precip', 'runoff',
                              'ir_det', 'av_det', 'mx_det', 'point',
                              'av_dep', 'max_dep', 'point2', 'sed_del',
                              'er'])
    if len(df.index) == 0:
        df['date'] = None
    else:
        # Faster than +=
        df['year'] = df['year'] + year0
        # Considerably faster than df.apply
        df['date'] = pd.to_datetime(dict(year=df['year'], month=df['month'],
                                         day=df['day']))
    return df


def read_ofe(filename, year0=2006):
    """Read OFE .ofe file, return a dataframe

    Args:
      filename (str): Filename to read
      year0 (int,optional): The simulation start year minus 1

    Returns:
      pd.DataFrame
    """
    df = pd.read_table(filename,
                       skiprows=2, index_col=False, delim_whitespace=True,
                       header=None, na_values=['*******', '******',
                                               '********'],
                       names=['ofe', 'day', 'month', 'year', 'precip',
                              'runoff', 'effint', 'peakro', 'effdur',
                              'enrich_ratio', 'keff', 'sm', 'leafarea',
                              'canhght', 'cancov', 'intcov', 'rilcov',
                              'livbio', 'deadbio', 'ki', 'kr', 'tcrit',
                              'rilwid', 'sedleave'])
    if len(df.index) == 0:
        df['date'] = None
    else:
        # Faster than +=
        df['year'] = df['year'] + year0
        # Considerably faster than df.apply
        df['date'] = pd.to_datetime(dict(year=df['year'], month=df['month'],
                                         day=df['day']))
    return df


def read_wb(filename):
    """Read a *custom* WEPP .wb file into Pandas Data Table"""
    df = pd.read_table(filename, delim_whitespace=True,
                       na_values=['*******', '******'])
    if len(df.index) == 0:
        df['date'] = None
    else:
        # Considerably faster than df.apply
        df['date'] = pd.to_datetime(df['year'].astype(str) + ' ' +
                                    df['jday'].astype(str), format='%Y %j')
    return df
