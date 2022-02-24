"""SHEF"""
# stdlib
from datetime import timedelta

import mock
import pytest
from pyiem.exceptions import InvalidSHEFEncoding, InvalidSHEFValue
from pyiem.nws.products.shef import (
    make_date,
    parse_station_valid,
    parser,
    process_di,
    process_message_a,
    process_message_b,
    process_message_e,
    process_messages,
    process_modifiers,
    strip_comments,
)
from pyiem.reference import TRACE_VALUE
from pyiem.util import utc, get_test_file


def test_220224_redundant_dh():
    """Test that a product with redundant DH values does not fool us."""
    prod = parser(get_test_file("SHEF/RR3GJT.txt"), utcnow=utc(2022, 2, 25))
    assert prod.data[4].valid == utc(2022, 2, 24, 7)


def test_dy():
    """Test support for the DY time variable."""
    msg = (
        ".BR GAMMA 220202 /SAIRF/SWIRF\n"
        "IA111  DY220202 / 100 / 2.2 : 1.8, 27 AM 210927 , 27  \n"
        "IA112  DY2202021112 / 100 / 2.2 : 1.8, 27 AM 210927 , 27  \n"
        ".END"
    )
    res = process_message_b(msg)
    assert res[0].valid == utc(2022, 2, 2, 12)
    assert res[2].valid == utc(2022, 2, 2, 11, 12)


def test_220125_dv():
    """Test various combinations of DV that DTX came up with."""
    prod = parser(get_test_file("SHEF/DV.txt"), utcnow=utc(2022, 1, 25, 18))
    assert prod.data[0].dv_interval == timedelta(hours=24)
    assert prod.data[1].dv_interval is None
    assert prod.data[2].dv_interval is None


def test_211230_rrmsgx():
    """Test that no exception happens with a non SHEF containing RRM."""
    prod = parser(get_test_file("SHEF/RRMSGX.txt"), utcnow=utc(2021, 12, 30))
    assert not prod.data


def test_211025_rr3mkx():
    """Test that we do not take some of the bad data here."""
    utcnow = utc(2021, 10, 25)
    prod = parser(get_test_file("SHEF/RR3MKX.txt"), utcnow=utcnow)
    assert not prod.data


def test_a_format():
    """Test the parsing of A format SHEF."""
    utcnow = utc(2021, 9, 17, 12)
    prod = parser(get_test_file("SHEF/A.txt"), utcnow=utcnow)
    assert len(prod.data) == 5
    assert prod.data[0].valid == utc(2021, 9, 10, 11)
    assert prod.data[0].data_created == utc(2021, 9, 17, 16, 40)


def test_b_format():
    """Test the parsing of B format SHEF."""
    utcnow = utc(2021, 9, 17, 0)
    prod = parser(get_test_file("SHEF/B.txt"), utcnow=utcnow)
    assert len(prod.data) == 16
    assert prod.data[0].valid == utc(2021, 9, 16, 21, 45)
    assert prod.data[0].physical_element == "QT"


def test_e_format():
    """Test the parsing of E format SHEF."""
    utcnow = utc(2021, 9, 17, 0)
    prod = parser(get_test_file("SHEF/E.txt"), utcnow=utcnow)
    assert len(prod.data) == 194
    assert prod.data[0].valid == utc(2021, 9, 17)
    assert prod.data[0].data_created == utc(2021, 9, 17)


def test_rtpdtx():
    """Test that we handle the complexity with RTPs."""
    utcnow = utc(2021, 9, 20, 0, 3)
    prod = parser(get_test_file("SHEF/RTPDTX.txt"), utcnow=utcnow)
    assert len(prod.data) == 4 * 22


def test_mixed_AE():
    """Test that we can parse a product with both A and E format included."""
    utcnow = utc(2021, 9, 20, 0, 2)
    prod = parser(get_test_file("SHEF/mixed_AE.txt"), utcnow=utcnow)
    assert len(prod.data) == 79  # unsure this is right, going for now


def test_seconds():
    """Test that we handle DH with seconds provided."""
    utcnow = utc(2021, 9, 20, 0, 3)
    prod = parser(get_test_file("SHEF/RR2LAC.txt"), utcnow=utcnow)
    assert len(prod.data) == 8
    assert prod.data[0].valid == utc(2021, 9, 19, 23, 51, 59)
    assert prod.data[0].str_value == "73"
    assert abs(prod.data[0].num_value - 73.0) < 0.01


def test_dh24():
    """Test that DH24 is handled properly."""
    msg = ".A YCPC1 210726 PD DH240000 /PCIRRZZ 6.89"
    res = process_message_a(msg, utc(2021, 9, 20, 1, 1))
    assert res[0].valid == utc(2021, 7, 27, 7)


def test_encoded_pairs():
    """Test that we can handle this wild encoding."""
    msg = ".A AMIT2 0124 DH12/DC201101241200/TB 6.065/TV 12.056/"
    res = process_message_a(msg)
    assert res[0].depth == 6
    assert abs(res[0].num_value - 65) < 0.01

    msg = ".A AMIT2 0124 DH12/DC1101241200/TB -6.005/TV -12.9999/"
    res = process_message_a(msg)
    assert res[0].depth == 6
    assert abs(res[0].num_value - -5) < 0.01
    assert res[1].depth == 12
    assert res[1].num_value is None


def test_5_4_1():
    """Test examples found in the SHEF manual."""
    msg = ".A CSAT2 0309 DH12/HG 10.25"
    res = process_message_a(msg, utc(2021, 3, 9))
    assert res[0].valid == utc(2021, 3, 9, 12)

    msg = ".A MASO1 0907 C DH22/QR .12/DM0908/DH09/QR 5.0"
    res = process_message_a(msg, utc(2021, 9, 9))
    assert res[0].valid == utc(2021, 9, 8, 3)
    assert res[1].valid == utc(2021, 9, 8, 14)

    msg = ".A BON 810907 P DH24/QID 250./DM090806/QIQ 300./QIQ 310."
    res = process_message_a(msg, utc(1981, 9, 9))
    assert res[0].valid == utc(1981, 9, 8, 7)
    assert res[1].valid == utc(1981, 9, 8, 13)


def test_5_4_2():
    """Test examples found in the SHEF manual."""
    msg = (
        ".B PDX 1011 P DH06/HG/DRH-12/HG\n"
        ":\n"
        ": ID 6 AM STAGE THIS MORNING, 6 PM STAGE LAST NIGHT, STATION NAME\n"
        ":\n"
        "PHIO3 9.7/6.2E :PHILOMATH, OR\n"
        "JFFO3 4.5/7.2  :JEFFERSON, OR\n"
        ".END"
    )
    res = process_message_b(msg, utc(2021, 10, 11))
    assert res[0].valid == utc(2021, 10, 11, 13)
    assert res[1].valid == utc(2021, 10, 11, 1)
    assert res[1].qualifier == "E"

    msg = (
        ".B PDR 0807 P DH05/SW/PC/DUS/TA\n"
        ": THIS IS SELECTED SNOTEL DATA\n"
        "ANRO3 DH0523/0.1/ 72.4/ 7.2\n"
        "BCDO3 DH0456/0.2/ 68.5/13.7\n"
        "BLAO3 DH0508/0.0/122.9/22.6\n"
        ".END"
    )
    res = process_message_b(msg, utc(2021, 8, 7))
    assert res[0].valid == utc(2021, 8, 7, 12, 23)


def test_7_4_7():
    """Test an evolving time series."""
    msg = (
        ".A COMT2 850327 C DH07/HG 1.89/DH1422/HG 2.44/DH1635/HG 8.71/"
        "DH1707/HG 7.77/DH1745/HG 11.42/DH2022/HG 4.78/DH2315/"
        "HG 12.55/DD280020/HG 17.02/DH0140/HG 12.00/DH0420/"
        "HG 27.21/DH0700/HG 10.55"
    )
    res = process_message_a(msg, utc(1985, 3, 27))
    assert res[-1].valid == utc(1985, 3, 28, 13)


def test_comment_on_off():
    """Test we can handle comments."""
    msg = (
        ".B ELP 0328 M DH07/HG/DUS/HG/HI\n"
        ":\n"
        ": RIVER STAGES FEET METERS  TENDENCY\n"
        ": PRESIDIO : PRST2 4.9 / 1.49 / :STEADY: 0\n"
        ".END\n"
    )
    res = process_message_b(msg, utc(1985, 3, 27))
    assert res[2].num_value == 0


def test_packed_b():
    """Test parsing of the packed B format."""
    msg = (
        ".B LCH 0305 C DH07/HG/PP\n"
        "LKCL1 0.9/ .04 , GLML1 13.7 //, OKDL1 10.6 / 0.4\n"
        ".END\n"
    )
    res = process_message_b(msg, utc(2021, 3, 5))
    assert res[3].str_value == ""


def test_doubleslash():
    """Test we can handle the tricky doubleslash stuff."""
    msg = (
        ".B LCH 0920 C DH0110/HGIRZ/HPIRZ\n"
        ":\n"
        ": TOLEDO BEND RES\n"
        "BKLT2 DMM//168.02:\n"
        ".END"
    )
    res = process_message_b(msg, utc(2021, 9, 20))
    assert not res


def test_invalid():
    """Test that we properly fail for an invalid encoding."""
    msg = ".E NUTQ7  E DH/HGIRG/DIN15/"
    with pytest.raises(InvalidSHEFEncoding):
        process_message_e(msg)


def test_empty_a():
    """Test that we don't error on an empty .A message."""
    msg = ".A   "
    res = process_message_a(msg)
    assert not res


def test_e_comment_in_header():
    """Test that we handle a comment found in the header."""
    utcnow = utc(2021, 9, 20, 5, 5)
    prod = parser(get_test_file("SHEF/RR2GSP.txt"), utcnow=utcnow)
    # Has 24 'obs', but we trim obs from the future and trailing empty for E
    assert len(prod.data) == 16
    assert prod.data[15].valid == utc(2021, 9, 20, 4)


def test_rr2phi():
    """Test that we can handle this RR2."""
    utcnow = utc(2021, 9, 20, 5, 10)
    prod = parser(get_test_file("SHEF/RR2PHI.txt"), utcnow=utcnow)
    assert len(prod.data) == 560  # assumed correct for now


def test_parse_b():
    """Test that this B message does not error."""
    msg = (
        ".B ONJSC 20210920 DH0435/HMIRZ/\n"
        "RUMN4 0.14/\n"
        "OCPN4 0.34/\n"
        "SETN4 0.11/\n"
        ".END"
    )
    res = process_message_b(msg)
    assert len(res) == 3


def test_unit_switching():
    """Test the handling of units."""
    msg = (
        ".A KLRM4 20210919 E DH22 /DUS/TA 22.33/US 0.626/UD 118/"
        "PPHRP 0.0/XR 69.8/DUE/TV 2.081/TV 4.079"
    )
    res = process_message_a(msg)
    assert len(res) == 7
    assert res[0].unit_convention == "S"


def test_dc():
    """Test that we can handle fullblown dates."""
    msg = (
        ".ER MORW2 20210919 Z DC202109200523/DUE/DQG/DH1800/HTIFE/DIH6/"
        "9.9/9.9/9.9/9.9/9.9/9.9/9.9/9.9"
    )
    res = process_message_e(msg)
    assert res[0].valid == utc(2021, 9, 19, 18)


def test_e_timestamps():
    """Test we can process this."""
    msg = ".E RBNT1 0920 C DH0500/PPHRZ/0.00"
    res = process_message_e(msg, utc(2021, 9, 20, 5))
    assert res[0].valid == utc(2021, 9, 20, 10)


def test_dc_in_b():
    """Test that we can handle a DC code within B format."""
    msg = (
        ".B ATR 0919 C DH23/DC0919/QTD\n"
        "TLLA1   5.482 : Tallapoosa\n"
        "WPKA1  21.060 : Coosa\n"
        ".END"
    )
    res = process_message_b(msg, utc(2021, 9, 19))
    assert res[0].data_created == utc(2021, 9, 20, 4)


def test_jan1():
    """Test things when we cross the new year."""
    msg = ".A COMT2 1231 C DH23/HG 1.89"
    res = process_message_a(msg, utc(2000, 1, 1))
    assert res[0].valid == utc(2000, 1, 1, 5)


def test_did1():
    """Test 1 day interval data."""
    msg = (
        ".ER HARP1 0920 E DC2109201005/DH20/QRIFF/DID1"
        "/     /     28.0/     23.0/     19.7"
    )
    res = process_message_e(msg, utc(2021, 9, 20))
    assert res[0].valid == utc(2021, 9, 21, 0)
    assert res[1].valid == utc(2021, 9, 22, 0)


def test_b_dm():
    """Test B format with DM in header."""
    msg = (
        ".BR MSP 210920 DM092000/DC09200455 /SDIPZ/DH01/SFIPZ\n"
        "ABEC2L      0.0 / 0.0: Avg (inches) Entire Basin\n"
        ".END"
    )
    res = process_message_b(msg, utc(2021, 9, 20))
    assert res[0].valid == utc(2021, 9, 20)
    assert len(res) == 2
    assert res[1].valid == utc(2021, 9, 20, 1)


def test_multiline_b_header():
    """Test that we can deal with a multi-line B header."""
    utcnow = utc(2021, 9, 20, 12)
    prod = parser(get_test_file("SHEF/B_multi.txt"), utcnow=utcnow)
    assert len(prod.data) == 42


def test_cs_timezone():
    """Test that we can handle standard time."""
    msg = ".E GDMM5 20210919 CS DH1948/TAIRG/DIN06/   70/   67/   67"
    res = process_message_e(msg, utc(2021, 9, 20))
    # 748 PM CST -> 848 PM CDT -> 0148 UTC
    assert res[0].valid == utc(2021, 9, 20, 1, 48)


def test_process_e_bad_value():
    """Test that we get nothing when finding a bad value."""
    msg = ".E GDMM5 20210919 CS DH1948/TAIRG/DIN06/   70/   HI/   67"
    with pytest.raises(InvalidSHEFValue):
        process_message_e(msg, utc(2021, 9, 20))


def test_qualifier():
    """Test the qualifier logic."""
    msg = ".AR SHPP1 20210925 Z DH06/DC202109210148/DUE/DQG/QIIFE 151000.0"
    res = process_message_a(msg)
    assert res[0].qualifier == "G"


def test_parse_station_valid():
    """Test handling of odd things."""
    station, _base, _valid, res = parse_station_valid(".A DMX 0919", utc())
    assert station == "DMX"
    assert not res


def test_process_modififers_unknown_D():
    """Test that we get a value error for this."""
    with pytest.raises(ValueError):
        process_modifiers("DZZ", None, utc())
    with pytest.raises(ValueError):
        process_modifiers("DVZ", None, utc())


def test_unknown_di():
    """Test that value error is raised for an unknown DI."""
    with pytest.raises(ValueError):
        process_di("DIZ")


def test_b_extra_tokens():
    """Test a theoretical B format with extra tokens in the first section."""
    msg = (
        ".BR MSP 210920 SDIPZ DM092000/DC09200455/DH01/SFIPZ\n"
        "ABEC2L      0.0 / 0.0: Avg (inches) Entire Basin\n"
        ".END"
    )
    res = process_message_b(msg, utc(2021, 9, 20))
    assert res[0].physical_element == "SD"


def test_a_extra_tokens():
    """Test a theoretical A format with extra tokens in first section."""
    msg = ".AR SHPP1 20210925 Z DH06 DC202109210148/DUE/DQG/QIIFE 151000.0"
    res = process_message_a(msg)
    assert res[0].qualifier == "G"


def test_dv():
    """Test that we can handle the ugliness of DV codes."""
    msg = (
        ".AR MRJA1 210920 C DH0700/TX 81/TN 72/TA 74/DVD04/PPV 2.49"
        "/TQ 99/DC2109211054"
    )
    res = process_message_a(msg)
    assert res[3].dv_interval == timedelta(days=4)
    assert res[4].dv_interval is None


def test_missing_a():
    """Test we can handle missing data in A format."""
    msg = ".A TFX 0921 M DH1000/TAIR /TDIR  0.0/XRIR 255/UDIR /USIR /"
    res = process_message_a(msg)
    assert res[0].str_value == ""


def test_bad_paired_element():
    """Test that we can handle a paired element without value."""
    msg = ".AR HBRA2 210921 Z DH1600/DC2109211600/HGIRZZ 22.65/HQIRZZ 539/"
    res = process_message_a(msg)
    assert res[1].depth == 539


def test_b_datetime():
    """Test that we get a datetime in the face of massive ambiguity."""
    msg = (
        ".BR BRO 210921 /HP/TW/QT\n"
        "MADT2  103.85 / 85.10 / 0.88 :ANZALDUAS DAM - RELEASE IN 1000S\n"
        "XXXT2  DHM / 103.85 / 85.10 / 0.88\n"
        ".END"
    )
    res = process_message_b(msg)
    assert res[0].valid == utc(2021, 9, 21, 12)
    assert res[2].str_value == "0.88"
    assert len(res) == 3


def test_a_dh_problem():
    """Test that we can deal with this fun."""
    msg = ".A DVT 0921 MS DH0800 DVH13 /TAVRZN 69"
    res = process_message_a(msg)
    assert res[0].physical_element == "TA"
    assert res[0].raw == msg


def test_process_messages_with_lots_of_errors():
    """Test that our error handling works."""
    messages = [".A DVT DH0800/TAVRZN 69"] * 10  # need enough to loop over 5
    messages.insert(0, ".A DVT DH/TAVRZN 69")
    prod = mock.Mock()
    prod.utcnow = utc()
    prod.data = []
    prod.warnings = []
    assert process_messages(process_message_a, prod, messages) == 0
    assert prod.warnings
    assert not prod.data


def test_strip_comments():
    """Test that a colon does not trip us up!"""
    msg = ".A SNPC1 210921 PD DH170500 /TA 85:"
    res = strip_comments(msg)
    assert res == ".A SNPC1 210921 PD DH170500 /TA 85"


def test_e_spaced_din():
    """Test that this DIN with a space does not trip us up."""
    msg = ".E RDCW2 210922 Z DH010000 /PPHRR/ DIH1 / 0.12"
    res = process_message_e(msg)
    assert res[0].valid == utc(2021, 9, 22, 1)


def test_trace():
    """Test that Trace values are handled."""
    msg = ".A UBW 210921 L DH1800/PC 50/SF *****/SD T/DC2109211739"
    res = process_message_a(msg)
    assert abs(res[0].num_value - 0.50) < 0.0001
    assert res[1].num_value is None
    assert abs(res[2].num_value - TRACE_VALUE) < 0.0001


def test_a_no_station():
    """Test that we raise a SHEF Exception when no station/datetime."""
    msg = ".A  20210921 Z DH2200/  1982.43"
    with pytest.raises(InvalidSHEFEncoding) as exp:
        process_message_a(msg)
    assert exp.match("^3.2")


def test_a_no_time():
    """Test that we raise a SHEF Exception when there is no timestamp."""
    msg = ".A DMX Z DH2200/  1982.43"
    with pytest.raises(InvalidSHEFEncoding) as exp:
        process_message_a(msg)
    assert exp.match("^3.2")


def test_make_date():
    """Test that exception is raised for too short of a DH message."""
    with pytest.raises(InvalidSHEFEncoding):
        make_date("DH")


def test_210922_rtpeax():
    """Test that we do not raise an exception for parsing this."""
    prod = parser(get_test_file("SHEF/RTPEAX.txt"))
    assert not prod.warnings
    assert len(prod.data) == (51 * 5)  # verified 51 lines of data x 5 cols


def test_retained_comment_field():
    """Test that we support this ugly fun."""
    msg = (
        ".A STCV2 0922 Z DH1210/DVH24/"
        'PPV 0.92"LAT=37.99 LON=-79.12  2 E Greenville  IFLOWS "/'
    )
    res = process_message_a(msg)
    assert abs(res[0].num_value - 0.92) < 0.001
    assert res[0].comment == "LAT=37.99 LON=-79.12  2 E Greenville  IFLOWS"


def test_210922_rr3fgf():
    """Test successful parsing of RR3FGF."""
    prod = parser(get_test_file("SHEF/RR3FGF.txt"))
    assert prod.data[0].station == "GRFN8"


def test_b_missing():
    """Test some trickiness with missing values."""
    msg = (
        ".BR MFR 0923 P DH07/TAIRZX/TAIRZN/PPDRZZ/SFDRZZ/SDIRZZ\n"
        "ASHO3 :Ashland      1750 :           M /    M /    M /    M /    M\n"
        "GLYO3 :Glide COOP    742 : DH0800    M /    M / 0.00 /    M /    M"
    )
    res = process_message_b(msg)
    assert res[7].str_value == "0.00"


def test_210923_rr2aly():
    """Test that we can parse RR2ALY."""
    prod = parser(get_test_file("SHEF/RR2ALY.txt"))
    assert not prod.data


def test_a_empty():
    """Test that we do not error on an empty A message."""
    msg = ".A MMRN6 20210923 Z DH/QTIRZ"
    res = process_message_a(msg)
    assert not res


def test_a_comment_with_slash():
    """Test this nightmare to support."""
    msg = (
        ".A AR338 0922 Z DH2346/DVH06/PPV 0.04"
        '"LAT=39.24 LON=-76.65  Baltimore/Lansdowne  CWOP "/"'
    )
    res = process_message_a(msg)
    assert abs(res[0].num_value - 0.04) < 0.001
    assert res[0].comment == "LAT=39.24 LON=-76.65  Baltimore/Lansdowne  CWOP"


def test_a_dc_on_own_line():
    """Test that we can handle this fun."""
    prod = parser(get_test_file("SHEF/RR3RAH.txt"))
    assert prod.data[0].str_value == "78"


def test_rr3_comment():
    """Test that we can store the free text comments in WxCoder."""
    prod = parser(get_test_file("SHEF/RR3DMX.txt"))
    assert prod.data[0].narrative.find(" safe.") > -1


def test_ddm():
    """Test that DDM is handled properly."""
    msg = (
        ".BR ALY 0926 E DH00/TAIRZX/DH08/TAIRZP/PPDRZZ/SFDRZZ/SDIRZZ\n"
        "AQW :North Adams     MA: DDM     /      /   53 /   0.00 /   M /   M"
    )
    res = process_message_b(msg)
    assert not res


def test_missing_mmm():
    """Test another missing combo used in the wind."""
    msg = (
        ".BR ATL 0926 ES DH00/TAIRZX/DH07/TAIRZP/PPDRZZ\n"
        ":Cartersville   :VPC        M /    M / M.MM"
    )
    res = process_message_b(msg)
    assert res[2].num_value is None


def test_missing_sequence():
    """Test what happens when we have a missing in a sequence."""
    msg = (
        ".BR PSR 0926 MS DH07/TAIRZX/TAIRZN/PPDRZZ/SFDRZZ/SDIRZZ\n"
        "ACYA3 :Arizona City    1525: DHM   /     M /   M /     M/    M/  M\n"
        "FHLA3 :Fountain Hills  1575: DHM   /     M /   M /     M/    M/  M\n"
        "GLEA3 :Globe           3660: DH0900/    83 /  59 /  0.20/    M/  M\n"
        "ROOA3 :Roosevelt 1WNW  2205: DHM   /     M /   M /     M/    M/  M\n"
    )
    res = process_message_b(msg, utc(2021, 9, 26))
    assert len(res) == 5
    assert res[0].valid == utc(2021, 9, 26, 16)


def test_unfilled_out_fields():
    """Test that we can deal with less than diction number of fields."""
    msg = (
        ".BR RIW 0924 M DH05/TAIRZX/TAIRZP/PPDRZZ/SFDRZZ/SDIRZZ\n"
        "AFO  : Afton             6215:   68 /  28 /    M\n"
        "CPR  : Casper            5320:   75 /  36 / 0.00 /      /   0\n"
        "DUB  : Dubois            7260:   66 /  36 /    M"
    )
    res = process_message_b(msg, utc(2021, 9, 24))
    assert len(res) == 15


def test_allow_numeric_stations():
    """Test that pure number station IDs are permitted."""
    msg = ".A 2312000 210927 PD DH090000 /PCIRR 4.76"
    res = process_message_a(msg)
    assert res[0].station == "2312000"


def test_b_too_much_data():
    """Test what happens when there is more data than dictions."""
    msg = (
        ".BR RIW 0924 M DH05/TAIRZX/TAIRZP\n"
        "AFO  : Afton             6215:   68 /  28 /    M\n"
    )
    with pytest.raises(InvalidSHEFEncoding):
        process_message_b(msg, utc(2021, 9, 24))


def test_b_bad_data():
    """Test what we get no data when things are poor."""
    msg = (
        ".BR RIW 0924 M DH05/TAIRZX/TAIRZP\n"
        "AFO  : Afton             6215:   Q /  Q\n"
    )
    res = process_message_b(msg, utc(2021, 9, 24))
    assert not res


def test_uh_ur_handling():
    """Test what happens when we get the ugly UH, UR field."""
    msg = ".A 2312000 210927 PD DH090000 /UH 3/UR 5"
    res = process_message_a(msg)
    assert res[0].num_value == 3
    assert res[0].to_english() == 30
    assert res[1].to_english() == 50


def test_211020_locationid():
    """Test that a location identifier longer than 8 characters is not ok."""
    prod = parser(get_test_file("SHEF/RR3GUM.txt"))
    assert not prod.data


def test_211006_dt():
    """Test that we can deal with DT time encoding."""
    msg = (
        ".BR MSR 20211006 DH12/DRH-18/PPQRZ/DRH-12/PPQRZ/"
        "DRH-06/PPQRZ/DRH-0/PPQRZ/PPDRZ\n"
        "SUW DT202110061155/M/M/M/M/M"
    )
    res = process_message_b(msg)
    assert res[0].valid == utc(2021, 10, 6, 11, 55)

    res = process_message_b(msg.replace("DT202110061155", "DTM"))
    assert not res
