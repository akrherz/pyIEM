"""Implementation of the NCEI DS3505 format

    https://www1.ncdc.noaa.gov/pub/data/ish/ish-format-document.pdf
"""
# pylint: disable=too-many-lines
import re
import warnings
from datetime import timezone, datetime
import json

from metar.Metar import Metar
from metar.Metar import ParserError as MetarParserError
from metpy.units import units
from metpy.calc import relative_humidity_from_dewpoint
from pyiem.datatypes import speed, pressure
from pyiem.meteorology import mcalc_feelslike
from pyiem.util import LOG


MISSING_RE = re.compile(r"^\+?\-?9+$")
EQD_RE = re.compile(r"^[QPRCDN][0-9][0-9]$")
QNN_RE = re.compile(r"^[A-Z][0-9][0-9][A-Z ][0-9]$")
DS3505_RE = re.compile(
    r"""
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
(?P<mslp_hpa>[0-9]{5})
(?P<mslp_hpa_qc>.)
""",
    re.VERBOSE,
)


def _tonumeric(val, scale_factor=1.0):
    """Convert to what we want"""
    if MISSING_RE.match(val) or val == "D0":
        return None
    try:
        return float(val) / scale_factor
    except ValueError:
        return None


def _d1000(val):
    """Divide the value by 1000"""
    return _tonumeric(val, 1000.0)


def _d10(val):
    """Divide the value by 10"""
    return _tonumeric(val, 10.0)


def _i10(val):
    """Divide the value by 10"""
    val = _tonumeric(val, 10.0)
    return None if val is None else int(val)


def _i(val):
    """int"""
    val = _tonumeric(val, 1.0)
    if val is None:
        return val
    return int(val)


SKY_STATE_CODES = {
    "0": "CLR",
    "1": "FEW",
    "2": "SCT",
    "3": "BKN",
    "4": "OVC",
    "5": "OBS",
    "6": "POB",
    "9": "///",
}

ADDITIONAL = {
    # Hourly Precip
    "AA1": [["hours", 2, _i], ["depth", 4, _d10], ["cond_code", 1], ["qc", 1]],
    "AA2": [["hours", 2, _i], ["depth", 4, _d10], ["cond_code", 1], ["qc", 1]],
    "AA3": [["hours", 2, _i], ["depth", 4, _d10], ["cond_code", 1], ["qc", 1]],
    "AA4": [["hours", 2, _i], ["depth", 4, _d10], ["cond_code", 1], ["qc", 1]],
    # Monthly Precip
    "AB1": [["depth", 5], ["cond_code", 1], ["qc", 1]],
    # Precip History
    "AC1": [["duration", 1], ["char_code", 1], ["qc", 1]],
    # Greatest amount in a month
    "AD1": [
        ["depth", 5],
        ["cond_code", 1],
        ["date1", 4],
        ["date2", 4],
        ["date3", 4],
        ["qc", 1],
    ],
    # Precip number of days
    "AE1": [
        ["q01_days", 2],
        ["q01_days_qc", 1],
        ["q10_days", 2],
        ["q10_days_qc", 1],
        ["q50_days", 2],
        ["q50_days_qc", 1],
        ["q100_days", 2],
        ["q100_days_qc", 1],
    ],
    # Precip estimated?
    "AG1": [["code", 1], ["depth", 3]],
    # Short duration precip
    "AH1": [
        ["period", 3],
        ["depth", 4],
        ["code", 1],
        ["enddate", 6],
        ["qc", 1],
    ],
    "AH2": [
        ["period", 3],
        ["depth", 4],
        ["code", 1],
        ["enddate", 6],
        ["qc", 1],
    ],
    "AH3": [
        ["period", 3],
        ["depth", 4],
        ["code", 1],
        ["enddate", 6],
        ["qc", 1],
    ],
    "AH4": [
        ["period", 3],
        ["depth", 4],
        ["code", 1],
        ["enddate", 6],
        ["qc", 1],
    ],
    "AH5": [
        ["period", 3],
        ["depth", 4],
        ["code", 1],
        ["enddate", 6],
        ["qc", 1],
    ],
    "AH6": [
        ["period", 3],
        ["depth", 4],
        ["code", 1],
        ["enddate", 6],
        ["qc", 1],
    ],
    # Short duration precip for month
    "AI1": [
        ["period", 3],
        ["depth", 4],
        ["code", 1],
        ["enddate", 6],
        ["qc", 1],
    ],
    "AI2": [
        ["period", 3],
        ["depth", 4],
        ["code", 1],
        ["enddate", 6],
        ["qc", 1],
    ],
    "AI3": [
        ["period", 3],
        ["depth", 4],
        ["code", 1],
        ["enddate", 6],
        ["qc", 1],
    ],
    "AI4": [
        ["period", 3],
        ["depth", 4],
        ["code", 1],
        ["enddate", 6],
        ["qc", 1],
    ],
    "AI5": [
        ["period", 3],
        ["depth", 4],
        ["code", 1],
        ["enddate", 6],
        ["qc", 1],
    ],
    "AI6": [
        ["period", 3],
        ["depth", 4],
        ["code", 1],
        ["enddate", 6],
        ["qc", 1],
    ],
    # Snow depth
    "AJ1": [
        ["depth", 4],
        ["cond_code", 1],
        ["qc", 1],
        ["swe", 6],
        ["swe_cond_code", 1],
        ["swe_qc", 1],
    ],
    # Snow depth month
    "AK1": [["depth", 4], ["cond_code", 1], ["dates", 6], ["qc", 1]],
    # Snow accumulation
    "AL1": [["period", 2], ["depth", 3], ["cond_code", 1], ["qc", 1]],
    "AL2": [["period", 2], ["depth", 3], ["cond_code", 1], ["qc", 1]],
    "AL3": [["period", 2], ["depth", 3], ["cond_code", 1], ["qc", 1]],
    "AL4": [["period", 2], ["depth", 3], ["cond_code", 1], ["qc", 1]],
    # Snow greatest in month
    "AM1": [
        ["depth", 4],
        ["cond_code", 1],
        ["dates1", 4],
        ["dates2", 4],
        ["dates3", 4],
        ["qc", 1],
    ],
    # snow for day month?
    "AN1": [["period", 3], ["depth", 4], ["cond_code", 1], ["qc", 1]],
    # precip occurence
    "AO1": [["minutes", 2], ["depth", 4], ["cond_code", 1], ["qc", 1]],
    "AO2": [["minutes", 2], ["depth", 4], ["cond_code", 1], ["qc", 1]],
    "AO3": [["minutes", 2], ["depth", 4], ["cond_code", 1], ["qc", 1]],
    "AO4": [["minutes", 2], ["depth", 4], ["cond_code", 1], ["qc", 1]],
    # 15 minute precip
    "AP1": [["depth", 4], ["cond_code", 1], ["qc", 1]],
    "AP2": [["depth", 4], ["cond_code", 1], ["qc", 1]],
    "AP3": [["depth", 4], ["cond_code", 1], ["qc", 1]],
    "AP4": [["depth", 4], ["cond_code", 1], ["qc", 1]],
    # presentweather
    "AT1": [["source", 2], ["type", 2], ["abbr", 4], ["qc", 1]],
    "AT2": [["source", 2], ["type", 2], ["abbr", 4], ["qc", 1]],
    "AT3": [["source", 2], ["type", 2], ["abbr", 4], ["qc", 1]],
    "AT4": [["source", 2], ["type", 2], ["abbr", 4], ["qc", 1]],
    "AT5": [["source", 2], ["type", 2], ["abbr", 4], ["qc", 1]],
    "AT6": [["source", 2], ["type", 2], ["abbr", 4], ["qc", 1]],
    "AT7": [["source", 2], ["type", 2], ["abbr", 4], ["qc", 1]],
    "AT8": [["source", 2], ["type", 2], ["abbr", 4], ["qc", 1]],
    # present weather intensity
    "AU1": [
        ["proximity", 1],
        ["descriptor", 1],
        ["precip", 2],
        ["obscure", 1],
        ["other", 1],
        ["combo", 1],
        ["qc", 1],
    ],
    "AU2": [
        ["proximity", 1],
        ["descriptor", 1],
        ["precip", 2],
        ["obscure", 1],
        ["other", 1],
        ["combo", 1],
        ["qc", 1],
    ],
    "AU3": [
        ["proximity", 1],
        ["descriptor", 1],
        ["precip", 2],
        ["obscure", 1],
        ["other", 1],
        ["combo", 1],
        ["qc", 1],
    ],
    "AU4": [
        ["proximity", 1],
        ["descriptor", 1],
        ["precip", 2],
        ["obscure", 1],
        ["other", 1],
        ["combo", 1],
        ["qc", 1],
    ],
    "AU5": [
        ["proximity", 1],
        ["descriptor", 1],
        ["precip", 2],
        ["obscure", 1],
        ["other", 1],
        ["combo", 1],
        ["qc", 1],
    ],
    "AU6": [
        ["proximity", 1],
        ["descriptor", 1],
        ["precip", 2],
        ["obscure", 1],
        ["other", 1],
        ["combo", 1],
        ["qc", 1],
    ],
    "AU7": [
        ["proximity", 1],
        ["descriptor", 1],
        ["precip", 2],
        ["obscure", 1],
        ["other", 1],
        ["combo", 1],
        ["qc", 1],
    ],
    "AU8": [
        ["proximity", 1],
        ["descriptor", 1],
        ["precip", 2],
        ["obscure", 1],
        ["other", 1],
        ["combo", 1],
        ["qc", 1],
    ],
    "AU9": [
        ["proximity", 1],
        ["descriptor", 1],
        ["precip", 2],
        ["obscure", 1],
        ["other", 1],
        ["combo", 1],
        ["qc", 1],
    ],
    # Automated weather
    "AW1": [["cond_code", 2], ["qc", 1]],
    "AW2": [["cond_code", 2], ["qc", 1]],
    "AW3": [["cond_code", 2], ["qc", 1]],
    "AW4": [["cond_code", 2], ["qc", 1]],
    # Past Weather
    "AX1": [["cond_code", 2], ["qc", 1], ["period", 2], ["period_qc", 1]],
    "AX2": [["cond_code", 2], ["qc", 1], ["period", 2], ["period_qc", 1]],
    "AX3": [["cond_code", 2], ["qc", 1], ["period", 2], ["period_qc", 1]],
    "AX4": [["cond_code", 2], ["qc", 1], ["period", 2], ["period_qc", 1]],
    "AX5": [["cond_code", 2], ["qc", 1], ["period", 2], ["period_qc", 1]],
    "AX6": [["cond_code", 2], ["qc", 1], ["period", 2], ["period_qc", 1]],
    # Past weather
    "AY1": [["cond_code", 1], ["qc", 1], ["period", 2], ["period_qc", 1]],
    "AY2": [["cond_code", 1], ["qc", 1], ["period", 2], ["period_qc", 1]],
    # Past weather automated
    "AZ1": [["cond_code", 1], ["qc", 1], ["period", 2], ["period_qc", 1]],
    "AZ2": [["cond_code", 1], ["qc", 1], ["period", 2], ["period_qc", 1]],
    # unsure
    "BA1": [["hours", 2, _i], ["depth", 4, _d10], ["cond_code", 1], ["qc", 1]],
    # CRN Secondary Precip
    "CB1": [["minutes", 2], ["depth", 6], ["qc", 1], ["precip_flag", 1]],
    "CB2": [["minutes", 2], ["depth", 6], ["qc", 1], ["precip_flag", 1]],
    # CRN, Fan Speed
    "CF1": [["speed", 4], ["qc", 1], ["speed_flag", 1]],
    "CF2": [["speed", 4], ["qc", 1], ["speed_flag", 1]],
    "CF3": [["speed", 4], ["qc", 1], ["speed_flag", 1]],
    # CRN, subhour precip
    "CG1": [["depth", 6], ["qc", 1], ["depth_flag", 1]],
    "CG2": [["depth", 6], ["qc", 1], ["depth_flag", 1]],
    "CG3": [["depth", 6], ["qc", 1], ["depth_flag", 1]],
    # CRN, rh
    "CH1": [
        ["minutes", 2],
        ["tmpc", 5],
        ["tmpc_qc", 1],
        ["tmpc_flag", 1],
        ["avg_rh", 4],
        ["qc", 1],
        ["avg_rh_flag", 1],
    ],
    "CH2": [
        ["minutes", 2],
        ["tmpc", 5],
        ["tmpc_qc", 1],
        ["tmpc_flag", 1],
        ["avg_rh", 4],
        ["qc", 1],
        ["avg_rh_flag", 1],
    ],
    # CRN, rh
    "CI1": [
        ["min_rh_temp", 5],
        ["min_rh_temp_qc", 1],
        ["min_rh_temp_flag", 1],
        ["max_rh_temp", 5],
        ["max_rh_temp_qc", 1],
        ["max_rh_temp_flag", 1],
        ["std_rh_temp", 5],
        ["std_rh_temp_qc", 1],
        ["std_rh_temp_flag", 1],
        ["std_rh", 5],
        ["std_rh_qc", 1],
        ["std_rh_flag", 1],
    ],
    # CRN, battery voltage
    "CN1": [
        ["batvol", 4],
        ["batvol_qc", 1],
        ["batvol_flag", 1],
        ["batvol_fl", 4],
        ["batvol_fl_qc", 1],
        ["batvol_fl_flag", 1],
        ["batvol_dl", 4],
        ["batvol_dl_qc", 1],
        ["batvol_dl_flag", 1],
    ],
    # CRN, misc diagnostics
    "CN2": [
        ["tranel", 5],
        ["tranel_qc", 1],
        ["tranel_flag", 1],
        ["tinlet_max", 5],
        ["tinlet_max_qc", 1],
        ["trinlet_max_flag", 1],
        ["opendoor_tm", 2],
        ["opendoor_tm_qc", 1],
        ["opendoor_tm_flag", 1],
    ],
    # CRN, secondary diagnostic
    "CN3": [
        ["refresavg", 6],
        ["refresavg_qc", 1],
        ["refresavg_flag", 1],
        ["dsignature", 6],
        ["dsignature__qc", 1],
        ["dsignature_flag", 1],
    ],
    # CRN, secondary hourly diagnostic
    "CN4": [
        ["heater_flag", 1],
        ["heater_flag_code", 1],
        ["heater_flag_code2", 1],
        ["doorflag", 1],
        ["doorflag_code", 1],
        ["doorflag_code2", 1],
        ["fortrans", 1],
        ["fortrans_code", 1],
        ["fortrans_code2", 1],
        ["refltrans", 3],
        ["refltrans_code", 1],
        ["refltrans_code2", 1],
    ],
    # CRN, metadata
    "CO1": [["climat_division", 2], ["lst_conversion", 3]],
    "CO2": [["elementid", 3], ["time_offset", 5]],
    "CO3": [["elementid", 3], ["time_offset", 5]],
    "CO4": [["elementid", 3], ["time_offset", 5]],
    "CO5": [["elementid", 3], ["time_offset", 5]],
    "CO6": [["elementid", 3], ["time_offset", 5]],
    "CO7": [["elementid", 3], ["time_offset", 5]],
    "CO8": [["elementid", 3], ["time_offset", 5]],
    "CO9": [["elementid", 3], ["time_offset", 5]],
    # CRN, control section
    "CR1": [["dl_vn", 5], ["dl_vn_qc", 1], ["dl_vn_flag", 1]],
    # CRN, sub-hourly temperature
    "CT1": [["avg_temp", 5], ["avg_temp_qc", 1], ["avg_temp_flag", 1]],
    "CT2": [["avg_temp", 5], ["avg_temp_qc", 1], ["avg_temp_flag", 1]],
    "CT3": [["avg_temp", 5], ["avg_temp_qc", 1], ["avg_temp_flag", 1]],
    # CRN, colocated temp sensors
    "CU1": [
        ["avg_temp", 5],
        ["avg_temp_qc", 1],
        ["avg_temp_flag", 1],
        ["temp_std", 4],
        ["temp_std_qc", 1],
        ["temp_std_flag", 1],
    ],
    "CU2": [
        ["avg_temp", 5],
        ["avg_temp_qc", 1],
        ["avg_temp_flag", 1],
        ["temp_std", 4],
        ["temp_std_qc", 1],
        ["temp_std_flag", 1],
    ],
    "CU3": [
        ["avg_temp", 5],
        ["avg_temp_qc", 1],
        ["avg_temp_flag", 1],
        ["temp_std", 4],
        ["temp_std_qc", 1],
        ["temp_std_flag", 1],
    ],
    # CRN, hourly temp extreme
    "CV1": [
        ["temp_min", 5],
        ["temp_min_qc", 1],
        ["temp_min_flag", 1],
        ["temp_min_time", 4],
        ["temp_min_time_qc", 1],
        ["temp_min_time_flag", 1],
        ["temp_max", 5],
        ["temp_max_qc", 1],
        ["temp_max_flag", 1],
        ["temp_max_time", 4],
        ["temp_max_time_qc", 1],
        ["temp_max_time_flag", 1],
    ],
    "CV2": [
        ["temp_min", 5],
        ["temp_min_qc", 1],
        ["temp_min_flag", 1],
        ["temp_min_time", 4],
        ["temp_min_time_qc", 1],
        ["temp_min_time_flag", 1],
        ["temp_max", 5],
        ["temp_max_qc", 1],
        ["temp_max_flag", 1],
        ["temp_max_time", 4],
        ["temp_max_time_qc", 1],
        ["temp_max_time_flag", 1],
    ],
    "CV3": [
        ["temp_min", 5],
        ["temp_min_qc", 1],
        ["temp_min_flag", 1],
        ["temp_min_time", 4],
        ["temp_min_time_qc", 1],
        ["temp_min_time_flag", 1],
        ["temp_max", 5],
        ["temp_max_qc", 1],
        ["temp_max_flag", 1],
        ["temp_max_time", 4],
        ["temp_max_time_qc", 1],
        ["temp_max_time_flag", 1],
    ],
    # CRN, subhourly wetness
    "CW1": [
        ["wet1", 5],
        ["wet1_qc", 1],
        ["wet1_flag", 1],
        ["wet2", 5],
        ["wet2_qc", 1],
        ["wet2_flag", 1],
    ],
    # CRN, vibrating wire summary
    "CX1": [
        ["precipitation", 6],
        ["precip_qc", 1],
        ["precip_flag", 1],
        ["freq_avg", 4],
        ["freq_avg_qc", 1],
        ["freq_avg_flag", 1],
        ["freq_min", 4],
        ["freq_min_qc", 1],
        ["freq_min_flag", 1],
        ["freq_max", 4],
        ["freq_max_qc", 1],
        ["freq_max_flag", 1],
    ],
    "CX2": [
        ["precipitation", 6],
        ["precip_qc", 1],
        ["precip_flag", 1],
        ["freq_avg", 4],
        ["freq_avg_qc", 1],
        ["freq_avg_flag", 1],
        ["freq_min", 4],
        ["freq_min_qc", 1],
        ["freq_min_flag", 1],
        ["freq_max", 4],
        ["freq_max_qc", 1],
        ["freq_max_flag", 1],
    ],
    "CX3": [
        ["precipitation", 6],
        ["precip_qc", 1],
        ["precip_flag", 1],
        ["freq_avg", 4],
        ["freq_avg_qc", 1],
        ["freq_avg_flag", 1],
        ["freq_min", 4],
        ["freq_min_qc", 1],
        ["freq_min_flag", 1],
        ["freq_max", 4],
        ["freq_max_qc", 1],
        ["freq_max_flag", 1],
    ],
    # Visual Runway
    "ED1": [
        ["angle", 2],
        ["runway", 1],
        ["visibility", 4],
        ["visibility_qc", 1],
    ],
    # Sky coverage
    "GA1": [
        ["coverage", 2],
        ["coverage_qc", 1],
        ["height", 6, _tonumeric],
        ["height_qc", 1],
        ["type", 2],
        ["type_qc", 1],
    ],
    "GA2": [
        ["coverage", 2],
        ["coverage_qc", 1],
        ["height", 6, _tonumeric],
        ["height_qc", 1],
        ["type", 2],
        ["type_qc", 1],
    ],
    "GA3": [
        ["coverage", 2],
        ["coverage_qc", 1],
        ["height", 6, _tonumeric],
        ["height_qc", 1],
        ["type", 2],
        ["type_qc", 1],
    ],
    "GA4": [
        ["coverage", 2],
        ["coverage_qc", 1],
        ["height", 6, _tonumeric],
        ["height_qc", 1],
        ["type", 2],
        ["type_qc", 1],
    ],
    "GA5": [
        ["coverage", 2],
        ["coverage_qc", 1],
        ["height", 6, _tonumeric],
        ["height_qc", 1],
        ["type", 2],
        ["type_qc", 1],
    ],
    "GA6": [
        ["coverage", 2],
        ["coverage_qc", 1],
        ["height", 6, _tonumeric],
        ["height_qc", 1],
        ["type", 2],
        ["type_qc", 1],
    ],
    # sky cover summation
    "GD1": [
        ["state_code", 1],
        ["state_code2", 2],
        ["state_qc", 1],
        ["height", 6, _tonumeric],
        ["height_qc", 1],
        ["height_char", 1],
    ],
    "GD2": [
        ["state_code", 1],
        ["state_code2", 2],
        ["state_qc", 1],
        ["height", 6, _tonumeric],
        ["height_qc", 1],
        ["height_char", 1],
    ],
    "GD3": [
        ["state_code", 1],
        ["state_code2", 2],
        ["state_qc", 1],
        ["height", 6, _tonumeric],
        ["height_qc", 1],
        ["height_char", 1],
    ],
    "GD4": [
        ["state_code", 1],
        ["state_code2", 2],
        ["state_qc", 1],
        ["height", 6, _tonumeric],
        ["height_qc", 1],
        ["height_char", 1],
    ],
    "GD5": [
        ["state_code", 1],
        ["state_code2", 2],
        ["state_qc", 1],
        ["height", 6, _tonumeric],
        ["height_qc", 1],
        ["height_char", 1],
    ],
    "GD6": [
        ["state_code", 1],
        ["state_code2", 2],
        ["state_qc", 1],
        ["height", 6, _tonumeric],
        ["height_qc", 1],
        ["height_char", 1],
    ],
    # sky coverage identifier
    "GE1": [
        ["convective", 1],
        ["vertical_datum", 6],
        ["height", 6],
        ["lower_range", 6],
    ],
    # Sky coverage
    "GF1": [
        ["total", 2],
        ["opaque", 2],
        ["coverage_qc", 1],
        ["lowest_coverage", 2],
        ["lowest_coverage_qc", 1],
        ["lowest_genus", 2],
        ["lowest_genus_code", 1],
        ["lowest_height", 5],
        ["lowest_height_qc", 1],
        ["mid_genus", 2],
        ["mid_genus_qc", 1],
        ["high_genus", 2],
        ["high_genus_qc", 1],
    ],
    # below station cloud ID
    "GG1": [
        ["coverage_code", 2],
        ["coverage_qc", 1],
        ["height", 5],
        ["height_qc", 1],
        ["type_code", 2],
        ["type_code_qc", 1],
        ["top_code", 2],
        ["top_code_qc", 1],
    ],
    "GG2": [
        ["coverage_code", 2],
        ["coverage_qc", 1],
        ["height", 5],
        ["height_qc", 1],
        ["type_code", 2],
        ["type_code_qc", 1],
        ["top_code", 2],
        ["top_code_qc", 1],
    ],
    "GG3": [
        ["coverage_code", 2],
        ["coverage_qc", 1],
        ["height", 5],
        ["height_qc", 1],
        ["type_code", 2],
        ["type_code_qc", 1],
        ["top_code", 2],
        ["top_code_qc", 1],
    ],
    "GG4": [
        ["coverage_code", 2],
        ["coverage_qc", 1],
        ["height", 5],
        ["height_qc", 1],
        ["type_code", 2],
        ["type_code_qc", 1],
        ["top_code", 2],
        ["top_code_qc", 1],
    ],
    "GG5": [
        ["coverage_code", 2],
        ["coverage_qc", 1],
        ["height", 5],
        ["height_qc", 1],
        ["type_code", 2],
        ["type_code_qc", 1],
        ["top_code", 2],
        ["top_code_qc", 1],
    ],
    "GG6": [
        ["coverage_code", 2],
        ["coverage_qc", 1],
        ["height", 5],
        ["height_qc", 1],
        ["type_code", 2],
        ["type_code_qc", 1],
        ["top_code", 2],
        ["top_code_qc", 1],
    ],
    # Solar Radiation
    "GH1": [
        ["solarrad", 5],
        ["solarrad_qc", 1],
        ["solarrad_flag", 1],
        ["solarrad_min", 5],
        ["solarrad_min_qc", 1],
        ["solarrad_min_flag", 1],
        ["solarrad_max", 5],
        ["solarrad_max_qc", 1],
        ["solarrad_max_flag", 1],
        ["solarrad_std", 5],
        ["solarrad_std_qc", 1],
        ["solarrad_std_flag", 1],
    ],
    # Sunshine
    "GJ1": [["duration", 4], ["duration_qc", 1]],
    # sunhine
    "GK1": [["percent", 3], ["percent_qc", 1]],
    # sunshine for month
    "GL1": [["duration", 5], ["duration_qc", 1]],
    # solar irradiance
    "GM1": [
        ["time", 4],
        ["global_irradiance", 4],
        ["global_irradiance_flag", 2],
        ["global_irradiance_qc", 1],
        ["direct_irradiance", 4],
        ["direct_irradiance_flag", 2],
        ["direct_irradiance_qc", 1],
        ["diffuse_irradiance", 4],
        ["diffuse_irradiance_flag", 2],
        ["diffuse_irradiance_qc", 1],
        ["uvb_irradiance", 4],
        ["uvb_irradiance_qc", 1],
    ],
    # solar radiation
    "GN1": [
        ["period", 4],
        ["upwelling_global", 4],
        ["upwelling_global_qc", 1],
        ["downwelling_thermal", 4],
        ["downwelling_thermal_qc", 1],
        ["upwelling_thermal", 4],
        ["upwelling_thermal_qc", 1],
        ["par", 4],
        ["par_qc", 4],
        ["solar_zenith", 3],
        ["solar_zenith_qc", 1],
    ],
    # Net Solar
    "GO1": [
        ["time", 4],
        ["net_solar", 4],
        ["net_solar_qc", 1],
        ["net_infrared", 4],
        ["net_infrared_qc", 1],
        ["net_radiation", 4],
        ["net_radiation_qc", 1],
    ],
    # Modelled irradiance
    "GP1": [
        ["time", 4],
        ["global_horizontal", 4],
        ["global_horizontal_flag", 2],
        ["global_horizontal_uncertainty", 3],
        ["direct_normal", 4],
        ["direct_normal_flag", 2],
        ["direct_normal_uncertainty", 3],
        ["diffuse_horizontal", 4],
        ["diffuse_horizontal_flag", 2],
        ["diffuse_horizontal_uncertainty", 3],
    ],
    # hourly solar angle
    "GQ1": [
        ["time", 4],
        ["zenith_angle", 4],
        ["zenith_angle_qc", 1],
        ["azimuth_angle", 4],
        ["azimuth_angle_qc", 1],
    ],
    # hourly extraterrestrial rad
    "GR1": [
        ["time", 4],
        ["horizontal", 4],
        ["horizontal_qc", 1],
        ["normal", 4],
        ["normal_qc", 1],
    ],
    # Hail data
    "HL1": [["size", 3], ["size_qc", 1]],
    # Ground Surface
    "IA1": [["code", 2], ["code_qc", 1]],
    # Ground Surface Min temp
    "IA2": [["period", 3], ["min_tmpc", 5], ["min_tempc_qc", 1]],
    # Hourly surface temperature
    "IB1": [
        ["surftemp", 5],
        ["surftemp_qc", 1],
        ["surftemp_flag", 1],
        ["surftemp_min", 5],
        ["surftemp_min_qc", 1],
        ["surftemp_min_flag", 1],
        ["surftemp_max", 5],
        ["surftemp_max_qc", 1],
        ["surftemp_max_flag", 1],
        ["surftemp_std", 4],
        ["surftemp_std_qc", 1],
        ["surftemp_std_flag", 1],
    ],
    # Hourly Surface
    "IB2": [
        ["surftemp_sb", 5],
        ["surftemp_sb_qc", 1],
        ["surftemp_sb_flag", 1],
        ["surftemp_sb_std", 4],
        ["surftemp_sb_std_qc", 1],
        ["surftemp_sb_std_flag", 1],
    ],
    # Ground surface obs
    "IC1": [
        ["hours", 2],
        ["wind_movement", 4],
        ["wind_movement_code", 1],
        ["wind_movement_flag", 1],
        ["evaporation", 3],
        ["evaporation_code", 1],
        ["evaporation_qc", 1],
        ["max_pan_tmpc", 4],
        ["max_pan_tmpc_code", 1],
        ["max_pan_tmpc_qc", 1],
        ["min_pan_tmpc", 4],
        ["min_pan_tmpc_code", 1],
        ["min_pan_tmpc_qc", 1],
    ],
    # Temperature extremes
    "KA1": [["hours", 3, _i10], ["code", 1], ["tmpc", 5, _d10], ["qc", 1]],
    "KA2": [["hours", 3, _i10], ["code", 1], ["tmpc", 5, _d10], ["qc", 1]],
    "KA3": [["hours", 3, _i10], ["code", 1], ["tmpc", 5, _d10], ["qc", 1]],
    "KA4": [["hours", 3, _i10], ["code", 1], ["tmpc", 5, _d10], ["qc", 1]],
    # average air temp
    "KB1": [["hours", 3, _i10], ["code", 1], ["tmpc", 5, _d10], ["qc", 1]],
    "KB2": [["hours", 3, _i10], ["code", 1], ["tmpc", 5, _d10], ["qc", 1]],
    "KB3": [["hours", 3, _i10], ["code", 1], ["tmpc", 5, _d10], ["qc", 1]],
    "KB4": [["hours", 3, _i10], ["code", 1], ["tmpc", 5, _d10], ["qc", 1]],
    # extreme air temp
    "KC1": [
        ["month_code", 1],
        ["cond_code", 1],
        ["tmpc", 5],
        ["dates", 6],
        ["tmpc_qc", 1],
    ],
    "KC2": [
        ["month_code", 1],
        ["cond_code", 1],
        ["tmpc", 5],
        ["dates", 6],
        ["tmpc_qc", 1],
    ],
    # heating/cooling degree days
    "KD1": [["period", 3], ["code", 1], ["value", 4], ["qc", 1]],
    "KD2": [["period", 3], ["code", 1], ["value", 4], ["qc", 1]],
    # extreme temperatures, number of days
    "KE1": [
        ["days32", 2],
        ["days32_code", 1],
        ["days90", 2],
        ["days90_code", 1],
        ["daysmin32", 2],
        ["daysmin32_code", 1],
        ["daysmin0", 2],
        ["daysmin0_code", 1],
    ],
    # Hourly calc temp
    "KF1": [["temp", 5], ["temp_qc", 1]],
    # average dewpoint
    "KG1": [
        ["period", 3],
        ["code", 1],
        ["dewpoint", 5],
        ["dewpoint_code", 1],
        ["dewpoint_qc", 1],
    ],
    "KG2": [
        ["period", 3],
        ["code", 1],
        ["dewpoint", 5],
        ["dewpoint_code", 1],
        ["dewpoint_qc", 1],
    ],
    # pressure
    "MA1": [
        ["altimeter", 5, _d10],
        ["altimeter_code", 1],
        ["station_pressure", 5, _d10],
        ["station_pressure_code", 1],
    ],
    # Pressure Tendency
    "MD1": [
        ["code", 1],
        ["code_qc", 1],
        ["threehour", 3, _d10],
        ["threehour_qc", 1],
        ["24hour", 4, _d10],
        ["24hour_qc", 1],
    ],
    # geopotential
    "ME1": [["level_code", 1], ["height", 4], ["height_qc", 1]],
    # SLP
    "MF1": [
        ["pressure", 5],
        ["pressure_qc", 1],
        ["pressure_day", 5],
        ["pressure_day_qc", 1],
    ],
    # Pressure
    "MG1": [
        ["avg_pressure", 5],
        ["avg_pressure_qc", 1],
        ["min_pressure", 5],
        ["min_pressure_qc", 1],
    ],
    # Pressure for the month
    "MH1": [
        ["avg_pressure", 5],
        ["avg_pressure_qc", 1],
        ["avg_slp", 5],
        ["avg_slp_qc", 1],
    ],
    # Pressure for the month
    "MK1": [
        ["max_pressure", 5],
        ["max_pressure_datetime", 6],
        ["max_pressure_qc", 1],
        ["min_pressure", 5],
        ["min_pressure_datetime", 6],
        ["min_pressure_qc", 1],
    ],
    # Present Weather
    "MV1": [["code", 2], ["code_qc", 1]],
    "MV2": [["code", 2], ["code_qc", 1]],
    "MV3": [["code", 2], ["code_qc", 1]],
    "MV4": [["code", 2], ["code_qc", 1]],
    "MV5": [["code", 2], ["code_qc", 1]],
    "MV6": [["code", 2], ["code_qc", 1]],
    "MV7": [["code", 2], ["code_qc", 1]],
    # Present Weather Manual
    "MW1": [["code", 2], ["qc", 1]],
    "MW2": [["code", 2], ["qc", 1]],
    "MW3": [["code", 2], ["qc", 1]],
    "MW4": [["code", 2], ["qc", 1]],
    "MW5": [["code", 2], ["qc", 1]],
    "MW6": [["code", 2], ["qc", 1]],
    "MW7": [["code", 2], ["qc", 1]],
    # Supplemental Wind
    "OA1": [["code", 1], ["period", 2], ["smps", 4], ["qc", 1]],
    "OA2": [["code", 1], ["period", 2], ["smps", 4], ["qc", 1]],
    "OA3": [["code", 1], ["period", 2], ["smps", 4], ["qc", 1]],
    # hourly subhourly wind
    "OB1": [
        ["period", 4],
        ["wind_max", 4],
        ["wind_max_qc", 1],
        ["wind_max_flag", 1],
        ["wind_max_drct", 3],
        ["wind_max_drct_qc", 1],
        ["wind_max_drct_flag", 1],
        ["wind_std", 5],
        ["wind_std_qc", 1],
        ["wind_std_flag", 1],
        ["wind_dir_std", 5],
        ["wind_dir_std_qc", 1],
        ["wind_dir_std_flag", 1],
    ],
    "OB2": [
        ["period", 4],
        ["wind_max", 4],
        ["wind_max_qc", 1],
        ["wind_max_flag", 1],
        ["wind_max_drct", 3],
        ["wind_max_drct_qc", 1],
        ["wind_max_drct_flag", 1],
        ["wind_std", 5],
        ["wind_std_qc", 1],
        ["wind_std_flag", 1],
        ["wind_dir_std", 5],
        ["wind_dir_std_qc", 1],
        ["wind_dir_std_flag", 1],
    ],
    # Wind gust
    "OC1": [["speed", 4, _d10], ["speed_qc", 1]],
    # Supplementary Wind
    "OD1": [
        ["code", 1],
        ["hours", 2],
        ["speed", 4],
        ["speed_qc", 1],
        ["direction", 3],
    ],
    "OD2": [
        ["code", 1],
        ["hours", 2],
        ["speed", 4],
        ["speed_qc", 1],
        ["direction", 3],
    ],
    "OD3": [
        ["code", 1],
        ["hours", 2],
        ["speed", 4],
        ["speed_qc", 1],
        ["direction", 3],
    ],
    # Wind summary
    "OE1": [
        ["code", 1],
        ["period", 2],
        ["speed", 5],
        ["direction", 3],
        ["time", 4],
        ["qc", 1],
    ],
    "OE2": [
        ["code", 1],
        ["period", 2],
        ["speed", 5],
        ["direction", 3],
        ["time", 4],
        ["qc", 1],
    ],
    "OE3": [
        ["code", 1],
        ["period", 2],
        ["speed", 5],
        ["direction", 3],
        ["time", 4],
        ["qc", 1],
    ],
    # relative humidity
    "RH1": [
        ["hours", 3],
        ["code", 1],
        ["percentage", 3],
        ["derived", 1],
        ["qc", 1],
    ],
    "RH2": [
        ["hours", 3],
        ["code", 1],
        ["percentage", 3],
        ["derived", 1],
        ["qc", 1],
    ],
    "RH3": [
        ["hours", 3],
        ["code", 1],
        ["percentage", 3],
        ["derived", 1],
        ["qc", 1],
    ],
    # Sea Surface temp
    "SA1": [["tmpc", 4], ["qc", 1]],
    # Soil temperature
    "ST1": [
        ["type", 1],
        ["tmpc", 5],
        ["qc", 1],
        ["depth", 4],
        ["depth_qc", 1],
        ["cover", 2],
        ["cover_qc", 1],
        ["subplot", 1],
        ["subplot_qc", 1],
    ],
    # Wave
    "UA1": [
        ["method", 1],
        ["period", 2],
        ["height", 3],
        ["height_qc", 1],
        ["state", 2],
        ["state_qc", 1],
    ],
    # Wave swell
    "UG1": [["seconds", 2], ["height", 3], ["direction", 3], ["swell_qc", 1]],
    "UG2": [["seconds", 2], ["height", 3], ["direction", 3], ["swell_qc", 1]],
    # Ice Accretion
    "WA1": [
        ["source_code", 1],
        ["thickness", 3],
        ["tendency_code", 1],
        ["qc", 1],
    ],
    # Surface Ice
    "WD1": [
        ["bearing_code", 2],
        ["concentration_rate", 3],
        ["non_uniform", 2],
        ["position_code", 2],
        ["ship_relative", 1],
        ["penetration_code", 1],
        ["ice_trend", 1],
        ["development_code", 2],
        ["growler", 1],
        ["gbb", 3],
        ["iceberg", 3],
        ["qc", 1],
    ],
    # Water Ice
    "WG1": [
        ["bearing", 2],
        ["edge_distance", 2],
        ["orientation", 2],
        ["formation_type", 2],
        ["navigation_effect", 2],
        ["qc", 1],
    ],
    # water level
    "WJ1": [
        ["thickness", 3],
        ["discharge", 5],
        ["ice", 2],
        ["ice2", 2],
        ["stage", 5],
        ["slush", 1],
        ["water_level_code", 1],
    ],
}
SLP = "Sea Level PressureIn"
ERROR_RE = re.compile("Unparsed groups in body '(?P<msg>.*)' while processing")


def vsbyfmt(val):
    """Tricky formatting of vis"""
    val = round(val, 3)
    if val == 0:
        return 0
    if val <= 0.125:
        return "1/8"
    if val <= 0.25:
        return "1/4"
    if val <= 0.375:
        return "3/8"
    if val <= 0.5:
        return "1/2"
    if val <= 1.1:
        return "1"
    if val <= 1.25:
        return "1 1/4"
    if val <= 1.6:
        return "1 1/2"
    if val <= 2.1:
        return "2"
    if val <= 2.6:
        return "2 1/2"
    return "%.0f" % (val,)


class OB:
    """hacky representation of the database schema"""

    station = None
    valid = None
    tmpf = None
    dwpf = None
    drct = None
    sknt = None
    alti = None
    gust = None
    vsby = None
    skyc1 = None
    skyc2 = None
    skyc3 = None
    skyc4 = None
    skyl1 = None
    skyl2 = None
    skyl3 = None
    metar = None
    skyl4 = None
    p03i = None
    p06i = None
    p24i = None
    max_tmpf_6hr = None
    min_tmpf_6hr = None
    max_tmpf_24hr = None
    min_tmpf_24hr = None
    mslp = None
    p01i = None
    wxcodes = None
    relh = None
    feel = None


def process_metar(mstr, now):
    """Do the METAR Processing"""
    mtr = None
    while mtr is None:
        try:
            mtr = Metar(mstr, now.month, now.year)
        except MetarParserError as exp:
            msg = str(exp)
            tokens = ERROR_RE.findall(str(exp))
            orig_mstr = mstr
            if tokens:
                for token in tokens[0].split():
                    mstr = mstr.replace(" %s" % (token,), "")
                if orig_mstr == mstr:
                    LOG.warning("Can't fix badly formatted metar: %s", mstr)
                    return None
            else:
                LOG.warning("MetarParserError: %s", msg)
                return None
        except Exception as exp:
            LOG.warning("Double Fail: %s %s", mstr, exp)
            return None
    if mtr is None or mtr.time is None:
        return None

    ob = OB()
    ob.metar = mstr[:254]
    ob.valid = now

    if mtr.temp:
        ob.tmpf = mtr.temp.value("F")
    if mtr.dewpt:
        ob.dwpf = mtr.dewpt.value("F")

    if mtr.wind_speed:
        ob.sknt = mtr.wind_speed.value("KT")
    if mtr.wind_gust:
        ob.gust = mtr.wind_gust.value("KT")

    # Calc some stuff
    if ob.tmpf is not None and ob.dwpf is not None:
        ob.relh = (
            relative_humidity_from_dewpoint(
                ob.tmpf * units("degF"), ob.dwpf * units("degF")
            )
            .to(units("percent"))
            .magnitude
        )
        if ob.sknt is not None:
            ob.feel = (
                mcalc_feelslike(
                    ob.tmpf * units.degF,
                    ob.dwpf * units.degF,
                    ob.sknt * units("knots"),
                )
                .to(units("degF"))
                .magnitude
            )

    if mtr.wind_dir and mtr.wind_dir.value() != "VRB":
        ob.drct = mtr.wind_dir.value()

    if mtr.vis:
        ob.vsby = mtr.vis.value("SM")

    # see pull request #38
    if mtr.press and mtr.press != mtr.press_sea_level:
        ob.alti = mtr.press.value("IN")

    if mtr.press_sea_level:
        ob.mslp = mtr.press_sea_level.value("MB")

    if mtr.precip_1hr:
        ob.p01i = mtr.precip_1hr.value("IN")

    # Do something with sky coverage
    for i in range(len(mtr.sky)):
        (c, h, _) = mtr.sky[i]
        setattr(ob, "skyc%s" % (i + 1), c)
        if h is not None:
            setattr(ob, "skyl%s" % (i + 1), h.value("FT"))

    if mtr.max_temp_6hr:
        ob.max_tmpf_6hr = mtr.max_temp_6hr.value("F")
    if mtr.min_temp_6hr:
        ob.min_tmpf_6hr = mtr.min_temp_6hr.value("F")
    if mtr.max_temp_24hr:
        ob.max_tmpf_24hr = mtr.max_temp_24hr.value("F")
    if mtr.min_temp_24hr:
        ob.min_tmpf_6hr = mtr.min_temp_24hr.value("F")
    if mtr.precip_3hr:
        ob.p03i = mtr.precip_3hr.value("IN")
    if mtr.precip_6hr:
        ob.p06i = mtr.precip_6hr.value("IN")
    if mtr.precip_24hr:
        ob.p24i = mtr.precip_24hr.value("IN")

    # Presentwx
    if mtr.weather:
        pwx = []
        for wx in mtr.weather:
            val = "".join([a for a in wx if a is not None])
            if val == "" or val == len(val) * "/":
                continue
            pwx.append(val)
        ob.wxcodes = pwx

    return ob


def sql(txn, stid, data):
    """Persist what data we have to the IEM schema database

    In general, the IEM database's atomic data is based on the parsing of the
    METAR product.  So we wouldn't want the two to conflict, so the METAR
    format is again used to drive the data used for the database insert.

    Args:
      txn (cursor): database transaction
      stid (str): station identifier to use with the database
      data (dict): what we got from previous parsing

    Returns:
      int or None: number of rows inserted
    """
    # First problem, which metar source to use?
    # If this is a US site, likely best to always use it
    metar = data.get("metar")
    if metar is None:
        metar = data["extra"].get("REM", {}).get("MET", "")
        if len(metar) > 20 and (len(stid) == 3 or stid[0] == "P"):
            # Split off the cruft
            metar = metar.strip().replace(";", " ").replace("METAR ", "")
            metar = metar.replace("COR ", "").rstrip("=")

    table = "t%s" % (data["valid"].year,)
    ob = process_metar(metar, data["valid"])
    if ob is None:
        return
    stid = stid if len(stid) == 4 and stid[0] != "K" else stid[-3:]
    _sql = f"""
        INSERT into {table} (station, valid,
        tmpf, dwpf, vsby, drct, sknt, gust, p01i, alti, skyc1, skyc2,
        skyc3, skyc4, skyl1, skyl2, skyl3, skyl4, metar, mslp,
        wxcodes, p03i, p06i, p24i, max_tmpf_6hr, max_tmpf_24hr,
        min_tmpf_6hr, min_tmpf_24hr, report_type, relh, feel)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s,%s,%s, %s, %s, %s, %s, %s, %s, %s, %s, 2, %s, %s)
        RETURNING valid
            """
    args = (
        stid,
        ob.valid,
        ob.tmpf,
        ob.dwpf,
        ob.vsby,
        ob.drct,
        ob.sknt,
        ob.gust,
        ob.p01i,
        ob.alti,
        ob.skyc1,
        ob.skyc2,
        ob.skyc3,
        ob.skyc4,
        ob.skyl1,
        ob.skyl2,
        ob.skyl3,
        ob.skyl4,
        metar,
        ob.mslp,
        ob.wxcodes,
        ob.p03i,
        ob.p06i,
        ob.p24i,
        ob.max_tmpf_6hr,
        ob.max_tmpf_24hr,
        ob.min_tmpf_6hr,
        ob.min_tmpf_24hr,
        ob.relh,
        ob.feel,
    )

    try:
        txn.execute(_sql, args)
    except Exception:
        LOG.warning(metar)
        LOG.warning(args)
        raise
    return txn.rowcount


def gen_metar(data):
    """Convert our parsed dictionary into a METAR"""
    mtr = "%s %sZ AUTO " % (data["call_id"], data["valid"].strftime("%d%H%M"))
    # wind direction
    if data.get("wind_code") == "C":
        mtr += "00000KT "
    elif (
        data.get("drct_qc") in ["1", "5"]
        and data["wind_speed_mps"] is not None
    ):
        if data["drct"] is None:
            mtr += "////"
        else:
            mtr += "%03.0f" % (data["drct"],)
        kts = speed(data["wind_speed_mps"], "MPS").value("KT")
        mtr += "%02.0f" % (kts,)
        if "OC1" in data["extra"]:
            val = data["extra"]["OC1"].get("speed", 0)
            if val is not None and val > 0:
                mtr += "G%02.0f" % (speed(val, "MPS").value("KT"),)

        mtr += "KT "
    # vis
    if data["vsby_m"] is not None:
        val = (units("meter") * data["vsby_m"]).to(units("mile")).m
        mtr += "%sSM " % (vsbyfmt(val),)
    # Present Weather Time
    combocode = ""
    for code in [
        "AU1",
        "AU2",
        "AU3",
        "AU4",
        "AU5",
        "AU6",
        "AU7",
        "AU8",
        "AU9",
    ]:
        if code not in data["extra"]:
            continue
        val = data["extra"][code]
        if val["combo"] == "1":  # lone
            if val["obscure"] == "1":
                mtr += "BR "
        elif val["combo"] == "2":  # start of dual code
            if val["descriptor"] == "7":
                combocode = "TS"
        elif val["combo"] == "3":  # end of dual code
            if val["proximity"] == "3" and val["precip"] == "02":
                mtr += "+%sRA " % (combocode,)
                combocode = ""
    # Clouds
    for code in ["GD1", "GD2", "GD3", "GD4", "GD5", "GD6"]:
        if code not in data["extra"]:
            continue
        val = data["extra"][code]
        skycode = SKY_STATE_CODES[val["state_code"]]
        height = val["height"]
        if skycode == "CLR":
            mtr += "CLR "
        elif height is None:
            continue
        else:
            hft = (units("meter") * height).to(units("feet")).m / 100.0
            mtr += "%s%03.0f " % (skycode, hft)
    # temperature
    tgroup = None
    if (
        data.get("airtemp_c_qc") not in ["2", "3"]
        and data["airtemp_c"] is not None
    ):
        tmpc = data["airtemp_c"]
        dwpc = data["dewpointtemp_c"]
        mtr += "%s%02.0f/" % ("M" if tmpc < 0 else "", abs(tmpc))
        if dwpc is not None:
            mtr += "%s%02.0f" % ("M" if dwpc < 0 else "", abs(dwpc))
            tgroup = "T%s%03i%s%03i" % (
                "1" if tmpc < 0 else "0",
                abs(tmpc) * 10.0,
                "1" if dwpc < 0 else "0",
                abs(dwpc) * 10.0,
            )
        mtr += " "
    # altimeter
    if (
        "MA1" in data["extra"]
        and data["extra"]["MA1"].get("altimeter") is not None
    ):
        altimeter = pressure(data["extra"]["MA1"]["altimeter"], "HPA").value(
            "IN"
        )
        mtr += "A%4.0f " % (altimeter * 100,)
    rmk = []
    for code in ["AA1", "AA2", "AA3", "AA4"]:
        if code not in data["extra"]:
            continue
        hours = data["extra"][code].get("hours")
        depth = data["extra"][code].get("depth")
        if hours is None or depth is None or hours == 12:
            continue
        if depth == 0 and data["extra"][code]["cond_code"] != "2":
            continue
        if hours in [3, 6]:
            prefix = "6"
        elif hours == 24:
            prefix = "7"
        elif hours == 1:
            prefix = "P"
        else:
            warnings.warn(f"Unknown precip hours {hours}")
            continue
        amount = (units("mm") * depth).to(units("inch")).m
        rmk.append("%s%04.0f" % (prefix, amount * 100))
    if data["mslp_hpa"] is not None:
        rmk.append("SLP%03.0f" % (data["mslp_hpa"] * 10 % 1000,))
    if tgroup is not None:
        rmk.append(tgroup)
    # temperature groups
    group4 = {"M": "////", "N": "////"}
    for code in ["KA1", "KA2", "KA3", "KA4"]:
        if code not in data["extra"]:
            continue
        val = data["extra"][code]
        hours = val.get("hours")
        if hours is None:
            continue
        typ = val["code"]
        tmpc = val["tmpc"]
        if tmpc is None:
            continue
        if hours is None or hours == 12:
            continue
        if hours == 6 and typ == "M":
            prefix = "1"
        elif hours == 6 and typ == "N":
            prefix = "2"
        elif hours == 24:
            group4[typ] = "%s%03i" % ("1" if tmpc < 0 else "0", abs(tmpc) * 10)
            continue
        else:
            warnings.warn(f"Unknown temperature hours {hours} typ: {typ}")
            continue
        rmk.append(
            "%s%s%03i" % (prefix, "1" if tmpc < 0 else "0", abs(tmpc) * 10)
        )
    if group4["M"] != "////" or group4["N"] != "////":
        rmk.append("4%(M)s%(N)s" % group4)
    # 3-hour pressure tendency
    if (
        "MD1" in data["extra"]
        and data["extra"]["MD1"]["threehour"] is not None
    ):
        rmk.append(
            "5%s%03i"
            % (
                data["extra"]["MD1"]["code"],
                data["extra"]["MD1"]["threehour"] * 10,
            )
        )
    rmk.append("IEM_DS3505")
    mtr += "RMK %s " % (" ".join(rmk),)
    data["metar"] = mtr.strip()


def parser(msg, call_id, add_metar=False):
    """Parse the message(single line) into a dict

    Args:
      msg (str): the single line of data to parse into a dict
      call_id (str): hard coded call_id as the data can't be trusted, sigh
      add_metar (bool,optional): should a METAR be generated? Default: False

    Returns:
      dict or None
    """
    match = DS3505_RE.match(msg)
    if not match:
        return
    data = match.groupdict()
    # Seems like these obs with this flag are 'bad'
    if data["srcflag"] in ["A", "B"]:
        return
    data["valid"] = datetime.strptime(
        "%s %s" % (data["yyyymmdd"], data["hhmi"]), "%Y%m%d %H%M"
    ).replace(tzinfo=timezone.utc)
    data["call_id"] = call_id
    data["lat"] = _d1000(data["lat"])
    data["lon"] = _d1000(data["lon"])
    data["wind_speed_mps"] = _d10(data["wind_speed_mps"])
    data["airtemp_c"] = _d10(data["airtemp_c"])
    data["dewpointtemp_c"] = _d10(data["dewpointtemp_c"])
    data["mslp_hpa"] = _d10(data["mslp_hpa"])
    for elem in ["drct", "ceiling_m", "vsby_m", "elevation"]:
        data[elem] = _tonumeric(data[elem])

    data["extra"] = {}
    try:
        parse_extra(data, msg[105:])
    except Exception:
        pass
    if add_metar:
        try:
            gen_metar(data)
        except Exception:
            LOG.warning(
                json.dumps(data, indent=True, sort_keys=True, default=str)
            )
            raise

    return data


def parse_extra(data, extra):
    """Parse the additional data fields"""
    pos = 0
    while pos < len(extra):
        code = extra[pos : pos + 3]
        pos += 3
        if code == "ADD":
            continue
        if code == "QNN":
            data["extra"]["QNN"] = {}
            code = extra[pos : pos + 5]
            while QNN_RE.match(code):
                pos += 5
                data["extra"]["QNN"][code] = extra[pos : pos + 6]
                pos += 6
                code = extra[pos : pos + 5]
            continue
        if code == "REM":
            data["extra"]["REM"] = {}
            code = extra[pos : pos + 3]
            while code in ["SYN", "AWY", "MET", "SOD", "SOM", "HPD"]:
                pos += 3
                sz = int(extra[pos : pos + 3])
                pos += 3
                data["extra"]["REM"][code] = extra[pos : pos + int(sz)]
                pos += sz
                code = extra[pos : pos + 3]
            continue
        if code == "EQD":
            data["extra"]["EQD"] = {}
            code = extra[pos : pos + 3]
            while EQD_RE.match(code):
                pos += 3
                data["extra"]["EQD"][code] = extra[pos : pos + 13]
                pos += 13
                code = extra[pos : pos + 3]
            continue
        if code not in ADDITIONAL:
            raise Exception(
                ("Unaccounted for %s\n" "remaining '%s'\n" "extra: '%s'")
                % (code, extra[pos:], extra)
            )
        data["extra"][code] = {}
        for token in ADDITIONAL[code]:
            if len(token) == 3:
                data["extra"][code][token[0]] = token[2](
                    extra[pos : pos + token[1]]
                )
            else:
                data["extra"][code][token[0]] = extra[pos : pos + token[1]]
            pos += token[1]
