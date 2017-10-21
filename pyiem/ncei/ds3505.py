"""Implementation of the NCEI DS3505 format

    ftp://ftp.ncdc.noaa.gov/pub/data/noaa/ish-format-document.pdf

"""
from __future__ import print_function
import re

ADDITIONAL = {
# Hourly Precip
'AA1': [['hrs', 2], ['depth', 4], ['cond_code', 1], ['qc', 1]],
'AA2': [['hrs', 2], ['depth', 4], ['cond_code', 1], ['qc', 1]],
'AA3': [['hrs', 2], ['depth', 4], ['cond_code', 1], ['qc', 1]],
'AA4': [['hrs', 2], ['depth', 4], ['cond_code', 1], ['qc', 1]],
# Monthly Precip
'AB1': [['depth', 5], ['cond_code', 1], ['qc', 1]],
# Precip History
'AC1': [['duration', 1], ['char_code', 1], ['qc', 1]],
# Greatest amount in a month
'AD1': [['depth', 5], ['cond_code', 1], ['date1', 4], ['date2', 4],
        ['date3', 4], ['qc', 1]],
# Precip number of days
'AE1': [['q01_days', 2], ['q01_days_qc', 1],
        ['q10_days', 2], ['q10_days_qc', 1],
        ['q50_days', 2], ['q50_days_qc', 1],
        ['q100_days', 2], ['q100_days_qc', 1]],
# Precip estimated?
'AG1': [['code', 1], ['depth', 3]],
# Short duration precip
'AH1': [['period', 3], ['depth', 4], ['code', 1], ['enddate', 6], ['qc', 1]],
'AH2': [['period', 3], ['depth', 4], ['code', 1], ['enddate', 6], ['qc', 1]],
'AH3': [['period', 3], ['depth', 4], ['code', 1], ['enddate', 6], ['qc', 1]],
'AH4': [['period', 3], ['depth', 4], ['code', 1], ['enddate', 6], ['qc', 1]],
'AH5': [['period', 3], ['depth', 4], ['code', 1], ['enddate', 6], ['qc', 1]],
'AH6': [['period', 3], ['depth', 4], ['code', 1], ['enddate', 6], ['qc', 1]],
# Short duration precip for month
'AI1': [['period', 3], ['depth', 4], ['code', 1], ['enddate', 6], ['qc', 1]],
'AI2': [['period', 3], ['depth', 4], ['code', 1], ['enddate', 6], ['qc', 1]],
'AI3': [['period', 3], ['depth', 4], ['code', 1], ['enddate', 6], ['qc', 1]],
'AI4': [['period', 3], ['depth', 4], ['code', 1], ['enddate', 6], ['qc', 1]],
'AI5': [['period', 3], ['depth', 4], ['code', 1], ['enddate', 6], ['qc', 1]],
'AI6': [['period', 3], ['depth', 4], ['code', 1], ['enddate', 6], ['qc', 1]],
# Snow depth
'AJ1': [['depth', 4], ['cond_code', 1], ['qc', 1], ['swe', 6], ['swe_cond_code', 1],
        ['swe_qc', 1]],
# Snow depth month
'AK1': [['depth', 4], ['cond_code', 1], ['dates', 6], ['qc', 1]],
# Snow accumulation
'AL1': [['period', 2], ['depth', 3], ['cond_code', 1], ['qc', 1]],
'AL2': [['period', 2], ['depth', 3], ['cond_code', 1], ['qc', 1]],
'AL3': [['period', 2], ['depth', 3], ['cond_code', 1], ['qc', 1]],
'AL4': [['period', 2], ['depth', 3], ['cond_code', 1], ['qc', 1]],
# Snow greatest in month
'AM1': [['depth', 4], ['cond_code', 1], ['dates1', 4], ['dates2', 4],
        ['dates3', 4], ['qc', 1]],
# snow for day month?
'AN1': [['period', 3], ['depth', 4], ['cond_code', 1], ['qc', 1]],
# precip occurence
'AO1': [['minutes', 2], ['depth', 4], ['cond_code', 1], ['qc', 1]],
'AO2': [['minutes', 2], ['depth', 4], ['cond_code', 1], ['qc', 1]],
'AO3': [['minutes', 2], ['depth', 4], ['cond_code', 1], ['qc', 1]],
'AO4': [['minutes', 2], ['depth', 4], ['cond_code', 1], ['qc', 1]],
# 15 minute precip
'AP1': [['depth', 4], ['cond_code', 1], ['qc', 1]],
'AP2': [['depth', 4], ['cond_code', 1], ['qc', 1]],
'AP3': [['depth', 4], ['cond_code', 1], ['qc', 1]],
'AP4': [['depth', 4], ['cond_code', 1], ['qc', 1]],
# presentweather
'AT1': [['source', 2], ['type', 2], ['abbr', 4], ['qc', 1]],
'AT2': [['source', 2], ['type', 2], ['abbr', 4], ['qc', 1]],
'AT3': [['source', 2], ['type', 2], ['abbr', 4], ['qc', 1]],
'AT4': [['source', 2], ['type', 2], ['abbr', 4], ['qc', 1]],
'AT5': [['source', 2], ['type', 2], ['abbr', 4], ['qc', 1]],
'AT6': [['source', 2], ['type', 2], ['abbr', 4], ['qc', 1]],
'AT7': [['source', 2], ['type', 2], ['abbr', 4], ['qc', 1]],
'AT8': [['source', 2], ['type', 2], ['abbr', 4], ['qc', 1]],
# present weather intensity
'AU1': [['proximity', 1], ['descriptor', 1], ['precip', 2], ['obscure', 1],
        ['other', 1], ['combo', 1], ['qc', 1]],
'AU2': [['proximity', 1], ['descriptor', 1], ['precip', 2], ['obscure', 1],
        ['other', 1], ['combo', 1], ['qc', 1]],
'AU3': [['proximity', 1], ['descriptor', 1], ['precip', 2], ['obscure', 1],
        ['other', 1], ['combo', 1], ['qc', 1]],
'AU4': [['proximity', 1], ['descriptor', 1], ['precip', 2], ['obscure', 1],
        ['other', 1], ['combo', 1], ['qc', 1]],
'AU5': [['proximity', 1], ['descriptor', 1], ['precip', 2], ['obscure', 1],
        ['other', 1], ['combo', 1], ['qc', 1]],
'AU6': [['proximity', 1], ['descriptor', 1], ['precip', 2], ['obscure', 1],
        ['other', 1], ['combo', 1], ['qc', 1]],
'AU7': [['proximity', 1], ['descriptor', 1], ['precip', 2], ['obscure', 1],
        ['other', 1], ['combo', 1], ['qc', 1]],
'AU8': [['proximity', 1], ['descriptor', 1], ['precip', 2], ['obscure', 1],
        ['other', 1], ['combo', 1], ['qc', 1]],
'AU9': [['proximity', 1], ['descriptor', 1], ['precip', 2], ['obscure', 1],
        ['other', 1], ['combo', 1], ['qc', 1]],
# Automated weather
'AW1': [['cond_code', 2], ['qc', 1]],
'AW2': [['cond_code', 2], ['qc', 1]],
'AW3': [['cond_code', 2], ['qc', 1]],
'AW4': [['cond_code', 2], ['qc', 1]],
# Past Weather
'AX1': [['cond_code', 2], ['qc', 1], ['period', 2], ['period_qc', 1]],
'AX2': [['cond_code', 2], ['qc', 1], ['period', 2], ['period_qc', 1]],
'AX3': [['cond_code', 2], ['qc', 1], ['period', 2], ['period_qc', 1]],
'AX4': [['cond_code', 2], ['qc', 1], ['period', 2], ['period_qc', 1]],
'AX5': [['cond_code', 2], ['qc', 1], ['period', 2], ['period_qc', 1]],
'AX6': [['cond_code', 2], ['qc', 1], ['period', 2], ['period_qc', 1]],
# Past weather
'AY1': [['cond_code', 1], ['qc', 1], ['period', 2], ['period_qc', 1]],
'AY2': [['cond_code', 1], ['qc', 1], ['period', 2], ['period_qc', 1]],
# Past weather automated
'AZ1': [['cond_code', 1], ['qc', 1], ['period', 2], ['period_qc', 1]],
'AZ2': [['cond_code', 1], ['qc', 1], ['period', 2], ['period_qc', 1]],
# Sky coverage
'GA1': [['coverage', 2], ['coverage_qc', 1], ['height', 6], ['height_qc', 1],
        ['type', 2], ['type_qc', 1]],
'GA2': [['coverage', 2], ['coverage_qc', 1], ['height', 6], ['height_qc', 1],
        ['type', 2], ['type_qc', 1]],
'GA3': [['coverage', 2], ['coverage_qc', 1], ['height', 6], ['height_qc', 1],
        ['type', 2], ['type_qc', 1]],
'GA4': [['coverage', 2], ['coverage_qc', 1], ['height', 6], ['height_qc', 1],
        ['type', 2], ['type_qc', 1]],
'GA5': [['coverage', 2], ['coverage_qc', 1], ['height', 6], ['height_qc', 1],
        ['type', 2], ['type_qc', 1]],
'GA6': [['coverage', 2], ['coverage_qc', 1], ['height', 6], ['height_qc', 1],
        ['type', 2], ['type_qc', 1]],
# Sky coverage
'GF1': [['total', 2], ['opaque', 2], ['coverage_qc', 1],
        ['lowest_coverage', 2], ['lowest_coverage_qc', 1],
        ['lowest_genus', 2], ['lowest_genus_code', 1],
        ['lowest_height', 5], ['lowest_height_qc', 1],
        ['mid_genus', 2], ['mid_genus_qc', 1],
        ['high_genus', 2], ['high_genus_qc', 1]],
# Ground Surface
'IA1': [['code', 2], ['code_qc', 1]],
# Temperature extremes
'KA1': [['hours', 3], ['code', 1], ['tmpc', 5], ['qc', 1]],
'KA2': [['hours', 3], ['code', 1], ['tmpc', 5], ['qc', 1]],
'KA3': [['hours', 3], ['code', 1], ['tmpc', 5], ['qc', 1]],
'KA4': [['hours', 3], ['code', 1], ['tmpc', 5], ['qc', 1]],
# Pressure Tendency
'MD1': [['code', 1], ['code_qc', 1], ['threehour', 3], ['threehour_qc', 1],
        ['24hour', 4], ['24hour_qc', 1]],
# Present Weather Manual
'MW1': [['code', 2], ['qc', 1]],
'MW2': [['code', 2], ['qc', 1]],
'MW3': [['code', 2], ['qc', 1]],
'MW4': [['code', 2], ['qc', 1]],
'MW5': [['code', 2], ['qc', 1]],
'MW6': [['code', 2], ['qc', 1]],
'MW7': [['code', 2], ['qc', 1]],
# Supplemental Wind
'OA1': [['code', 1], ['period', 2], ['smps', 4], ['qc', 1]],
# Remarks
'REM': [['id', 3], ['length', 3]],
# Sea Surface temp
'SA1': [['tmpc', 4], ['qc', 1]],
# Wave
'UA1': [['method', 1], ['period', 2], ['height', 3], ['height_qc', 1],
        ['state', 2], ['state_qc', 1]],
}

DS3505_RE = re.compile(r"""
^(?P<chars>[0-9]{4})
(?P<stationid>......)
(?P<wban>.....)
(?P<yyyymmdd>[0-9]{8})
(?P<hhmi>[0-9]{4})
(?P<srcflag>.)
(?P<lat>[\+\-][0-9]{5})
(?P<lon>[\+\-][0-9]{6})
(?P<report_type>.....)
(?P<elevation>[\+\-][0-9]{4})
(?P<call_id>.....)
(?P<qc_process>....)
(?P<drct>[0-9]{3})
(?P<drct_qc>.)
(?P<wind_code>.)
(?P<wind_speed_mps>[0-9]{4})
(?P<wind_speed_mps_qc>.)
(?P<ceiling_m>[0-9]{5})
(?P<ceiling_m_qc>.)
(?P<ceiling_m_how>.)
(?P<ceiling_m_cavok>.)
(?P<vsby_m>[0-9]{6})
(?P<vsby_m_qc>.)
(?P<vsby_m_variable>.)
(?P<vsby_m_variable_qc>.)
(?P<airtemp_c>[\+\-][0-9]{4})
(?P<airtemp_c_qc>.)
(?P<dewpointtemp_c>[\+\-][0-9]{4})
(?P<dewpointtemp_c_qc>.)
(?P<pressure_hpa>[0-9]{5})
(?P<pressure_hpa_qc>.)
""", re.VERBOSE)


def parser(msg):
    """Parse the message into a dict"""
    match = DS3505_RE.match(msg)
    if not match:
        return None
    data = match.groupdict()
    data['lat'] = (float(data['lat']) / 1000.
                   if data['lat'] != '+99999'
                   else None)
    data['lon'] = (float(data['lon']) / 1000.
                   if data['lon'] != '+999999'
                   else None)
    data['elevation'] = (float(data['elevation'])
                   if data['elevation'] != '+9999'
                   else None)
    data['wind_speed_mps'] = (float(data['wind_speed_mps']) / 10.
                              if data['wind_speed_mps'] != '9999'
                              else None)
    data['airtemp_c'] = (float(data['airtemp_c']) / 10.
                              if data['airtemp_c'] != '+9999'
                              else None)
    data['dewpointtemp_c'] = (float(data['dewpointtemp_c']) / 10.
                              if data['dewpointtemp_c'] != '+9999'
                              else None)
    data['pressure_hpa'] = (float(data['pressure_hpa']) / 10.
                              if data['pressure_hpa'] != '99999'
                              else None)
    for elem in ['drct', 'ceiling_m', 'vsby_m']:
        if data[elem][0] == 9 and len(data[elem]) * "9":
            data[elem] = None
        else:
            data[elem] = float(data[elem])

    parse_extra(data, msg[105:])

    return data


def parse_extra(data, extra):
    """Parse the additional data fields"""
    # ADD can be ignored
    extra = extra[3:]
    pos = 0
    data['extra'] = {}
    while pos < len(extra):
        code = extra[pos:pos+3]
        pos += 3
        if code == 'EQD':
            # TODO: unsure how we will handle this one
            break
        if code not in ADDITIONAL:
            raise Exception("Unaccounted for %s, remaining %s" % (code,
                                                                  extra[pos:]))
        data['extra'][code] = dict()
        for token in ADDITIONAL[code]:
            data['extra'][code][token[0]] = extra[pos:pos+token[1]]
            pos += token[1]
        if code == 'REM':
            sz = int(data['extra'][code]['length'])
            data['extra'][code]['remark'] = extra[pos:pos+int(sz)]
            pos += sz
