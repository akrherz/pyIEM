"""Tests for the DS3505 format."""
# pylint: disable=redefined-outer-name

import pytest
import numpy as np
from pyiem.ncei import ds3505
from pyiem import util
from pyiem.util import get_dbconn, utc, get_test_file


@pytest.fixture()
def dbcursor():
    """Get a database cursor."""
    pgconn = get_dbconn("asos")
    yield pgconn.cursor()
    pgconn.close()


def test_issue298_precip():
    """Test what our code does with AH precip fields."""
    msg = (
        "0083010010999991988123100004+70933-008667FM-12+0009ENJA "
        "V0202801N01181004201CN0010001N9-01061-01191101621ADDAA106000591"
        "AG10000AY181061AY231061GF107991071091004501001001MD1210451+9999MW1851"
    )
    data = ds3505.parser(msg, "ENJA", add_metar=True)
    ans = (
        "ENJA 310000Z AUTO 28023KT 1SM M11/M12 RMK 60002 SLP162 "
        "T11061119 52045 IEM_DS3505"
    )
    assert data["metar"] == ans


def test_vsby_format():
    """Test our conversion to fractions."""
    for i in np.arange(0, 3, 0.1):
        assert ds3505.vsbyfmt(i) is not None


def test_process_metar_bad():
    """Test that we can deal with an invalid formatted METAR."""
    metar = (
        "QQQQ 012153Z 23016G25KT 10TSM TSGRRA FEW025 SCT055 17/04 A2982 RMK "
        "P0000 AO2 SLP104 T01720044 10106 20072 53018="
    )
    now = util.utc(2017, 11, 1)
    ob = ds3505.process_metar(metar, now)
    assert abs(ob.mslp - 1010.4) < 0.1


def test_process_really_bad_metar():
    """Test what happens with very bad metar garbage."""
    metar = "QQQQ 012453Z"
    now = util.utc(2017, 11, 1)
    ob = ds3505.process_metar(metar, now)
    assert ob is None


def test_process_metar():
    """Exercise some deamons from that function"""
    metar = "KALO 011300Z AUTO 0SM 02/02 RMK T00220017 IEM_DS3505"
    now = util.utc(2017, 11, 1)
    ob = ds3505.process_metar(metar, now)
    assert ob.vsby == 0


def test_200519():
    """Found another issue with BRO."""
    msg = (
        "0251722500129191995040600003+25900-097433SY-SA+0006BRO  "
        "V0201405N004652200019N0160001N1+02445+01835100815ADDAA101000095AA2"
        "06000091AG10000GF100991001001999999001001GP10060021701024053201027"
        "006401024GQ100600732926889GR100600393913669MA1100811100755REMSYN015 "
        "333 555 90600;AWY022FEW CU TIDE DEP 00///;QNNKA1 0 00065MA1D0 "
        "29750QA1 0 10081SA1 0 00076YA1 0 14009"
    )
    data = ds3505.parser(msg, "BRO", add_metar=True)
    ans = (
        "BRO 060000Z AUTO 14009KT 10SM 24/18 A2977 "
        "RMK SLP081 T02440183 IEM_DS3505"
    )
    assert data["metar"] == ans


def test_171024():
    """Bad parse for ALO"""
    msg = (
        "0088999999949101950010113005+42550-092400SAO  +026599999V02"
        "099999000050000049N000000599+00224+00175999999EQDN01 00000"
        "JPWTH 1QNNG11 1 00000K11 1 00035L11 1 00000N11 1 00000S11 "
        "1 00036W11 1 00000"
    )
    data = ds3505.parser(msg, "ALO", add_metar=True)
    ans = "ALO 011300Z AUTO 0SM 02/02 RMK T00220017 IEM_DS3505"
    assert data["metar"] == ans


def test_badtemp():
    """Station had obviously bad temperature, see what QC said"""
    msg = (
        "0171030750999992005041908204+58450-003083FM-15+0036EGPC "
        "V0201401N004612200019N0112651N1+99999+99999999999ADDGA1021"
        "+009609999GF102991999999999999999999MA1100911999999MW1001"
        "REMMET045EGPC 190820Z 14009KT 9999 FEW032 35/33 Q1009;"
        "EQDQ01+003503ATOT  Q02+003303ATOD  Q03+000000PRSWM2"
    )
    data = ds3505.parser(msg, "EGPC", add_metar=True)
    ans = "EGPC 190820Z AUTO 14009KT 7SM A2980 RMK IEM_DS3505"
    assert data["metar"] == ans


def test_altimeter():
    """See what we are doing with altimeter and SLP"""
    msg = (
        "0125030750999992013102322004+58450-003083FM-12+003699999"
        "V0202501N009819999999N030000199+00671+00351099051ADDMA"
        "1999990098611MD1110201+9990OD139901441999REMSYN07003075 "
        "45980 /2519 10067 20035 39861 49905 51020 333 8//99 90710 "
        "91128="
    )
    data = ds3505.parser(msg, "EGPC", add_metar=True)
    ans = (
        "EGPC 232200Z AUTO 25019KT 19SM 07/04 RMK "
        "SLP905 T00670035 51020 IEM_DS3505"
    )
    assert data["metar"] == ans


def test_6hour_temp(dbcursor):
    """6 hour high/low"""
    # 2016-08-12 23:53:00
    # KAMW 122353Z AUTO 35014G23KT 10SM CLR 25/21 A2983 RMK AO2 SLP092
    # 60000 T02500211 10272 20250 55001
    msg = (
        "0271725472949892016081223537+41991-093619FM-15+0291KAMW V03035"
        "05N007252200059N0160935N5+02505+02115100925ADDAA101000095AA206"
        "000021GA1005+999999999GD10991+9999999GF1009919999999999999999"
        "99KA1060M+02721KA2060N+02501MA1101025097575MD1590019+9999"
        "OC101185REMMET11708/12/16 17:53:02 METAR KAMW 122353Z "
        "35014G23KT 10SM CLR 25/21 A2983 RMK AO2 SLP092 60000 "
        "T02500211 10272 20250 55001"
    )
    data = ds3505.parser(msg, "KAMW", add_metar=True)
    # db schema for testing only goes to 2015
    data["valid"] = utc(2011, 1, 12, 23, 53)
    ans = (
        "KAMW 122353Z AUTO 35014G23KT 10SM CLR 25/21 A2983 "
        "RMK 60000 SLP092 T02500211 10272 20250 55001 IEM_DS3505"
    )
    assert data["metar"] == ans

    assert ds3505.sql(dbcursor, "AMW", data) == 1


def test_precip_6group():
    """3 hour precip"""
    # 2016-08-12 02:53:00
    # KAMW 120253Z AUTO 36012KT 1 1/4SM +TSRA BR SCT005
    # SCT009 OVC014 21/21 A2991 RMK AO2 WSHFT 0219 LTG DSNT ALQDS
    # RAE00B24 TSE0155B27 SLP119 P0080 60232 T02110211 53037
    msg = (
        "0463725472949892016081202537+41991-093619FM-15+0291KAMW V03"
        "03605N00625004275MN0020125N5+02115+02115101195ADDAA10102069"
        "5AA203058991AU107000025AU230020035AU300001015AW1105AW2635AW"
        "3905AW4951GA1045+001525999GA2045+002745999GA3085+004275999"
        "GD12991+0015259GD22991+0027459GD34991+0042759GE19MSL   "
        "+99999+99999GF199999999999001521999999MA1101295097845"
        "MD1390379+9999REMMET18308/11/16 20:53:02 METAR KAMW "
        "120253Z 36012KT 1 1/4SM +TSRA BR SCT005 SCT009 "
        "OVC014 21/21 A2991 RMK AO2 WSHFT 0219 LTG DSNT "
        "ALQDS RAE00B24 TSE0155B27 SLP119 P0080 60232 "
        "T02110211 53037EQDQ01  05898PRCP03"
    )
    data = ds3505.parser(msg, "KAMW", add_metar=True)
    # NOTE, this should be 0.80 instead of 0.81 !?!?!, NCDC wrong?
    ans = (
        "KAMW 120253Z AUTO 36012KT 1 1/4SM +TSRA BR "
        "SCT005 SCT009 OVC014 21/21 A2991 RMK P0081 60232 "
        "SLP119 T02110211 53037 IEM_DS3505"
    )
    assert data["metar"] == ans


def test_metar():
    """Can we replicate an actual METAR"""
    # IEM METAR database has this for 1 Jan 2016
    # KAMW 010713Z AUTO 29013KT 10SM BKN017 OVC033 M05/M08 A3028 RMK
    #    AO2 T10501083
    msg = (
        "0232725472949892016010107137+41991-093619FM-16+0291KAMW "
        "V0302905N00675005185MN0160935N5-00505-00835999999ADDGA1075+"
        "005185999GA2085+010065999GD13991+0051859GD24991+0100659"
        "GE19MSL   +99999+99999GF199999999999005181999999MA1102545"
        "099065REMMET09501/01/16 01:13:02 SPECI KAMW 010713Z "
        "29013KT 10SM BKN017 OVC033 M05/M08 A3028 RMK AO2 T10501083"
    )
    data = ds3505.parser(msg, "KAMW", add_metar=True)
    ans = (
        "KAMW 010713Z AUTO 29013KT 10SM BKN017 OVC033 "
        "M05/M08 A3028 RMK T10501083 IEM_DS3505"
    )
    assert data["metar"] == ans


def test_metar2():
    """Can we do more"""
    # KAMW 010853Z AUTO 30013KT 10SM OVC017 M05/M08 A3028 RMK
    #    AO2 SLP266 T10501083 55004
    msg = (
        "0232725472949892016010108537+41991-093619FM-15+0291KAMW "
        "V0303005N00675005185MN0160935N5-00505-00835102665ADDAA1"
        "01000095GA1085+005185999GD14991+0051859GE19MSL   +99999+"
        "99999GF199999999999005181999999MA1102545099065MD1590049+"
        "9999REMMET10101/01/16 02:53:02 METAR KAMW 010853Z 30013KT "
        "10SM OVC017 M05/M08 A3028 RMK AO2 SLP266 T10501083 55004"
    )
    data = ds3505.parser(msg, "KAMW", add_metar=True)
    ans = (
        "KAMW 010853Z AUTO 30013KT 10SM OVC017 M05/M08 "
        "A3028 RMK SLP266 T10501083 55004 IEM_DS3505"
    )
    assert data["metar"] == ans


def test_171023():
    """This failed"""
    msg = (
        "0174030750999991977080406004+58450-003083FM-12+0039EGPC "
        "V0209991C00001066001CN0750001N9+00901+00801101131ADDAJ10000"
        "9199999999AY111999GA1011+006009089GA2031+036009039GA3061+"
        "066009029GF107991021081008001031061MD1710131+9999MW1021WG"
        "199999999999REMSYN02920310 70307 81820 83362 86272"
    )
    data = ds3505.parser(msg, "KAMW", add_metar=True)
    assert data is not None

    msg = (
        "0067030750999991999102018004+58450-003080FM-12+0039EGPC "
        "V02099999999999999999N9999999N1+99999+99999999999REMSYN058"
        "AAXX  20184 03075 46/// ///// 1//// 2//// 4//// 5//// 333;"
    )
    data = ds3505.parser(msg, "EGPC", add_metar=True)
    assert data is not None


def test_basic():
    """Can we parse it, yes we can"""
    msg = (
        "0114010010999991988010100004+70933-008667FM-12+0009ENJA "
        "V0203301N01851220001CN0030001N9-02011-02211100211ADDAA10"
        "6000091AG14000AY131061AY221061GF102991021051008001001001"
        "MD1710141+9999MW1381OA149902631REMSYN011333   91151"
    )
    data = ds3505.parser(msg, "ENJA", add_metar=True)
    assert data is not None
    ans = (
        "ENJA 010000Z AUTO 33036KT 2SM "
        "M20/M22 RMK SLP021 T12011221 57014 IEM_DS3505"
    )
    assert data["metar"] == ans


def test_read():
    """Can we process an entire file?"""
    for line in get_test_file("NCEI/DS3505.txt", fponly=True):
        data = ds3505.parser(line.decode("ascii").strip(), "ENJA")
        assert data is not None

    for line in get_test_file("NCEI/DS3505_KAMW_2016.txt", fponly=True):
        data = ds3505.parser(line.decode("ascii").strip(), "KAMW")
        assert data is not None
