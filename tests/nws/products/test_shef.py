"""SHEF"""
from pyiem.nws.products.shef import (
    parser,
    process_message_a,
    process_message_b,
)
from pyiem.util import utc, get_test_file


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
    msg = ".A YCPC1 210726 PD DH240000 /PCIRRZZ 6.89:"
    res = process_message_a(msg, utc(2021, 9, 20, 1, 1))
    assert res[0].valid == utc(2021, 7, 27, 7)


def test_encoded_pairs():
    """Test that we can handle this wild encoding."""
    msg = ".A AMIT2 0124 DH12/DC012412/TB 6.065/TV 12.056/"
    res = process_message_a(msg)
    assert res[0].depth == 6
    assert abs(res[0].num_value - 65) < 0.01

    msg = ".A AMIT2 0124 DH12/DC012412/TB -6.005/TV -12.9999/"
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
    assert res[1].estimated is True

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
        ".A COMT2 850327 C DH07/HG 1.89/DH1422/HG 2.44/DH1635/HG 8.71\n"
        ".A1 DH1707/HG 7.77/DH1745/HG 11.42/DH2022/HG 4.78/DH2315\n"
        ".A2 HG 12.55/DD280020/HG 17.02/DH0140/HG 12.00/DH0420\n"
        ".A3 HG 27.21/DH0700/HG 10.55"
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
