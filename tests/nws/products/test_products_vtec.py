"""Test some of the atomic stuff in the VTEC module"""

# pylint: disable=too-many-lines
import datetime

import pandas as pd
import pytest

from pyiem.nws.nwsli import NWSLI
from pyiem.nws.products.vtec import check_dup_ps
from pyiem.nws.products.vtec import parser as _vtecparser
from pyiem.nws.products.wwp import parser as wwp_parser
from pyiem.nws.ugc import UGC, UGCParseException, UGCProvider
from pyiem.nws.vtec import parse

# Local
from pyiem.util import get_test_file, utc

CUGC = "Product failed to cover all UGC"


class FakeObject:
    """Mocked thing"""

    tp = None
    valid = None
    vtec = None


def vtecparser(text, utcnow=None, nwsli_provider=None):
    """Helper."""
    return _vtecparser(
        text, ugc_provider={}, utcnow=utcnow, nwsli_provider=nwsli_provider
    )


def filter_warnings(ar, startswith="get_gid"):
    """Remove non-deterministic warnings

    Some of our tests produce get_gid() warnings, which are safe to ignore
    for the purposes of this testing
    """
    return [a for a in ar if not a.startswith(startswith)]


def test_gh1119_upgrade_wordsmithing():
    """Test the jabber message here makes some sense."""
    ugc_provider = {
        "WAZ658": UGC("WA", "Z", "658", name="West Side", wfos=["SEW"]),
        "WAZ659": UGC("WA", "Z", "659", name="East Side", wfos=["SEW"]),
    }
    prod = _vtecparser(
        get_test_file("RFWSEW.txt"),
        ugc_provider=ugc_provider,
    )
    j = prod.get_jabbers("")
    ans = (
        "SEW upgrades Fire Weather Watch to Red Flag Warning valid at Sep 3, "
        "12:00 PM PDT for East Side, West Side [WA] till Sep 3, 9:00 PM PDT "
        "2025-O-NEW-KSEW-FW-W-0004_2025-09-03T19:00Z"
    )
    assert j[0][0] == ans


def test_gh978_tsunami_warning_channels():
    """Test that we get a proper WFO channel assignment for this."""
    ugc_provider = {
        "CAZ101": UGC("CA", "Z", "101", name="Coast", wfos=["EKA"]),
    }
    prod = _vtecparser(
        get_test_file("TSU/TSUWCA_2024.txt"),
        ugc_provider=ugc_provider,
    )
    j = prod.get_jabbers("")
    assert "EKA" in j[0][2]["channels"]


def test_gh930_dueling_tropics():
    """Test that we get a special warning for this."""
    prod = vtecparser(get_test_file("TCV/TCVHGX.txt"))
    assert any(a.startswith("Dueling tropical") for a in prod.warnings)


@pytest.mark.parametrize("database", ["postgis"])
def test_gh1097_unknown_ugc(dbcursor):
    """Test that the word parishes appears as we wish."""
    prov = {
        "GUZ001": UGC("GU", "Z", "001", name="Guam", wfos=["GUM"]),
    }
    prod = _vtecparser(get_test_file("TSU/TSUGUM.txt"), ugc_provider=prov)
    prod.sql(dbcursor)
    assert prod.warnings


@pytest.mark.parametrize("database", ["postgis"])
def test_con_creates(dbcursor):
    """Test that entries are added for CONs without history."""
    prod = vtecparser(get_test_file("NPWMRX/NPWMRX_0.txt"))
    prod.sql(dbcursor)
    prod = vtecparser(get_test_file("NPWMRX/NPWMRX_1.txt"))
    prod.sql(dbcursor)
    assert any("CON create" in x for x in prod.warnings)
    dbcursor.execute(
        "select ugc from warnings_2025 where wfo = 'MRX' and phenomena = 'HT' "
        "and significance = 'Y' and eventid = 1 and ugc in "
        "('TNZ081', 'TNZ082', 'TNZ098')"
    )
    assert dbcursor.rowcount == 3


@pytest.mark.parametrize("database", ["postgis"])
def test_gh925_wcn_pds(dbcursor):
    """Test that the cross check gets this as a PDS."""
    # Insert the watch
    prod = wwp_parser(get_test_file("WWP/WWP9_PDS.txt"))
    prod.sql(dbcursor)
    # Ingest the WCN
    prod = vtecparser(get_test_file("WCN/WCNMPX.txt"))
    prod.sql(dbcursor)
    assert prod.segments[0].is_pds


@pytest.mark.parametrize("database", ["postgis"])
def test_gh899_cor_emergency(dbcursor):
    """Test that we can handle a COR product that is an emergency."""
    for i in range(4):
        prod = vtecparser(get_test_file(f"TOROAX/{i}.txt"))
        prod.sql(dbcursor)
    dbcursor.execute(
        "select is_emergency from warnings where vtec_year = 2024 and "
        "wfo = 'OAX' and eventid = 38 and phenomena = 'TO' and "
        "significance = 'W' and ugc = 'IAC155'"
    )
    assert dbcursor.fetchone()["is_emergency"]


@pytest.mark.parametrize("database", ["postgis"])
def test_240428_too_long_fcster(dbcursor):
    """Test handling a too long signature"""
    prod = vtecparser(get_test_file("WSW/WSWDLH.txt"))
    prod.sql(dbcursor)


@pytest.mark.parametrize("database", ["postgis"])
def test_gh888_dont_store_can(dbcursor):
    """Test that CAN polygons are not stored in case of two segment."""
    for i in range(3):
        prod = vtecparser(get_test_file(f"SVRMEG/SVRMEG_{i}.txt"))
        prod.sql(dbcursor)
        dbcursor.execute(
            "select count(*) from sbw where vtec_year = 2024 and wfo = 'MEG' "
            "and eventid = 53 and phenomena = 'SV' and significance = 'W' and "
            "product_id = %s",
            (prod.get_product_id(),),
        )
        # the test here is for i=1, which has a CAN/CON combo, only want 1
        assert dbcursor.fetchone()["count"] == 1


@pytest.mark.parametrize("database", ["postgis"])
def test_gh862_longfuse_polygons(dbcursor):
    """Test that we more sensibly handle polygon times."""
    prod = vtecparser(get_test_file("FLWMEG/FLWMEG.txt"))
    prod.sql(dbcursor)
    prod = vtecparser(get_test_file("FLWMEG/FLSMEG_0.txt"))
    prod.sql(dbcursor)
    dbcursor.execute(
        "select issue, polygon_begin, product_signature from sbw "
        "where vtec_year = 2024 and wfo = 'MEG' and "
        "eventid = 12 and phenomena = 'FL' and significance = 'W' and "
        "product_id = %s",
        (prod.get_product_id(),),
    )
    row = dbcursor.fetchone()
    assert row["polygon_begin"] == utc(2024, 2, 11, 12, 36)
    assert row["product_signature"] == "ARS"
    prod = vtecparser(get_test_file("FLWMEG/FLSMEG_1.txt"))
    prod.sql(dbcursor)
    dbcursor.execute(
        "select issue, polygon_begin from sbw "
        "where vtec_year = 2024 and wfo = 'MEG' and "
        "eventid = 12 and phenomena = 'FL' and significance = 'W' and "
        "product_id = %s",
        (prod.get_product_id(),),
    )
    row = dbcursor.fetchone()
    assert row["issue"] == utc(2024, 2, 12, 1, 20)


@pytest.mark.parametrize("database", ["postgis"])
def test_FLScrosses(dbcursor):
    """Test theoretical overlap of FLS over the new year."""
    # 2015
    prod = vtecparser(get_test_file("FLScrosses/FLW_0.txt"))
    prod.sql(dbcursor)
    # 2016
    prod = vtecparser(get_test_file("FLScrosses/FLW_1.txt"))
    prod.sql(dbcursor)
    # updates the 2015 one, but ambiguous
    prod = vtecparser(get_test_file("FLScrosses/FLS_0.txt"))
    prod.sql(dbcursor)
    assert prod.segments[0].vtec[0].year == 2015


def test_230717_ffw_emergency():
    """Test that this series does not generate an emergency."""
    for i in range(1, 7):
        prod = vtecparser(get_test_file(f"FFWOKX/{i}.txt"))
        if i in [4, 5]:
            assert prod.warnings
        assert not prod.segments[0].is_emergency


def test_230628_ibwthunderstorm():
    """Test the tags created with this SVR."""
    data = get_test_file("SVR/SVRPSR_IBW1.txt")
    prod = vtecparser(data.replace("CONSIDERABLE", "DESTRUCTIVE"))
    j = prod.get_jabbers("")
    assert j[0][2]["channels"].find("SV.W.DESTRUCTIVE") > -1


@pytest.mark.parametrize("database", ["postgis"])
def test_230418_index_error(dbcursor):
    """Test this product for not generating an index error."""
    prod = vtecparser(get_test_file("FLS/FLSTFX_indexerror.txt"))
    prod.sql(dbcursor)


def test_230217_tore_false_positive():
    """Test that this event is not an emergency."""
    prod = vtecparser(get_test_file("TORE/TORHGX_false_positive.txt"))
    assert not prod.segments[0].is_emergency


@pytest.mark.parametrize("database", ["postgis"])
def test_flwmtr_dueling_etns(dbcursor):
    """Test that we can properly juggle dueling ETNs over 1 Jan."""
    # 4. New FA.W issued for 2023
    # 5. Is a CON for the 2022 event and where the bug is...
    for i in range(9):
        prod = vtecparser(get_test_file(f"FLWMTR/FLWMTR_{i}.txt"))
        prod.sql(dbcursor)
        assert not filter_warnings(prod.warnings)


@pytest.mark.parametrize("database", ["postgis"])
def test_gh676_emergency(dbcursor):
    """Test that the database flags this as an emergency."""
    for i in range(2):
        prod = vtecparser(get_test_file(f"FFW/FFWFFC_{i}.txt"))
        prod.sql(dbcursor)
    dbcursor.execute(
        "SELECT is_emergency from warnings where vtec_year = 2022 and "
        "wfo = 'FFC' and "
        "phenomena = 'FF' and significance = 'W' and eventid = 32"
    )
    assert dbcursor.fetchone()["is_emergency"]


def test_gh660_no_polygon_warnings():
    """Test that warnings are emitted for a product without a polygon."""
    text = get_test_file("SQW/SQWBTV.txt").replace("LAT...LON", "")
    prod = vtecparser(text)
    ans = "Segment 1 missing required polygon for VTEC: SQ.W"
    assert ans in prod.warnings


def test_gh493_sqwtags():
    """Test the processing of snow squall warning tags!"""
    prod = vtecparser(get_test_file("SQW/SQWBTV.txt"))
    j = prod.get_jabbers("")
    ans = (
        "BTV issues Snow Squall Warning [snow squall: RADAR INDICATED] for "
        "((VTC021)), ((VTC027)) [VT] till 6:30 PM EST "
        "2022-O-NEW-KBTV-SQ-W-0016_2022-02-27T22:44Z"
    )
    assert j[0][2]["twitter"] == ans


@pytest.mark.parametrize("database", ["postgis"])
def test_gh493_sqwtags_db(dbcursor):
    """Test the processing of snow squall warning tags!"""
    prod = vtecparser(get_test_file("SQW/SQWDVN.txt"))
    prod.sql(dbcursor)
    dbcursor.execute(
        "SELECT damagetag, squalltag from sbw where vtec_year = 2022 and "
        "wfo = 'DVN' and "
        "phenomena = 'SQ' and significance = 'W' and eventid = 6 and "
        "status = 'CON'"
    )
    row = dbcursor.fetchone()
    assert row["damagetag"] == "SIGNIFICANT"
    assert row["squalltag"] == "OBSERVED"
    jmsg = prod.get_jabbers("http://localhost")
    assert "impact threat" in jmsg[0][2]["twitter"]


def test_220617_parishes():
    """Test that the word parishes appears as we wish."""
    prov = {
        "LAC005": UGC("LA", "C", "005", name="*" * 300, wfos=["LIX"]),
    }
    prod = _vtecparser(get_test_file("WCN/WCNLIX.txt"), ugc_provider=prov)
    j = prod.get_jabbers("")
    ans = (
        "LIX cancels Severe Thunderstorm Watch (9 parishes in [LA])  "
        "2022-O-CAN-KLIX-SV-A-0344_2022-06-10T22:46Z"
    )
    assert j[0][2]["twitter"] == ans


@pytest.mark.parametrize("database", ["postgis"])
def test_220608_bad_tweet(dbcursor):
    """Test what is emitted from a shortened tweet message."""
    prod = vtecparser(get_test_file("WCN/WCNTSA.txt"))
    prod.sql(dbcursor)
    j = prod.get_jabbers("")
    ans = (
        "TSA updates Severe Thunderstorm Watch (expands area to include 9 "
        "counties, continues 8 counties) till Jun 8, 5:00 PM CDT "
        "2022-O-EXA-KTSA-SV-A-0332_2022-06-08T16:59Z"
    )
    assert j[0][2]["twitter"] == ans


def test_220605_bad_tweet():
    """Test that a multi-segment cancels does not make lots of messages."""
    prod = vtecparser(get_test_file("TCV/TCVMLB.txt"))
    j = prod.get_jabbers("")
    ans = (
        "MLB cancels Tropical Storm Warning (((FLZ154)), ((FLZ159)), "
        "((FLZ164)), ((FLZ247)), ((FLZ254)), ((FLZ259)), ((FLZ264)), "
        "((FLZ347)), ((FLZ447)), ((FLZ547)), ((FLZ647)), ((FLZ747)) [FL])  "
        "2022-O-CAN-KMLB-TR-W-1001_2022-06-04T20:44Z"
    )
    assert j[0][2]["twitter"] == ans


def test_gh540_duplicated_ugcs():
    """Test that we get a warning from a duplicated UGCs."""
    data = get_test_file("NPW/NPWFFC.txt").replace("GAZ001>003", "GAZ004")
    prod = vtecparser(data)
    assert any(a.startswith("Duplicated UGCs") for a in prod.warnings)


@pytest.mark.parametrize("database", ["postgis"])
def test_gh533_dualing_events(dbcursor):
    """Test redundant ETNs that crossed the new years."""
    for i in range(0, 3):
        data = get_test_file(f"NPWLCH/{i:02d}.txt")
        prod = vtecparser(data)
        prod.sql(dbcursor)
        assert not filter_warnings(prod.warnings)


@pytest.mark.parametrize("database", ["postgis"])
def test_211115_bullets(dbcursor):
    """Test that we can get the bullets for riverpro."""
    data = get_test_file("FLS/FLSSEW_bullets.txt")
    prod = vtecparser(data)
    prod.sql(dbcursor)
    assert prod.segments[0].bullets


def test_issue491_false_emergency_positive():
    """Test that this product is not flagged as an emergency."""
    data = get_test_file("SVSFFC.txt")
    prod = vtecparser(data)
    assert not prod.segments[0].is_emergency


def test_issue461_firewx_ugcs():
    """Test that we can do the right thing with Fire Weather UGCS."""
    ugc_provider = UGCProvider(
        {
            "AZZ101": UGC("AZ", "Z", 101, name="A", wfos=["YYY"]),
            "NVZ461": UGC("NV", "Z", 461, name="A", wfos=["XXX"]),
        }
    )
    ugc_provider.df = pd.concat(
        [
            ugc_provider.df,
            pd.DataFrame(
                [
                    {
                        "ugc": "AZZ101",
                        "wfo": "QQQ",
                        "name": "A",
                        "source": "fz",
                    },
                    {
                        "ugc": "NVZ466",
                        "wfo": "AAA",
                        "name": "A",
                        "source": "fz",
                    },
                    {
                        "ugc": "NVZ466",
                        "wfo": "AAA",
                        "name": "A",
                        "source": "fz",
                    },
                ]
            ),
        ],
        ignore_index=True,
    )
    prod = _vtecparser(
        get_test_file("RFWVEF/RFW_00.txt"),
        ugc_provider=ugc_provider,
    )
    wfos = prod.get_affected_wfos()
    assert "XXX" in wfos
    assert "YYY" not in wfos
    assert "QQQ" in wfos
    assert ugc_provider["AZZ101"].wfos
    assert ugc_provider.get("NVZ466").name == "((NVZ466))"


@pytest.mark.parametrize("database", ["postgis"])
def test_invalidpolygon(dbcursor):
    """Test that some graceful handling of a bad polygon can happen."""
    data = get_test_file("FLS/FLSSJU_twopoint.txt")
    prod = vtecparser(data)
    prod.sql(dbcursor)
    assert any(x.startswith("Less than three ") for x in prod.warnings)


@pytest.mark.parametrize("database", ["postgis"])
def test_issue253_ibwthunderstorm(dbcursor):
    """Test the processing of IBW Thunderstorm Damage Threat."""
    data = get_test_file("SVR/SVRPSR_IBW1.txt")
    prod = vtecparser(data)
    prod.sql(dbcursor)
    dbcursor.execute(
        "select damagetag from sbw where vtec_year = 2020 and wfo = 'PSR' "
        "and eventid = 43 and phenomena = 'SV' and significance = 'W' "
    )
    assert dbcursor.fetchone()["damagetag"] == "CONSIDERABLE"
    j = prod.get_jabbers("")
    ans = (
        "PSR issues Severe Thunderstorm Warning [tornado: POSSIBLE, "
        "damage threat: CONSIDERABLE, wind: 70 MPH (OBSERVED), "
        "hail: 1.00 IN (RADAR INDICATED)] for "
        "((AZC013)), ((AZC021)) [AZ] till 6:00 PM MST "
        "2020-O-NEW-KPSR-SV-W-0043_2020-09-09T00:29Z"
    )
    assert j[0][0] == ans


def test_210304_notimezone():
    """Test that we not care that this product has no local timezone."""
    data = get_test_file("TSU/TSUPAC.txt")
    prod = vtecparser(data)
    assert not prod.warnings
    assert prod.valid == utc(2021, 3, 4, 18, 58)
    prod = vtecparser(data.replace("1858", "0048"))
    assert not prod.warnings
    assert prod.valid == utc(2021, 3, 4, 0, 48)


@pytest.mark.parametrize("database", ["postgis"])
def test_210302_multipolygon(dbcursor):
    """Test that buffer(0) producing a multipolygon is handled."""
    prod = vtecparser(get_test_file("FLW/FLWJKL_multipolygon.txt"))
    prod.sql(dbcursor)
    assert any("buffer" in x for x in prod.warnings)


@pytest.mark.parametrize("database", ["postgis"])
def test_210103_vtec_cor(dbcursor):
    """Test that VTEC COR actions do not get their status stored."""
    prod = vtecparser(get_test_file("NPWGID/00.txt"))
    prod.sql(dbcursor)
    # CAN 4 ugcs
    prod = vtecparser(get_test_file("NPWGID/01.txt"))
    prod.sql(dbcursor)
    # CORrected the product, ensure those four ugcs are still cancelled
    prod = vtecparser(get_test_file("NPWGID/02.txt"))
    prod.sql(dbcursor)
    dbcursor.execute(
        "SELECT ugc from warnings where vtec_year = 2021 and wfo = 'GID' and "
        "eventid = 2 and "
        "phenomena = 'FG' and significance = 'Y' and status = 'CAN'"
    )
    assert dbcursor.rowcount == 4
    # CAN the rest, make sure we have no warnings
    prod = vtecparser(get_test_file("NPWGID/02.txt"))
    prod.sql(dbcursor)
    assert not filter_warnings(prod.warnings)


@pytest.mark.parametrize("database", ["postgis"])
def test_201120_tml_line(dbcursor):
    """Test that we can insert TML lines."""
    data = get_test_file("TORFSD.txt")
    prod = vtecparser(data.replace("4260 9567", "4260 9567 4160 8567"))
    prod.sql(dbcursor)
    assert prod.get_signature() == "JEFF CHAPMAN & ./Test"


@pytest.mark.parametrize("database", ["postgis"])
def test_201120_sbw_duplicate(dbcursor):
    """Test that we get an error for a SBW duplicated."""
    data = get_test_file("TOR.txt")
    prod = vtecparser(data)
    prod.sql(dbcursor)
    prod.sql(dbcursor)
    assert any(x.find("is a SBW duplicate") > -1 for x in prod.warnings)
    prod = vtecparser(data.replace(".NEW.", ".CON."))
    prod.sql(dbcursor)
    assert any(x.find("SBW prev polygon") > -1 for x in prod.warnings)


@pytest.mark.parametrize("database", ["postgis"])
def test_201120_correction(dbcursor):
    """Test that we emit a warning for first found correction."""
    data = get_test_file("TOR.txt").replace("291656", "291656 CCA")
    prod = vtecparser(data)
    prod.sql(dbcursor)
    assert any(x.find("is a correction") > -1 for x in prod.warnings)


@pytest.mark.parametrize("database", ["postgis"])
def test_201120_unknown_vtec(dbcursor):
    """Test that we emit a warning when finding an unknown VTEC action."""
    data = get_test_file("TOR.txt").replace(".NEW.KJAN", ".QQQ.KJAN")
    prod = vtecparser(data)
    prod.sql(dbcursor)
    assert any(x.find("QQQ") > -1 for x in prod.warnings)


@pytest.mark.parametrize("database", ["postgis"])
def test_201120_resent(dbcursor):
    """Test that we can handle a resent product."""
    data = get_test_file("TOR.txt")
    eas = "EAS ACTIVATION REQUESTED"
    data2 = data.replace(eas, f"{eas}...RESENT")
    # trigger a false initially
    prod = vtecparser(data2)
    prod.sql(dbcursor)
    prod = vtecparser(data)
    prod.sql(dbcursor)
    prod = vtecparser(data2)
    prod.sql(dbcursor)


@pytest.mark.parametrize("database", ["postgis"])
def test_201120_missing_ugc(dbcursor):
    """Test that a warning for missing ugc is emitted."""
    data = get_test_file("CFW/CFWSJU.txt")
    data = data.replace("PRZ001-002-005-008-211645-", "")
    prod = vtecparser(data)
    prod.sql(dbcursor)
    ans = "UGC is missing for segment that has VTEC!"
    assert ans in prod.warnings


@pytest.mark.parametrize("database", ["postgis"])
def test_201120_dup(dbcursor):
    """Test that a warning for duplicated VTEC is emitted."""
    prod = vtecparser(get_test_file("CFW/CFWSJU.txt"))
    prod.sql(dbcursor)
    ans = "Segment has duplicated VTEC"
    assert any(x.startswith(ans) for x in prod.warnings)


def test_201116_1970vtec():
    """Test that we don't allow a 1970s VTEC timestamp, which is in error."""
    prod = vtecparser(get_test_file("FLS/FLSSEW_vtec1970.txt"))
    assert prod.segments[0].vtec[0].begints is None


@pytest.mark.parametrize("database", ["postgis"])
def test_issue284_incomplete_update(dbcursor):
    """Test that we emit warnings when a product fails to update everything."""
    prod = vtecparser(get_test_file("FFW/FFWLCH_0.txt"))
    prod.sql(dbcursor)
    assert not filter_warnings(prod.warnings)
    prod = vtecparser(get_test_file("FFW/FFSLCH_1.txt"))
    prod.sql(dbcursor)
    warnings = filter_warnings(prod.warnings)
    assert len(warnings) == 1
    assert warnings[0].startswith(CUGC)


def test_201116_timezone():
    """Test what happens with some timezone fun."""
    valid = utc(2020, 9, 9, 0, 29)
    prod = vtecparser(get_test_file("SVR/SVRPSR.txt"), utcnow=valid)
    ans = "valid at 5:29 PM MST"
    assert prod.segments[0].vtec[0].get_begin_string(prod) == ans


def test_vtec_begin_time_format():
    """Test that we can call vtec begin_time."""
    valid = utc(2010, 4, 5, 21, 47)
    prod = vtecparser(get_test_file("SVRLMK.txt"), utcnow=valid)
    ans = "valid at 5:47 PM EDT"
    assert prod.segments[0].vtec[0].get_begin_string(prod) == ans


def test_old_windhail_tag():
    """Test that we can parse legacy wind...hail tags."""
    valid = utc(2010, 4, 5, 21, 47)
    prod = vtecparser(get_test_file("SVRLMK.txt"), utcnow=valid)
    assert prod.segments[0].hailtag == "1.00"
    # manually edited the polygon to make it invalid
    assert filter_warnings(prod.warnings)[0].startswith("process_time_mot_loc")
    # manually edited TIME...MOT...LOC to make it invalid
    assert filter_warnings(prod.warnings)[1].startswith("LAT...LON")


def test_dups():
    """We had a false positive :("""
    segment = FakeObject()
    segment.tp = FakeObject()
    segment.tp.valid = datetime.datetime(2017, 5, 24, 12, 0)
    segment.vtec = parse(
        (
            "/O.UPG.KTWC.FW.A.0008.170525T1800Z-170526T0300Z/\n"
            "/O.NEW.KTWC.FW.W.0013.170525T1800Z-170526T0300Z/\n"
            "/O.UPG.KTWC.FW.A.0009.170526T1700Z-170527T0300Z/\n"
            "/O.NEW.KTWC.FW.W.0014.170526T1700Z-170527T0300Z/\n"
        )
    )
    res = check_dup_ps(segment)
    assert not res


def test_200719_nomnd():
    """Test that we can handle a product without a MND header."""
    utcnow = utc(2020, 7, 18, 18, 51)
    prod = vtecparser(get_test_file("FLSBRO_nomnd.txt"), utcnow=utcnow)
    assert "Could not find local timezone in text." in prod.warnings
    j = prod.get_jabbers("http://localhost")
    ans = (
        "BRO issues Flood Advisory for ((TXC261)), ((TXC489)) [TX] till "
        "Jul 18, 20:45 UTC "
        "http://localhost2020-O-NEW-KBRO-FA-Y-0074_2020-07-18T18:51Z"
    )
    assert j[0][0] == ans


@pytest.mark.parametrize("database", ["postgis"])
def test_200306_issue210(dbcursor):
    """Test our logic for figuring out which table has our event."""
    nwsli_provider = {
        "JAMS1": NWSLI("JAMS1", "Ames", ["XXX"], -99, 44),
        "CNOG1": NWSLI("CNOG1", "Ames", ["XXX"], -99, 44),
    }
    for i in range(7):
        prod = vtecparser(
            get_test_file(f"FLWCHS/2019_{i}.txt"),
            nwsli_provider=nwsli_provider,
        )
        prod.sql(dbcursor)
        assert not filter_warnings(prod.warnings)
    for i in range(2):
        prod = vtecparser(
            get_test_file(f"FLWCHS/2020_{i}.txt"),
            nwsli_provider=nwsli_provider,
        )
        prod.sql(dbcursor)
        assert not filter_warnings(prod.warnings)


@pytest.mark.parametrize("database", ["postgis"])
def test_200302_issue203(dbcursor):
    """Test that we warn when a polygon goes missing."""
    for i in range(2):
        prod = vtecparser(get_test_file(f"FLWCAE/{i}.txt"))
        prod.sql(dbcursor)
        if i == 0:
            assert prod.segments[0].sbw
            continue
        assert prod.warnings[1].find("should have contained") > -1
        assert prod.segments[0].sbw is None
        assert prod.segments[0].is_pds is False
        assert len(prod.warnings) == 3
        dbcursor.execute(
            """
            SELECT status from sbw WHERE vtec_year = 2020 and wfo = 'CAE' and
            eventid = 24 and phenomena = 'FL' and significance = 'W'
            and status = 'CAN'
        """
        )
        assert dbcursor.rowcount == 1


def test_200224_urls():
    """Test that we are generating the right URLs."""
    ans = "2020-02-25T06:00Z"
    for i in range(3):
        prod = vtecparser(get_test_file(f"WSWDVN/{i}.txt"))
        j = prod.get_jabbers("http://localhost")
        url = j[0][0].strip().split()[-1].split("_")[1]
        assert url == ans


@pytest.mark.parametrize("database", ["postgis"])
def test_issue120_ffwtags(dbcursor):
    """Can we support Flood Warning tags."""
    prod = vtecparser(get_test_file("FFW/FFW_tags.txt"))
    assert "DAM FAILURE" in prod.segments[0].flood_tags
    j = prod.get_jabbers("http://localhost")
    ans = (
        "GUM issues Flash Flood Emergency [flash flood: observed, "
        "flash flood damage threat: catastrophic, dam failure: imminent, "
        "expected rainfall: 2-3 inches in 60 minutes] "
        "for ((GUC100)), ((GUC110)), ((GUC120)) [GU] till Oct 25, 9:15 AM "
        "CHST * At 612 AM ChST, satellite estimates indicated heavy rain "
        "across the warned area. Up to three inches of rain have already "
        "fallen. Flash flooding is expected to begin shortly. "
        "http://localhost2018-O-NEW-PGUM-FF-W-0014_2018-10-24T20:23Z"
    )
    assert j[0][0] == ans
    prod.sql(dbcursor)
    dbcursor.execute(
        "SELECT * from sbw WHERE vtec_year = 2018 and wfo = 'GUM' and "
        "eventid = 14 and "
        "phenomena = 'FF' and significance = 'W'"
    )
    row = dbcursor.fetchone()
    assert row["floodtag_damage"] == "CATASTROPHIC"
    assert row["floodtag_flashflood"] == "OBSERVED"
    assert row["floodtag_dam"] == "IMMINENT"
    assert row["floodtag_heavyrain"] == "2-3 INCHES IN 60 MINUTES"
    assert row["floodtag_leeve"] is None


@pytest.mark.parametrize("database", ["postgis"])
def test_TORE_series(dbcursor):
    """Can we process a Tornado Emergency that came with SVS update."""

    def getval():
        dbcursor.execute(
            """
            SELECT is_emergency from warnings WHERE vtec_year = 2018 and
            wfo = 'DMX' and eventid = 43 and phenomena = 'TO' and
            significance = 'W' and ugc = 'IAC127'
        """
        )
        return dbcursor.fetchone()["is_emergency"]

    def getval2():
        dbcursor.execute(
            """
            SELECT is_emergency from sbw WHERE vtec_year = 2018 and
            wfo = 'DMX' and eventid = 43 and phenomena = 'TO' and
            significance = 'W' and status != 'CAN' ORDER by updated DESC
        """
        )
        return dbcursor.fetchone()["is_emergency"]

    def getval3():
        dbcursor.execute(
            """
            select is_emergency from sbw where vtec_year = 2018 and
            wfo = 'DMX' and eventid = 43 and phenomena = 'TO' and
            significance = 'W'
        """
        )
        return dbcursor.rowcount

    prod = vtecparser(get_test_file("TORE/TOR.txt"))
    prod.sql(dbcursor)
    assert getval3() == 1
    jmsg = prod.get_jabbers("http://localhost")
    assert "TO.EMERGENCY" not in jmsg[0][2]["channels"].split(",")
    assert getval() is False
    assert getval2() is False

    prod = vtecparser(get_test_file("TORE/SVS_E.txt"))
    prod.sql(dbcursor)
    assert getval3() == 2
    assert not prod.warnings
    jmsg = prod.get_jabbers("http://localhost")
    assert "TO.EMERGENCY" in jmsg[0][2]["channels"].split(",")
    assert getval()
    assert getval2()

    # no longer an emergency, but we don't want database to update
    prod = vtecparser(get_test_file("TORE/SVS_F.txt"))
    prod.sql(dbcursor)
    assert getval()
    assert getval2() is False


@pytest.mark.parametrize("database", ["postgis"])
def test_181228_issue76_sbwtable(dbcursor):
    """Can we locate the current SBW table with polys in the future."""
    prod = vtecparser(get_test_file("FLWMOB/FLW.txt"))
    prod.sql(dbcursor)
    assert "HVTEC NWSLI MRRM6 is unknown." in prod.warnings
    prod = vtecparser(
        get_test_file("FLWMOB/FLS.txt"),
        nwsli_provider={"MRRM6": NWSLI("MRRM6", "Ames", ["XXX"], -99, 44)},
    )
    prod.sql(dbcursor)
    dbcursor.execute(
        "SELECT * from sbw where vtec_year = 2018 and wfo = 'MOB' and "
        "eventid = 57 "
        "and phenomena = 'FL' and significance = 'W' and status = 'NEW'"
    )
    row = dbcursor.fetchone()
    assert row["hvtec_nwsli"] == "MRRM6"
    assert row["hvtec_severity"] == "1"
    assert row["hvtec_cause"] == "ER"
    assert row["hvtec_record"] == "NO"
    assert not filter_warnings(prod.warnings)


@pytest.mark.parametrize("database", ["postgis"])
def test_180411_can_expiration(dbcursor):
    """Do we properly update the expiration time of a CAN event"""
    utcnow = utc(2018, 1, 22, 2, 6)
    prod = vtecparser(get_test_file("vtec/TORFWD_0.txt"), utcnow=utcnow)
    prod.sql(dbcursor)
    # This should be the expiration time as well
    utcnow = utc(2018, 1, 22, 2, 30)
    prod = vtecparser(get_test_file("vtec/TORFWD_1.txt"), utcnow=utcnow)
    prod.sql(dbcursor)
    for status in ["NEW", "CAN"]:
        dbcursor.execute(
            """
            SELECT expire from sbw where vtec_year = 2018 and wfo = 'FWD' and
            phenomena = 'TO' and significance = 'W' and eventid = 6
            and status = %s
        """,
            (status,),
        )
        row = dbcursor.fetchone()
        assert row["expire"] == utcnow


@pytest.mark.parametrize("database", ["postgis"])
def test_issue9(dbcursor):
    """A product crossing year bondary"""
    utcnow = utc(2017, 12, 31, 9, 24)
    prod = vtecparser(get_test_file("vtec/crosses_0.txt"), utcnow=utcnow)
    prod.sql(dbcursor)
    utcnow = utc(2018, 1, 1, 16, 0)
    prod = vtecparser(get_test_file("vtec/crosses_1.txt"), utcnow=utcnow)
    prod.sql(dbcursor)
    warnings = filter_warnings(prod.warnings)
    # We used to emit a warning for this, but not any more
    assert not warnings
    utcnow = utc(2018, 1, 1, 21, 33)
    prod = vtecparser(get_test_file("vtec/crosses_2.txt"), utcnow=utcnow)
    prod.sql(dbcursor)
    warnings = filter_warnings(prod.warnings)
    assert not warnings


@pytest.mark.parametrize("database", ["postgis"])
def test_180202_issue54(dbcursor):
    """Are we doing the right thing with VTEC EXP actions?"""

    def get_expire(colname):
        """get expiration"""
        dbcursor.execute(
            f"SELECT distinct {colname} from warnings WHERE vtec_year = 2018 "
            "and wfo = 'LWX' "
            "and eventid = 6 and phenomena = 'WW' and significance = 'Y'"
        )
        assert dbcursor.rowcount == 1
        return dbcursor.fetchone()[colname]

    expirets = utc(2018, 2, 2, 9)
    for i in range(3):
        prod = vtecparser(get_test_file(f"vtec/WSWLWX_{i}.txt"))
        prod.sql(dbcursor)
        warnings = filter_warnings(prod.warnings)
        assert not warnings
        assert get_expire("expire") == expirets
        assert get_expire("updated") == prod.valid


@pytest.mark.parametrize("database", ["postgis"])
def test_171121_issue45(dbcursor):
    """Do we alert on duplicated ETNs?"""
    utcnow = utc(2017, 4, 20, 21, 33)
    prod = vtecparser(get_test_file("vtec/NPWDMX_0.txt"), utcnow=utcnow)
    prod.sql(dbcursor)
    utcnow = utc(2017, 11, 20, 21, 33)
    prod = vtecparser(get_test_file("vtec/NPWDMX_1.txt"), utcnow=utcnow)
    prod.sql(dbcursor)
    warnings = filter_warnings(prod.warnings)
    assert len(warnings) == 1


@pytest.mark.parametrize("database", ["postgis"])
def test_170823_tilde(dbcursor):
    """Can we parse a product that has a non-ascii char in it"""
    prod = vtecparser(get_test_file("FFWTWC_tilde.txt"))
    assert prod.z == "MST"
    j = prod.get_jabbers("http://localhost/")
    prod.sql(dbcursor)
    ans = (
        "TWC issues Flash Flood Warning for "
        "((AZC021)) [AZ] till Aug 23, 6:30 PM MST "
        "http://localhost/2017-O-NEW-KTWC-FF-W-0067_2017-08-23T23:34Z"
    )
    assert j[0][0] == ans


def test_170822_duststormwarning():
    """Can we parse the new Dust Storm Warning?"""
    prod = vtecparser(get_test_file("DSW.txt"))
    assert prod.z == "MST"
    j = prod.get_jabbers("http://localhost/")
    ans = (
        "PSR issues Dust Storm Warning for ((AZC021)) "
        "[AZ] till 11:15 AM MST "
        "http://localhost/2016-O-NEW-KPSR-DS-W-0001_2016-11-30T17:49Z"
    )
    assert j[0][0] == ans


def test_170718_wrongtz():
    """Product from TWC has the wrong time zone denoted in the text"""
    prod = vtecparser(get_test_file("FLSTWC.txt"))
    assert prod.z == "MST"
    j = prod.get_jabbers("http://localhost/")
    assert "FA.Y.AZ" in j[0][2]["channels"].split(",")
    ans = (
        "TWC issues Flood Advisory for ((AZC009)) "
        "[AZ] till Jul 18, 3:30 PM MST "
        "http://localhost/2017-O-NEW-KTWC-FA-Y-0034_2017-07-18T19:38Z"
    )
    assert j[0][0] == ans


@pytest.mark.parametrize("database", ["postgis"])
def test_170523_dupfail(dbcursor):
    """The dup check failed with an exception"""
    prod = vtecparser(get_test_file("MWWLWX_dups.txt"))
    prod.sql(dbcursor)


@pytest.mark.parametrize("database", ["postgis"])
def test_170504_falsepositive(dbcursor):
    """This alert for overlapping VTEC is a false positive"""
    prod = vtecparser(get_test_file("NPW/NPWFFC.txt"))
    prod.sql(dbcursor)
    res = [x.find("duplicated VTEC") > 0 for x in prod.warnings]
    assert not any(res)


@pytest.mark.parametrize("database", ["postgis"])
def test_170502_novtec(dbcursor):
    """MWS is a product that does not require VTEC, so no warnings"""
    prod = vtecparser(get_test_file("MWSMFL.txt"))
    prod.sql(dbcursor)
    assert not prod.warnings


@pytest.mark.parametrize("database", ["postgis"])
def test_170411_suspect_vtec(dbcursor):
    """MWWSJU contains VTEC that NWS HQ says should not be possible"""
    prod = vtecparser(get_test_file("MWWLWX_twovtec.txt"))
    prod.sql(dbcursor)
    a = [x.find("duplicated VTEC") > 0 for x in prod.warnings]
    assert not any(a)


@pytest.mark.parametrize("database", ["postgis"])
def test_170411_baddelim(dbcursor):
    """FLSGRB contains an incorrect sequence of $$ and &&"""
    prod = vtecparser(get_test_file("FLSGRB.txt"))
    prod.sql(dbcursor)
    assert len(prod.warnings) >= 1


@pytest.mark.parametrize("database", ["postgis"])
def test_170403_mixedlatlon(dbcursor):
    """Check our parsing of mixed case Lat...Lon"""
    prod = vtecparser(get_test_file("mIxEd_CaSe/FLWLCH.txt"))
    prod.sql(dbcursor)
    ans = (
        "SRID=4326;MULTIPOLYGON (((-93.29 30.30, -93.14 30.38, "
        "-93.03 30.31, -93.08 30.25, -93.21 30.19, -93.29 30.30)))"
    )
    assert prod.segments[0].giswkt == ans
    dbcursor.execute("SELECT impact_text from riverpro where nwsli = 'OTBL1'")
    assert dbcursor.rowcount == 1
    row = dbcursor.fetchone()
    ans = (
        "At stages near 4.0 feet..."
        "Minor flooding of Goos Ferry Road will occur."
    )
    assert row["impact_text"] == ans


@pytest.mark.parametrize("database", ["postgis"])
def test_170324_waterspout(dbcursor):
    """Do we parse Waterspout tags!"""
    utcnow = utc(2017, 3, 24, 1, 37)
    prod = vtecparser(get_test_file("SMWMFL.txt"), utcnow=utcnow)
    j = prod.get_jabbers("http://localhost")
    ans = (
        "MFL issues Marine Warning [waterspout: POSSIBLE, "
        "wind: &gt;34 KTS, hail: 0.00 IN] for "
        "((AMZ630)), ((AMZ651)) [AM] till 10:15 PM EDT "
        "http://localhost2017-O-NEW-KMFL-MA-W-0059_2017-03-24T01:37Z"
    )
    assert j[0][0] == ans
    prod.sql(dbcursor)
    dbcursor.execute(
        """SELECT * from sbw where vtec_year = 2017 and wfo = 'MFL' and
    phenomena = 'MA' and significance = 'W' and eventid = 59
    and status = 'NEW' and waterspouttag = 'POSSIBLE'
    """
    )
    assert dbcursor.rowcount == 1


def test_170303_ccwpoly():
    """Test that CCW polygon does not trip us up."""
    prod = vtecparser(get_test_file("FLWHGX_ccw.txt"))
    assert not filter_warnings(filter_warnings(prod.warnings), "HVTEC")


@pytest.mark.parametrize("database", ["postgis"])
def test_170115_table_failure(dbcursor):
    """Test WSW series for issues"""
    for i in range(12):
        prod = vtecparser(get_test_file(f"WSWAMA/WSWAMA_{i:02d}.txt"))
        prod.sql(dbcursor)
        assert not filter_warnings(prod.warnings)


@pytest.mark.parametrize("database", ["postgis"])
def test_160912_missing(dbcursor):
    """see why this series failed in production"""
    for i in range(4):
        prod = vtecparser(get_test_file(f"RFWVEF/RFW_{i:02d}.txt"))
        prod.sql(dbcursor)
        warnings = filter_warnings(prod.warnings)
        assert not warnings


def test_gh614_npwdmx():
    """Test that we don't get confusing messages for timing."""
    prod = vtecparser(get_test_file("NPW/NPWDMX.txt"))
    j = prod.get_jabbers("")
    ans = (
        "DMX continues Heat Advisory (51 forecast zones in [IA])  "
        "2022-O-CON-KDMX-HT-Y-0001_2022-06-14T16:00Z"
    )
    assert len(j) == 1
    assert j[0][2]["twitter"] == ans


def test_gh614_messages():
    """Test the jabber messages generated from this many segment prod."""
    prod = vtecparser(get_test_file("TCV/TCVAKQ.txt"))
    j = prod.get_jabbers("")
    ans = (
        "AKQ updates Tropical Storm Warning (36 zones)  "
        "2016-O-NEW-KAKQ-TR-W-1009_2016-09-02T15:55Z"
    )
    assert len(j) == 1
    assert j[0][2]["twitter"] == ans


def test_160904_resent():
    """Is this product a correction?"""
    prod = vtecparser(get_test_file("TCV/TCVAKQ.txt"))
    assert prod.is_correction()


@pytest.mark.parametrize("database", ["postgis"])
def test_160720_unknown_ugc(dbcursor):
    """Unknown UGC logic failed for some reason"""
    # Note that this example has faked UGCs to test things out
    prod = vtecparser(get_test_file("RFWBOI_fakeugc.txt"))
    prod.sql(dbcursor)
    assert len(prod.warnings) == 2


def test_160623_invalid_tml():
    """See that we emit an error for an invalid TML"""
    prod = vtecparser(get_test_file("MWSKEY.txt"))
    warnings = filter_warnings(prod.warnings)
    assert len(warnings) == 1


def test_160513_windtag():
    """Wind tags can be in knots too!"""
    prod = vtecparser(get_test_file("SMWLWX.txt"))
    assert prod.segments[0].windtag == "34"
    j = prod.get_jabbers("http://localhost", "http://localhost")
    ans = (
        "LWX issues Marine Warning [wind: &gt;34 KTS, "
        "hail: 0.00 IN] for ((ANZ537)) [AN] till "
        "May 13, 5:15 PM EDT "
        "http://localhost2016-O-NEW-KLWX-MA-W-0035_2016-05-13T19:51Z"
    )
    assert j[0][0] == ans


def test_160415_mixedcase():
    """See how bad we break with mixed case"""
    prod = vtecparser(get_test_file("mIxEd_CaSe/FFSGLD.txt"))
    assert prod.tz is not None
    assert prod.segments[0].vtec[0].action == "CON"
    j = prod.get_jabbers("http://localhost", "http://localhost")
    ans = (
        "GLD continues Flash Flood Warning for ((COC017)) "
        "[CO] till Apr 15, 7:00 PM MDT "
        "http://localhost2016-O-CON-KGLD-FF-W-0001_2016-04-15T23:41Z"
    )
    channels = j[0][2]["channels"].split(",")
    assert "FF.W" not in channels
    assert "FF.W-CON" in channels
    assert j[0][0] == ans


@pytest.mark.parametrize("database", ["postgis"])
def test_151225_extfuture(dbcursor):
    """Warning failure jumps states!"""
    # /O.NEW.KPAH.FL.W.0093.151227T0517Z-151228T1727Z/
    prod = vtecparser(get_test_file("FLWPAH/FLWPAH_1.txt"))
    prod.sql(dbcursor)
    dbcursor.execute(
        """
        SELECT ugc, issue, expire from warnings where vtec_year = 2015 and
        wfo = 'PAH'
        and phenomena = 'FL' and eventid = 93 and significance = 'W'
        and status = 'NEW'
    """
    )
    assert dbcursor.rowcount == 2
    # /O.EXT.KPAH.FL.W.0093.151227T0358Z-151229T0442Z/
    prod = vtecparser(get_test_file("FLWPAH/FLWPAH_2.txt"))
    prod.sql(dbcursor)
    warnings = filter_warnings(filter_warnings(prod.warnings), CUGC)
    assert len(warnings) == 2


@pytest.mark.parametrize("database", ["postgis"])
def test_150915_noexpire(dbcursor):
    """Check that we set an expiration for initial infinity SBW geo"""
    prod = vtecparser(get_test_file("FLWGRB.txt"))
    assert prod.segments[0].vtec[0].endts is None
    prod.sql(dbcursor)
    dbcursor.execute(
        """
        SELECT init_expire, expire from sbw where vtec_year = 2015 and
        wfo = 'GRB'
        and phenomena = 'FL' and eventid = 3 and significance = 'W'
        and status = 'NEW'
    """
    )
    row = dbcursor.fetchone()
    assert row["init_expire"] is not None
    assert row["expire"] is not None


@pytest.mark.parametrize("database", ["postgis"])
def test_150820_exb(dbcursor):
    """Found a bug with setting of issuance for EXB case!"""
    for i in range(3):
        prod = vtecparser(get_test_file(f"CFWLWX/{i}.txt"))
        prod.sql(dbcursor)
    # Make sure the issuance time is correct for MDZ014
    dbcursor.execute(
        """SELECT issue at time zone 'UTC' as ii from warnings
    where vtec_year = 2015 and wfo = 'LWX' and eventid = 30
    and phenomena = 'CF' and significance = 'Y'
    and ugc = 'MDZ014'"""
    )
    assert dbcursor.fetchone()["ii"] == datetime.datetime(2015, 8, 11, 13)


@pytest.mark.parametrize("database", ["postgis"])
def test_150814_init_expire(dbcursor):
    """Make sure init_expire is not null"""
    prod = vtecparser(get_test_file("FLWLZK.txt"))
    prod.sql(dbcursor)
    dbcursor.execute(
        """SELECT count(*) from warnings
        where vtec_year = 2015 and wfo = 'LZK' and eventid = 18
        and phenomena = 'FL' and significance = 'W'
        and init_expire is null"""
    )
    assert dbcursor.fetchone()["count"] == 0


def test_150507_notcor():
    """SVROUN is not a product correction!"""
    prod = vtecparser(get_test_file("SVROUN.txt"))
    assert not prod.is_correction()


def test_150429_flswithsign():
    """FLSMKX see that we are okay with the signature"""
    prod = vtecparser(get_test_file("FLSMKX.txt"))
    ans = (
        "SRID=4326;MULTIPOLYGON "
        "(((-88.32 42.62, -88.13 42.62, -88.12 42.52, -88.10 42.45, "
        "-88.27 42.45, -88.25 42.55, -88.32 42.62)))"
    )
    assert prod.segments[0].giswkt == ans


def test_150331_notcorrection():
    """SVRMEG is not a product correction"""
    prod = vtecparser(get_test_file("SVRMEG.txt"))
    assert not prod.is_correction()


def test_150304_testtor():
    """TORILX is a test, we had better handle it!"""
    prod = vtecparser(get_test_file("TORILX.txt"))
    j = prod.get_jabbers("http://localhost", "http://localhost")
    assert not j


@pytest.mark.parametrize("database", ["postgis"])
def test_150203_exp_does_not_end(dbcursor):
    """MWWCAR a VTEC EXP action should not terminate it"""
    for i in range(23):
        prod = vtecparser(get_test_file(f"MWWCAR/{i}.txt"))
        prod.sql(dbcursor)
        warnings = filter_warnings(prod.warnings)
        warnings = filter_warnings(warnings, "VTEC Product appears to c")
        assert not warnings


@pytest.mark.parametrize("database", ["postgis"])
def test_150203_null_issue(dbcursor):
    """WSWOKX had null issue times, bad!"""
    for i in range(18):
        prod = vtecparser(get_test_file(f"WSWOKX/{i}.txt"))
        prod.sql(dbcursor)
        # Make sure there are no null issue times
        dbcursor.execute(
            "SELECT count(*) from warnings where vtec_year = 2015 and "
            "wfo = 'OKX' and "
            "eventid = 6 and phenomena = 'WW' and significance = 'Y' "
            "and issue is null"
        )
        assert dbcursor.fetchone()["count"] == 0


@pytest.mark.parametrize("database", ["postgis"])
def test_150115_correction_sbw(dbcursor):
    """FLWMHX make sure a correction does not result in two polygons"""
    prod = vtecparser(get_test_file("FLWMHX/0.txt"))
    prod.sql(dbcursor)
    warnings = filter_warnings(filter_warnings(prod.warnings), "HVTEC")
    assert not warnings
    prod = vtecparser(get_test_file("FLWMHX/1.txt"))
    prod.sql(dbcursor)
    warnings = filter_warnings(filter_warnings(prod.warnings), "HVTEC")
    assert not warnings


def test_150105_considerable_tag():
    """TORFSD has considerable tag"""
    prod = vtecparser(get_test_file("TORFSD.txt"))
    j = prod.get_jabbers("http://localhost", "http://localhost")
    ans = (
        "FSD issues Tornado Warning (PDS) "
        "[tornado: RADAR INDICATED, damage threat: CONSIDERABLE, "
        "hail: 1.50 IN] for ((IAC035)) [IA] till 8:00 PM CDT * AT 720 "
        "PM CDT...A SEVERE THUNDERSTORM CAPABLE OF PRODUCING A LARGE "
        "AND EXTREMELY DANGEROUS TORNADO WAS LOCATED NEAR WASHTA...AND "
        "MOVING NORTHEAST AT 30 MPH. "
        "http://localhost2013-O-NEW-KFSD-TO-W-0020_2013-10-05T00:22Z"
    )
    assert j[0][0] == ans
    assert prod.segments[0].is_pds


@pytest.mark.parametrize("database", ["postgis"])
def test_150105_sbw(dbcursor):
    """FLSLBF SBW that spans two years!"""
    for i in range(7):
        prod = vtecparser(get_test_file(f"FLSLBF/{i}.txt"))
        prod.sql(dbcursor)
        warnings = filter_warnings(prod.warnings)
        assert not warnings


@pytest.mark.parametrize("database", ["postgis"])
def test_150105_manycors(dbcursor):
    """WSWGRR We had some issues with this series, lets test it"""
    for i in range(15):
        prod = vtecparser(get_test_file(f"WSWGRR/{i}.txt"))
        prod.sql(dbcursor)
        warnings = filter_warnings(prod.warnings)
        assert not warnings


@pytest.mark.parametrize("database", ["postgis"])
def test_150102_multiyear(dbcursor):
    """WSWOUN See how well we span multiple years"""
    for i in range(13):
        prod = vtecparser(get_test_file(f"WSWOUN/{i}.txt"))
        prod.sql(dbcursor)
        # Make sure there are no null issue times
        dbcursor.execute(
            "SELECT count(*) from warnings where vtec_year = 2014 and "
            "wfo = 'OUN' and "
            "eventid = 16 and phenomena = 'WW' and significance = 'Y' "
            "and issue is null"
        )
        assert dbcursor.fetchone()["count"] == 0
        if i == 5:
            dbcursor.execute(
                "SELECT issue from warnings WHERE vtec_year = 2014 and "
                "ugc = 'OKZ036' and "
                "wfo = 'OUN' and eventid = 16 and phenomena = 'WW' and "
                "significance = 'Y'"
            )
            row = dbcursor.fetchone()
            assert row["issue"] == utc(2015, 1, 1, 6, 0)
        warnings = filter_warnings(prod.warnings)
        warnings = filter_warnings(warnings, "Segment has duplicated")
        warnings = filter_warnings(warnings, "VTEC Product appears to c")
        assert not warnings


def test_141226_correction():
    """Add another test for product corrections"""
    with pytest.raises(UGCParseException):
        vtecparser(get_test_file("FLSRAH.txt"))


@pytest.mark.parametrize("database", ["postgis"])
def test_141212_mqt(dbcursor):
    """Updated four rows instead of three, better check on it"""
    for i in range(4):
        prod = vtecparser(get_test_file(f"MWWMQT/{i}.txt"))
        prod.sql(dbcursor)
        assert not filter_warnings(filter_warnings(prod.warnings), CUGC)


@pytest.mark.parametrize("database", ["postgis"])
def test_141211_null_expire(dbcursor):
    """Figure out why the database has a null expiration for this FL.W"""
    for i in range(0, 13):
        prod = vtecparser(get_test_file(f"FLSIND/{i}.txt"))
        prod.sql(dbcursor)
        prod.get_jabbers("", "")
        warnings = filter_warnings(filter_warnings(prod.warnings), "HVTEC")
        assert not filter_warnings(warnings, "LAT...LON")


@pytest.mark.parametrize("database", ["postgis"])
def test_141210_continues(dbcursor):
    """See that we handle CON with infinite time A-OK"""
    for i in range(0, 2):
        prod = vtecparser(get_test_file(f"FFAEKA/{i}.txt"))
        prod.sql(dbcursor)
        warnings = filter_warnings(filter_warnings(prod.warnings), "HVTEC")
        assert not warnings


@pytest.mark.parametrize("database", ["postgis"])
def test_141208_upgrade(dbcursor):
    """See that we can handle the EXB case"""
    for i in range(0, 18):
        prod = vtecparser(get_test_file(f"MWWLWX/{i:02d}.txt"))
        prod.sql(dbcursor)
        warnings = filter_warnings(prod.warnings)
        warnings = filter_warnings(warnings, "Segment has duplicated")
        assert not filter_warnings(warnings, CUGC)
    # ANZ532 gets too entries from the above check the issuance time of first
    dbcursor.execute(
        """
        SELECT issue at time zone 'UTC' as ii from warnings
        where vtec_year = 2014 and wfo = 'LWX'
        and eventid = 221 and phenomena = 'SC' and significance = 'Y'
        and ugc = 'ANZ532' and status != 'UPG'"""
    )
    assert dbcursor.fetchone()["ii"] == datetime.datetime(2014, 12, 7, 19, 13)


def test_truncated_tsu():
    """Test that we raise an error with a truncated TSU."""
    text = get_test_file("TSU/TSUWCA.txt")
    with pytest.raises(ValueError):
        vtecparser(text[:-60])


def test_141016_tsuwca():
    """TSUWCA Got a null vtec timestamp with this product"""
    utcnow = utc(2014, 10, 16, 17, 10)
    prod = vtecparser(get_test_file("TSU/TSUWCA.txt"), utcnow=utcnow)
    j = prod.get_jabbers("http://localhost", "http://localhost")
    assert not j


def test_140731_badugclabel():
    """Make sure this says zones and not counties!"""
    ugc_provider = {}
    for u in range(530, 550, 1):
        n = "a" * min((u + 1 / 2), 80)
        ugc_provider[f"ANZ{u:03d}"] = UGC(
            "AN", "Z", f"{u:03d}", name=n, wfos=["DMX"]
        )

    utcnow = utc(2014, 7, 31, 17, 35)
    prod = _vtecparser(
        get_test_file("MWWLWX.txt"), utcnow=utcnow, ugc_provider=ugc_provider
    )
    assert not prod.segments[0].is_emergency
    j = prod.get_jabbers("http://localhost", "http://localhost")
    ans = (
        "LWX issues Small Craft Advisory "
        "valid at Jul 31, 6:00 PM EDT for 7 forecast zones in [AN] till "
        "Aug 1, 6:00 AM EDT "
        "http://localhost2014-O-NEW-KLWX-SC-Y-0151_2014-07-31T22:00Z"
    )
    assert j[0][0] == ans


def test_tornado_emergency():
    """See what we do with Tornado Emergencies"""
    utcnow = utc(2012, 4, 15, 3, 27)
    data = get_test_file("TOR_emergency.txt")
    prod = vtecparser(data, utcnow=utcnow)
    assert prod.segments[0].is_emergency
    j = prod.get_jabbers("http://localhost", "http://localhost")
    ans = (
        '<p>ICT <a href="http://localhost'
        '2012-O-NEW-KICT-TO-W-0035_2012-04-15T03:27Z">'
        "issues Tornado Emergency</a> "
        "[tornado: OBSERVED, damage threat: CATASTROPHIC, "
        "hail: 2.50 IN] for ((KSC015)), ((KSC173)) [KS] till 11:00 PM CDT "
        '* AT 1019 PM CDT...<span style="color: #FF0000;">TORNADO '
        "EMERGENCY</span> FOR THE WICHITA METRO AREA. A CONFIRMED LARGE..."
        "VIOLENT AND EXTREMELY DANGEROUS TORNADO WAS LOCATED NEAR "
        "HAYSVILLE...AND MOVING NORTHEAST AT 50 MPH.</p>"
    )
    assert j[0][1] == ans
    ans = (
        "ICT issues Tornado Emergency [tornado: OBSERVED, damage "
        "threat: CATASTROPHIC, hail: 2.50 IN] "
        "for ((KSC015)), ((KSC173)) [KS] till 11:00 PM CDT "
        "http://localhost2012-O-NEW-KICT-TO-W-0035_2012-04-15T03:27Z"
    )
    assert j[0][2]["twitter"] == ans
    ans = (
        "https://mesonet.agron.iastate.edu/plotting/auto/plot/208/"
        "network:WFO::wfo:ICT::year:2012::phenomenav:TO::significancev:W"
        "::etn:35::valid:2012-04-15%200327::_r:86.png"
    )
    assert j[0][2]["twitter_media"] == ans
    # Remove catastrophic tag
    prod = vtecparser(
        data.replace("CATASTROPHIC", "CONSIDERABLE"),
        utcnow=utcnow,
    )
    assert not prod.segments[0].is_emergency


def test_badtimestamp():
    """See what happens when the MND provides a bad timestamp"""
    utcnow = utc(2005, 8, 29, 16, 56)
    with pytest.raises(ValueError):
        vtecparser(get_test_file("TOR_badmnd_timestamp.txt"), utcnow=utcnow)


def test_wcn_updates():
    """Make sure our Tags and svs_special works for combined message"""
    utcnow = utc(2014, 6, 6, 20, 37)
    ugc_provider = {}
    for u in range(1, 201, 2):
        n = "a" * int(min((u + 1 / 2), 40))
        for st in ["AR", "MS", "TN", "MO"]:
            ugc_provider[f"{st}C{u:03d}"] = UGC(
                st, "C", f"{u:03d}", name=n, wfos=["DMX"]
            )
    prod = _vtecparser(
        get_test_file("WCN/WCNMEG.txt"),
        utcnow=utcnow,
        ugc_provider=ugc_provider,
    )
    j = prod.get_jabbers("http://localhost", "http://localhost")
    ans = (
        "MEG updates Severe Thunderstorm Watch (expands area to include "
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa [MO] and 11 counties in "
        "[TN], continues 12 counties in [AR] and "
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa [MO] and 22 counties in "
        "[MS] and aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, "
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, "
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, "
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, "
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, "
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa [TN]) till Jun 6, 7:00 PM "
        "CDT. http://localhost2014-O-EXA-KMEG-SV-A-0240_2014-06-06T20:37Z"
    )
    assert j[0][0] == ans


def test_140715_condensed():
    """Make sure our Tags and svs_special works for combined message"""
    utcnow = utc(2014, 7, 6, 2, 1)
    prod = vtecparser(get_test_file("TORSVS.txt"), utcnow=utcnow)
    assert not prod.segments[0].is_emergency
    j = prod.get_jabbers("http://localhost", "http://localhost")
    ans = (
        "DMX updates Tornado Warning "
        "[tornado: OBSERVED, hail: &lt;.75 IN] (cancels ((IAC049)) [IA], "
        "continues ((IAC121)) [IA]) till 9:15 PM CDT. AT 901 PM CDT...A "
        "CONFIRMED TORNADO WAS LOCATED NEAR WINTERSET... MOVING "
        "SOUTHEAST AT 30 MPH. "
        "http://localhost2014-O-CON-KDMX-TO-W-0051_2014-07-06T02:01Z"
    )
    assert j[0][0] == ans


def test_140714_segmented_watch():
    """Two segmented watch text formatting stinks"""
    utcnow = utc(2014, 7, 14, 17, 25)
    prod = vtecparser(get_test_file("WCN/WCNPHI.txt"), utcnow=utcnow)
    j = prod.get_jabbers("http://localhost", "http://localhost")
    ans = (
        "PHI issues Severe Thunderstorm Watch (((DEC001)), "
        "((DEC003)), ((DEC005)) [DE] and ((MDC011)), ((MDC015)), "
        "((MDC029)), ((MDC035)), ((MDC041)) [MD] and ((NJC001)), "
        "((NJC005)), ((NJC007)), ((NJC009)), ((NJC011)), ((NJC015)), "
        "((NJC019)), ((NJC021)), ((NJC023)), ((NJC025)), ((NJC027)), "
        "((NJC029)), ((NJC033)), ((NJC035)), ((NJC037)), ((NJC041)) [NJ] "
        "and ((PAC011)), ((PAC017)), ((PAC025)), ((PAC029)), ((PAC045)), "
        "((PAC077)), ((PAC089)), ((PAC091)), ((PAC095)), ((PAC101)) [PA] "
        "and ((ANZ430)), ((ANZ431)), ((ANZ450)), ((ANZ451)), "
        "((ANZ452)), ((ANZ453)), ((ANZ454)), ((ANZ455)) [AN]) "
        "till Jul 14, 8:00 PM EDT. "
        "http://localhost2014-O-NEW-KPHI-SV-A-0418_2014-07-14T17:25Z"
    )
    assert j[0][0] == ans


def test_140610_tweet_spacing():
    """Saw spacing issue in tweet message"""
    utcnow = utc(2014, 6, 10, 13, 23)
    prod = vtecparser(get_test_file("FLWLCH.txt"), utcnow=utcnow)
    j = prod.get_jabbers("http://localhost", "http://localhost")
    ans = (
        "LCH issues Flood Warning "
        "valid at Jun 10, 9:48 AM CDT for ((VLSL1)) till Jun 12, 1:00 "
        "PM CDT http://localhost2014-O-NEW-KLCH-FL-W-0015_2014-06-10T14:48Z"
    )
    assert j[0][2]["twitter"] == ans
    ans = "https://water.noaa.gov/resources/hydrographs/vlsl1_hg.png"
    assert j[0][2]["twitter_media"] == ans


@pytest.mark.parametrize("database", ["postgis"])
def test_routine(dbcursor):
    """what can we do with a ROU VTEC product"""
    utcnow = utc(2014, 6, 19, 2, 56)
    prod = vtecparser(get_test_file("FLWMKX_ROU.txt"), utcnow=utcnow)
    prod.sql(dbcursor)
    warnings = filter_warnings(filter_warnings(prod.warnings), "HVTEC")
    assert not warnings


def test_correction():
    """Can we properly parse a product correction"""
    utcnow = utc(2014, 6, 6, 21, 30)
    prod = vtecparser(get_test_file("CCA.txt"), utcnow=utcnow)
    assert prod.is_correction()


@pytest.mark.parametrize("database", ["postgis"])
def test_140610_no_vtec_time(dbcursor):
    """A VTEC Product with both 0000 for start and end time, sigh"""
    utcnow = utc(2014, 6, 10, 0, 56)
    prod = vtecparser(get_test_file("FLSLZK_notime.txt"), utcnow=utcnow)
    prod.sql(dbcursor)
    assert prod.segments[0].vtec[0].begints is None
    assert prod.segments[0].vtec[0].endts is None


@pytest.mark.parametrize("database", ["postgis"])
def test_140609_ext_backwards(dbcursor):
    """Sometimes the EXT goes backwards in time, so we have fun"""
    utcnow = utc(2014, 6, 6, 15, 40)

    dbcursor.execute(
        """DELETE from warnings where vtec_year = 2014 and wfo = 'LBF'
    and eventid = 2 and phenomena = 'FL' and significance = 'W' """
    )
    dbcursor.execute(
        "DELETE from sbw where vtec_year = 2014 and wfo = 'LBF' and "
        "eventid = 2 and phenomena = 'FL' and significance = 'W'"
    )
    for i in range(1, 6):
        prod = vtecparser(
            get_test_file(f"FLWLBF/FLWLBF_{i}.txt"), utcnow=utcnow
        )
        prod.sql(dbcursor)

    dbcursor.execute("SET TIME ZONE 'UTC'")

    dbcursor.execute(
        "select status, updated, issue, expire, init_expire, polygon_begin, "
        "polygon_end from sbw where vtec_year = 2014 and eventid = 2 and "
        "phenomena = 'FL' and "
        "significance = 'W' and wfo = 'LBF' ORDER by updated ASC"
    )
    assert dbcursor.fetchone()["polygon_end"] == utc(2014, 6, 7, 2, 15)


def test_svs_search():
    """See that we get the SVS search done right"""
    utcnow = utc(2014, 6, 6, 20)

    prod = vtecparser(get_test_file("TORBOU_ibw.txt"), utcnow=utcnow)
    j = prod.segments[0].svs_search()
    ans = (
        "* AT 250 PM MDT...A SEVERE THUNDERSTORM "
        "CAPABLE OF PRODUCING A TORNADO WAS LOCATED 9 MILES WEST OF "
        "WESTPLAINS...OR 23 MILES SOUTH OF KIMBALL...MOVING EAST AT "
        "20 MPH."
    )
    assert j == ans


def test_tortag():
    """See what we can do with warnings with tags in them"""
    utcnow = utc(2011, 8, 7, 4, 36)

    prod = vtecparser(get_test_file("TORtag.txt"), utcnow=utcnow)
    j = prod.get_jabbers("http://localhost/", "http://localhost/")
    assert prod.is_homogeneous()
    ans = (
        '<p>DMX <a href="http://localhost/2011-'
        'O-NEW-KDMX-TO-W-0057_2011-08-07T04:36Z">'
        "issues Tornado Warning</a> [tornado: "
        "OBSERVED, damage threat: SIGNIFICANT, hail: 2.75 IN] "
        "for ((IAC117)), ((IAC125)), ((IAC135)) [IA] till 12:15 AM CDT "
        "* AT 1132 PM CDT...NATIONAL WEATHER SERVICE DOPPLER RADAR "
        "INDICATED A SEVERE THUNDERSTORM CAPABLE OF PRODUCING A TORNADO. "
        "THIS DANGEROUS STORM WAS LOCATED 8 MILES EAST OF CHARITON..."
        "OR 27 MILES NORTHWEST OF CENTERVILLE...AND MOVING NORTHEAST "
        "AT 45 MPH.</p>"
    )
    assert j[0][1] == ans


def test_wcn():
    """Special tweet logic for cancels and continues

    NOTE: with updated twitter tweet chars, these tests are not as fun
    """
    utcnow = utc(2014, 6, 3)
    ugc_provider = {}
    for u in range(1, 201, 2):
        n = "a" * int(min((u + 1 / 2), 40))
        ugc_provider[f"IAC{u:03d}"] = UGC(
            "IA", "C", f"{u:03d}", name=n, wfos=["DMX"]
        )

    prod = _vtecparser(
        get_test_file("SVS.txt"), utcnow=utcnow, ugc_provider=ugc_provider
    )
    j = prod.get_jabbers("http://localhost/", "http://localhost/")
    assert prod.is_homogeneous()
    ans = (
        "DMX updates Severe Thunderstorm Warning [wind: 60 MPH, hail: "
        "&lt;.75 IN]  (cancels aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa "
        "[IA], continues aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa [IA]) "
        "till 10:45 PM CDT "
        "http://localhost/2014-O-CON-KDMX-SV-W-0143_2014-06-03T00:00Z"
    )
    assert j[0][2]["twitter"] == ans
    ans = (
        "https://mesonet.agron.iastate.edu/plotting/auto/plot/208/network:"
        "WFO::wfo:DMX::year:2014::phenomenav:SV::significancev:W::etn:143::"
        "valid:2014-06-04%200331::_r:86.png"
    )
    assert j[0][2]["twitter_media"] == ans

    prod = _vtecparser(
        get_test_file("WCN/WCN.txt"), utcnow=utcnow, ugc_provider=ugc_provider
    )
    j = prod.get_jabbers("http://localhost/", "http://localhost/")
    assert prod.is_homogeneous()
    ans = (
        "DMX updates Tornado Watch (cancels a, "
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaa, aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        "aaaaaaaaa, aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, aaaaaaaaa"
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa [IA], continues 12 counties "
        "in [IA]) till Jun 4, 1:00 AM CDT "
        "http://localhost/2014-O-CON-KDMX-TO-A-0210_2014-06-03T00:00Z"
    )
    assert j[0][2]["twitter"] == ans
    ans = (
        "DMX updates Tornado Watch (cancels a, "
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaa, aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        "aaaaaaaa, aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, aaaaaaaaaaa"
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaa [IA], continues 12 counties "
        "in [IA]) till Jun 4, 1:00 AM CDT. "
        "http://localhost/2014-O-CON-KDMX-TO-A-0210_2014-06-03T00:00Z"
    )
    assert j[0][0] == ans


@pytest.mark.parametrize("database", ["postgis"])
def test_140604_sbwupdate(dbcursor):
    """Make sure we are updating the right info in the sbw table"""
    utcnow = utc(2014, 6, 4)

    dbcursor.execute(
        "DELETE from sbw where vtec_year = 2014 and wfo = 'LMK' and "
        "eventid = 95 and phenomena = 'SV' and significance = 'W'"
    )
    dbcursor.execute(
        "DELETE from warnings where vtec_year = 2014 and wfo = 'LMK' and "
        "eventid = 95 and phenomena = 'SV' and significance = 'W'"
    )

    prod = vtecparser(get_test_file("SVRLMK_1.txt"), utcnow=utcnow)
    prod.sql(dbcursor)

    dbcursor.execute(
        "SELECT expire from sbw WHERE vtec_year = 2014 and wfo = 'LMK' and "
        "eventid = 95 and phenomena = 'SV' and significance = 'W'"
    )
    assert dbcursor.rowcount == 1

    prod = vtecparser(get_test_file("SVRLMK_2.txt"), utcnow=utcnow)
    prod.sql(dbcursor)

    dbcursor.execute(
        """SELECT expire from sbw WHERE vtec_year = 2014 and
    wfo = 'LMK' and eventid = 95 and phenomena = 'SV' and
    significance = 'W' """
    )
    assert dbcursor.rowcount == 2
    warnings = filter_warnings(prod.warnings)
    assert not warnings


def test_140321_invalidgeom():
    """See what we do with an invalid geometry from IWX"""
    prod = vtecparser(get_test_file("FLW_badgeom.txt"))
    ans = (
        "SRID=4326;MULTIPOLYGON ((("
        "-85.68 41.86, -85.64 41.97, -85.54 41.97, -85.54 41.96, "
        "-85.61 41.93, -85.66 41.84, -85.68 41.86)))"
    )
    assert prod.segments[0].giswkt == ans


@pytest.mark.parametrize("database", ["postgis"])
def test_140527_astimezone(dbcursor):
    """Test the processing of a begin timestamp"""
    utcnow = utc(2014, 5, 27, 16, 3)
    prod = vtecparser(get_test_file("MWWSEW.txt"), utcnow=utcnow)
    prod.sql(dbcursor)
    j = prod.get_jabbers("http://localhost/", "http://localhost/")
    ans = (
        "SEW continues Small Craft Advisory "
        "valid at May 27, 4:00 PM PDT for ((PZZ131)), ((PZZ132)) [PZ] till"
        " May 28, 5:00 AM PDT "
        "http://localhost/2014-O-CON-KSEW-SC-Y-0113_2014-05-27T23:00Z"
    )
    assert j[0][0] == ans


@pytest.mark.parametrize("database", ["postgis"])
def test_140527_00000_hvtec_nwsli(dbcursor):
    """Test the processing of a HVTEC NWSLI of 00000"""
    utcnow = utc(2014, 5, 27)
    prod = vtecparser(get_test_file("FLSBOU.txt"), utcnow=utcnow)
    prod.sql(dbcursor)
    j = prod.get_jabbers("http://localhost/", "http://localhost/")
    ans = (
        "BOU extends time of Flood Advisory "
        "for ((COC049)), ((COC057)) [CO] till May 29, 9:30 PM MDT "
        "http://localhost/2014-O-EXT-KBOU-FA-Y-0018_2014-05-27T15:25Z"
    )
    assert j[0][0] == ans
    ans = (
        "BOU extends time of Flood "
        "Advisory for ((COC049)), ((COC057)) [CO] till "
        "May 29, 9:30 PM MDT "
        "http://localhost/2014-O-EXT-KBOU-FA-Y-0018_2014-05-27T15:25Z"
    )
    assert j[0][2]["twitter"] == ans


def test_affected_wfos():
    """see what affected WFOs we have"""
    ugc_provider = {"IAZ006": UGC("IA", "Z", "006", wfos=["DMX"])}
    prod = _vtecparser(
        get_test_file("WSWDMX/WSW_00.txt"), ugc_provider=ugc_provider
    )
    assert prod.segments[0].get_affected_wfos()[0] == "DMX"


@pytest.mark.parametrize("database", ["postgis"])
def test_141023_upgrade(dbcursor):
    """See that we can handle the upgrade and downgrade dance"""
    for i in range(1, 8):
        prod = vtecparser(get_test_file(f"NPWBOX/NPW_{i:02d}.txt"))
        prod.sql(dbcursor)
        warnings = filter_warnings(prod.warnings)
        assert not warnings


@pytest.mark.parametrize("database", ["postgis"])
def test_vtec_series(dbcursor):
    """Test a lifecycle of WSW products"""
    # This is from 2024, which will exercise an archive search
    prod = vtecparser(get_test_file("WSWDMX/WSW_N1.txt"))
    prod.sql(dbcursor)

    prod = vtecparser(get_test_file("WSWDMX/WSW_00.txt"))
    assert prod.afos == "WSWDMX"
    prod.sql(dbcursor)

    # Did Marshall County IAZ049 get a ZR.Y
    dbcursor.execute(
        "SELECT issue from warnings WHERE vtec_year = 2013 and wfo = 'DMX' "
        "and eventid = 1 "
        "and phenomena = 'ZR' and significance = 'Y' and status = 'EXB' "
        "and ugc = 'IAZ049'"
    )
    assert dbcursor.rowcount == 1

    prod = vtecparser(get_test_file("WSWDMX/WSW_01.txt"))
    assert prod.afos == "WSWDMX"
    prod.sql(dbcursor)

    # Is IAZ006 in CON status with proper end time
    answer = utc(2013, 1, 28, 6)
    dbcursor.execute(
        "SELECT expire from warnings WHERE vtec_year = 2013 and wfo = 'DMX' "
        "and eventid = 1 "
        "and phenomena = 'WS' and significance = 'W' and status = 'CON' "
        "and ugc = 'IAZ006'"
    )

    assert dbcursor.rowcount == 1
    row = dbcursor.fetchone()
    assert row["expire"] == answer

    # No change
    for i in range(2, 9):
        prod = vtecparser(get_test_file(f"WSWDMX/WSW_{i:02d}.txt"))
        assert prod.afos == "WSWDMX"
        prod.sql(dbcursor)

    prod = vtecparser(get_test_file("WSWDMX/WSW_09.txt"))
    assert prod.afos == "WSWDMX"
    prod.sql(dbcursor)

    # IAZ006 should be cancelled
    answer = utc(2013, 1, 28, 5, 38)
    dbcursor.execute(
        "SELECT expire from warnings WHERE vtec_year = 2013 and wfo = 'DMX' "
        "and eventid = 1 "
        "and phenomena = 'WS' and significance = 'W' and status = 'CAN' "
        "and ugc = 'IAZ006'"
    )

    assert dbcursor.rowcount == 1
    row = dbcursor.fetchone()
    assert row["expire"] == answer


@pytest.mark.parametrize("database", ["postgis"])
def test_vtec(dbcursor):
    """Simple test of VTEC parser"""
    # Remove cruft first
    dbcursor.execute(
        "DELETE from warnings WHERE vtec_year = 2005 and wfo = 'JAN' and "
        "eventid = 130 and "
        "phenomena = 'TO' and significance = 'W'"
    )
    dbcursor.execute(
        """
        DELETE from sbw WHERE vtec_year = 2005 and
        wfo = 'JAN' and eventid = 130 and phenomena = 'TO' and
        significance = 'W' and status = 'NEW'
    """
    )

    ugc_provider = {"MSC091": UGC("MS", "C", "091", "DARYL", ["XXX"])}
    nwsli_provider = {"AMWI4": NWSLI("AMWI4", "Ames", ["XXX"], -99, 44)}
    prod = _vtecparser(
        get_test_file("TOR.txt"),
        ugc_provider=ugc_provider,
        nwsli_provider=nwsli_provider,
    )
    assert not prod.is_skip_con()
    assert abs(prod.segments[0].sbw.area - 0.3053) < 0.0001

    prod.sql(dbcursor)

    # See if we got it in the database!
    dbcursor.execute(
        """
        SELECT issue from warnings WHERE vtec_year = 2005 and
        wfo = 'JAN' and eventid = 130 and phenomena = 'TO' and
        significance = 'W' and status = 'NEW'
    """
    )
    assert dbcursor.rowcount == 3

    dbcursor.execute(
        "SELECT issue from sbw WHERE vtec_year = 2005 and wfo = 'JAN' and "
        "eventid = 130 and "
        "phenomena = 'TO' and significance = 'W' and status = 'NEW'"
    )
    assert dbcursor.rowcount == 1

    msgs = prod.get_jabbers("http://localhost", "http://localhost/")
    ans = (
        "JAN issues Tornado Warning for "
        "((MSC035)), ((MSC073)), DARYL [MS] till Aug 29, 1:15 PM CDT * AT "
        "1150 AM CDT...THE NATIONAL WEATHER SERVICE HAS ISSUED A "
        "TORNADO WARNING FOR DESTRUCTIVE WINDS OVER 110 MPH IN THE EYE "
        "WALL AND INNER RAIN BANDS OF HURRICANE KATRINA. THESE WINDS "
        "WILL OVERSPREAD MARION...FORREST AND LAMAR COUNTIES DURING "
        "THE WARNING PERIOD. "
        "http://localhost2005-O-NEW-KJAN-TO-W-0130_2005-08-29T16:51Z"
    )
    assert msgs[0][0] == ans
