"""Off-loaded private stuff from `vtec.py`."""

# pylint: disable=too-many-arguments
import itertools
from datetime import datetime, timedelta, timezone

import pandas as pd
from psycopg.sql import SQL

from pyiem.nws.product import TextProduct, TextProductSegment
from pyiem.nws.ugc import UGC
from pyiem.nws.vtec import VTEC
from pyiem.reference import VTEC_POLYGON_DATES
from pyiem.util import LOG

# When a VTEC product has an infinity time 000000T0000Z, we need some value
# for the database to make things logically work.  We arb pick 21 days, which
# seems to be enough time to ensure a WFO issues some followup statement.
DEFAULT_EXPIRE_DELTA = timedelta(hours=21 * 24)


def _check_vtec_polygon(prod):
    """Emit warnings for segments that should have a polygon."""
    for i, seg in enumerate(prod.segments, start=1):
        if seg.sbw is not None:
            continue
        for vtec in seg.vtec:
            basedate = VTEC_POLYGON_DATES.get(vtec.s2())
            if basedate is None or prod.valid.date() < basedate:
                continue
            prod.warnings.append(
                f"Segment {i} missing required polygon for VTEC: {vtec.s2()}"
            )


def which_year(txn, prod, segment, vtec) -> int:
    """Figure out which table we should work against"""
    # The case of a NEW event always goes into the current UTC year of prod
    if vtec.action in ["NEW"]:
        # Lets piggyback a check to see if this ETN has been reused?
        # Can this realiably be done?
        txn.execute(
            f"SELECT max(updated) from warnings_{prod.valid.year} "
            "WHERE wfo = %s "
            "and eventid = %s and significance = %s and phenomena = %s",
            (vtec.office, vtec.etn, vtec.significance, vtec.phenomena),
        )
        row = txn.fetchone()
        if row["max"] is not None:
            if (prod.valid - row["max"]).total_seconds() > (21 * 86400):
                prod.warnings.append(
                    "Possible Duplicated ETN\n"
                    f"  max(updated) is {row['max']}, "
                    f"prod.valid is {prod.valid}\n"
                    f"  VTEC: {str(vtec)}\n  "
                    f"product_id: {prod.get_product_id()}"
                )
        return prod.valid.year
    # Lets query the database to look for any matching entries within
    # the past 3, 10, 31 days, to find with the product_issue was,
    # which guides the table that the data is stored within
    for offset in [3, 10, 31]:
        txn.execute(
            """
            SELECT vtec_year, hvtec_nwsli,
            min(product_issue at time zone 'UTC'),
            max(product_issue at time zone 'UTC'),
            array_agg(ugc) as database_ugcs,
            min(issue at time zone 'UTC') as min_issue from warnings
            WHERE wfo = %s and eventid = %s and significance = %s and
            phenomena = %s and ((updated > %s and updated <= %s)
            or (expire > %s and expire < %s)) and status not in ('UPG', 'CAN')
            GROUP by vtec_year, hvtec_nwsli ORDER by vtec_year DESC
            """,
            (
                vtec.office,
                vtec.etn,
                vtec.significance,
                vtec.phenomena,
                prod.valid - timedelta(days=offset),
                prod.valid,
                prod.valid,
                prod.valid + timedelta(days=31),  # life choices
            ),
        )
        rows = txn.fetchall()
        if not rows:
            continue
        if len(rows) > 1:
            # We could have an ambiguious situation around the new year, so
            # we attempt to use the issue to resolve this.
            if vtec.begints is not None:
                for row in rows:
                    mi = row["min_issue"].replace(tzinfo=timezone.utc)
                    if mi == vtec.begints:
                        return row["vtec_year"]
            # We likely have a flood warning and can use the HVTEC NWSLI
            # to resolve ambiguity
            hvtec_nwsli = segment.get_hvtec_nwsli()
            if hvtec_nwsli and hvtec_nwsli != "00000":
                for row in rows:
                    if hvtec_nwsli == row["hvtec_nwsli"]:
                        return row["vtec_year"]
            # Attempt to resolve by comparing UGCs
            segugcs = [str(u) for u in segment.ugcs]
            for row in rows:
                if all(x in segugcs for x in row["database_ugcs"]):
                    LOG.warning("Resolved ambuquity via UGC check")
                    return row["vtec_year"]

        row = rows[0]
        if row["min"] is not None:
            year = row["min"].year
            if row["max"].year != year:
                LOG.warning(
                    "VTEC Product appears to cross 1 Jan UTC "
                    "minyear: %s maxyear: %s VTEC: %s productid: %s",
                    year,
                    row["max"].year,
                    str(vtec),
                    prod.get_product_id(),
                )
            return row["vtec_year"]

    # Give up
    if not prod.is_correction():
        table = f"warnings_{prod.valid.year}"
        prod.warnings.append(
            "Failed to find year of product issuance:\n"
            f"  VTEC:{str(vtec)}\n  PRODUCT: {prod.get_product_id()}\n"
            f"  defaulting to use year: {prod.valid.year}\n"
            f"  {list_rows(txn, table, vtec)}"
        )
    return prod.valid.year


def _check_dueling_tropics(prod: TextProduct) -> bool:
    """Check that we don't have overlapping tropical products.

    A requested quality control check.

    Args:
        prod: Product object to check.

    Returns:
        True if overlapping tropical products, False if not.
    """
    sentinel = False
    for i, seg in enumerate(prod.segments, start=1):
        keys = [f"{v.phenomena}.{v.significance}" for v in seg.vtec]
        if "TR.A" not in keys and "TR.W" not in keys:
            continue
        for sig in ["A", "W"]:
            if f"TR.{sig}" not in keys or f"HU.{sig}" not in keys:
                continue
            # We have a potential overlap
            active = 0
            for vtec in seg.vtec:
                if (
                    vtec.phenomena in ["TR", "HU"]
                    and vtec.significance == sig
                    and vtec.action not in ["UPG", "CAN", "EXP"]
                ):
                    active += 1
            if active > 1:
                prod.warnings.append(
                    f"Dueling tropical VTEC for segment {i} {seg.vtec}"
                )
                sentinel = True
    return sentinel


def _check_unique_ugc(prod) -> bool:
    """Quality Control check that a given product uniquely uses UGCS.

    Discussions with AWIPS developer expressed interesting in knowing that
    this was being enforced.  It adds a warning message and returns a bool
    on if this was a problem.

    Args:
        prod: Product object to check.

    Returns:
        True if UGCS are unique, False if not.
    """
    domain = []
    for seg in prod.segments:
        # HVTEC products are an exception to this rule.
        if seg.hvtec:
            continue
        domain.extend([str(u) for u in seg.ugcs])
    ugcs = pd.Series(domain, dtype=str)
    if ugcs.duplicated().any():
        vals = ugcs[ugcs.duplicated()].values
        prod.warnings.append(
            f"Duplicated UGCs Found (10.1701 3.9.1): {','.join(vals)}"
        )
        return False
    return True


def _associate_vtec_year(prod, txn):
    """Figure out to which year each VTEC in the product belongs.

    Modifies the prod.segment.vtec objects."""
    for seg, _ugcs, vtec in prod.suv_iter():
        if vtec.year is None:
            vtec.year = which_year(txn, prod, seg, vtec)


def _load_database_status(txn, prod):
    """Build a pandas dataframe for what the database knows."""
    rows = []
    done = []
    for _seg, _ugcs, vtec in prod.suv_iter():
        if vtec.status == "NEW" or vtec.year is None:
            continue
        key = f"{vtec.office}.{vtec.phenomena}.{vtec.significance}.{vtec.etn}"
        if key in done:
            continue
        done.append(key)
        txn.execute(
            "SELECT ugc, status, updated at time zone 'UTC' as utc_updated, "
            "expire at time zone 'UTC' as utc_expire "
            f"from warnings_{vtec.year} WHERE wfo = %s and "
            "phenomena = %s and significance = %s and eventid = %s and "
            "status not in ('CAN', 'UPG', 'EXP') and expire >= %s",
            (
                vtec.office,
                vtec.phenomena,
                vtec.significance,
                vtec.etn,
                prod.valid,
            ),
        )
        for row in txn.fetchall():
            entry = {
                "ugc": row["ugc"],
                "status": row["status"],
                "year": vtec.year,
                "phenomena": vtec.phenomena,
                "significance": vtec.significance,
                "etn": vtec.etn,
                "updated": row["utc_updated"],
                "expire": row["utc_expire"],
            }
            rows.append(entry)
    return pd.DataFrame(rows)


def check_dup_ps(segment):
    """Does this TextProductSegment have duplicated VTEC

    NWS AWIPS Developer asked that alerts be made when a VTEC segment has a
    phenomena and significance that are reused. In practice, this error is
    in the case of having the same phenomena.significance overlap in time. The
    combination of the same pheom.sig for events happening now and in the
    future is OK and common

    Returns:
      bool
    """
    combos = {}
    for thisvtec in segment.vtec:
        if thisvtec.begints is None or thisvtec.endts is None:
            # The logic here is too difficult for now, so we ignore
            continue
        key = thisvtec.s2()
        val = combos.setdefault(key, [])
        # we can't use vtec.endts in this situation
        endts = (
            segment.tp.valid
            if thisvtec.status in ["UPG", "CAN"]
            else thisvtec.endts
        )
        val.append([thisvtec.begints, endts])

    for combo in combos.values():
        if len(combo) == 1:
            continue
        for one, two in itertools.permutations(combo, 2):
            # We check for overlap
            if one[0] >= two[0] and one[0] < two[1]:
                return True
    return False


def do_sql_hvtec(txn, segment):
    """Process the HVTEC in this product"""
    nwsli = segment.hvtec[0].nwsli.id
    # No point in saving these events
    if nwsli == "00000":
        return
    if len(segment.bullets) < 4:
        return
    stage_text = ""
    flood_text = ""
    forecast_text = ""
    impact_text = ""
    for _, bullet in enumerate(segment.bullets):
        bsu = bullet.strip().upper()
        if bsu.find("FLOOD STAGE") == 0:
            flood_text = bullet
        if bsu.find("FORECAST") == 0:
            forecast_text = bullet
        if bsu.find("AT ") == 0 and stage_text == "":
            stage_text = bullet
        if bsu.startswith("IMPACT") and bsu.find("...") > -1:
            impact_text = bullet.split("...", 1)[1].strip()
    txn.execute(
        "INSERT into riverpro(nwsli, stage_text, flood_text, forecast_text, "
        "impact_text, severity) VALUES (%s,%s,%s,%s,%s,%s)",
        (
            nwsli,
            stage_text,
            flood_text,
            forecast_text,
            impact_text,
            segment.hvtec[0].severity,
        ),
    )


def list_rows(txn, table, vtec):
    """Return a simple listing of what exists in the database"""
    txn.execute(
        (
            "SELECT ugc, issue at time zone 'UTC' as ui, status, "
            f"updated at time zone 'UTC' as uu from {table} "
            "WHERE wfo = %s and phenomena = %s and significance = %s and "
            "eventid = %s ORDER by ugc"
        ),
        (vtec.office, vtec.phenomena, vtec.significance, vtec.etn),
    )
    res = (
        f"Entries for VTEC within {table}\n"
        "  UGC    STA ISSUED              UPDATED\n"
    )
    for row in txn.fetchall():
        res += f"  {row['ugc']} {row['status']} {row['ui']} {row['uu']}\n"
    return res


def _debug_warning(prod, txn, vtec, segment, ets):
    """Get a more useful warning message for this failure"""
    cnt = txn.rowcount
    txn.execute(
        "SELECT ugc, issue at time zone 'UTC' as utc_issue, "
        "expire at time zone 'UTC' as utc_expire, "
        "updated at time zone 'UTC' as utc_updated, "
        "status from warnings WHERE vtec_year = %s and wfo = %s and "
        "eventid = %s and ugc = any(%s) and significance = %s and "
        "phenomena = %s ORDER by ugc ASC, issue ASC",
        (
            vtec.year,
            vtec.office,
            vtec.etn,
            segment.get_ugcs_list(),
            vtec.significance,
            vtec.phenomena,
        ),
    )
    debugmsg = "UGC    STA ISSUE            EXPIRE           UPDATED\n"

    def myfmt(val):
        """Be more careful"""
        default = f"{'((NULL))':>16}"
        return default if val is None else val.strftime("%Y-%m-%d %H:%M")

    for row in txn.fetchall():
        debugmsg += (
            f"{row['ugc']} {row['status']} {myfmt(row['utc_issue'])} "
            f"{myfmt(row['utc_expire'])} {myfmt(row['utc_updated'])}\n"
        )
    return (
        f"Warning: {vtec.s3()} do_sql_vtec {vtec.year} {vtec.action} "
        f"updated {cnt} row, should {len(segment.ugcs)} rows\n"
        f"UGCS: {segment.ugcs}\n"
        f"valid: {prod.valid} expire: {ets}\n{debugmsg}"
    )


def _resent_match(prod, txn, vtec):
    """Check if this is a resent match."""
    txn.execute(
        "SELECT max(updated) as maxtime from warnings "
        "WHERE vtec_year = %s and eventid = %s and significance = %s and "
        "wfo = %s and phenomena = %s",
        (vtec.year, vtec.etn, vtec.significance, vtec.office, vtec.phenomena),
    )
    maxtime = txn.fetchone()["maxtime"]
    if maxtime is not None and maxtime == prod.valid:
        LOG.warning(
            "RESENT Match, skipping SQL for %s!", prod.get_product_id()
        )
        return True
    return False


def _cross_check_watch_pds(prod, txn, segment: TextProductSegment, vtec):
    """Lookup the watch information."""
    txn.execute(
        """
        select is_pds from watches where num = %s
        and extract(year from issued at time zone 'UTC') = %s
        """,
        (vtec.etn, prod.valid.year),
    )
    if txn.rowcount != 1:
        prod.warnings.append(
            f"Failed to cross check PDS status {prod.valid.year}[{vtec.etn}]"
        )
        return
    segment.is_pds = txn.fetchone()["is_pds"]


def create_warning_record(
    txn,
    prod: TextProduct,
    segment: TextProductSegment,
    vtec: VTEC,
    ugc: UGC,
    bts: datetime,
    ets: datetime,
) -> None:
    """Create a new warning record in the database."""
    # Since we are in a transaction and a null gid will cause a rollback,
    # we need to pre-flight check this and return if it is None.
    txn.execute(
        "select get_gid(%s, %s, %s) as gid",
        (str(ugc), prod.valid, vtec.phenomena == "FW"),
    )
    gid = txn.fetchone()["gid"]
    if gid is None:
        prod.warnings.append(
            f"get_gid({str(ugc)}, {prod.valid}, {vtec.phenomena == 'FW'}) "
            "was null, cannot create warning record"
        )
        return
    txn.execute(
        "INSERT into warnings (vtec_year, issue, expire, updated, "
        "wfo, eventid, status, fcster, ugc, phenomena, "
        "significance, gid, init_expire, product_issue, "
        "hvtec_nwsli, hvtec_severity, hvtec_cause, hvtec_record, "
        "is_emergency, is_pds, purge_time, product_ids) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
        "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "RETURNING gid",
        (
            vtec.year,
            bts,
            ets,
            prod.valid,
            vtec.office,
            vtec.etn,
            vtec.action,
            prod.get_signature(),
            str(ugc),
            vtec.phenomena,
            vtec.significance,
            gid,
            ets,
            prod.valid,
            segment.get_hvtec_nwsli(),
            segment.get_hvtec_severity(),
            segment.get_hvtec_cause(),
            segment.get_hvtec_record(),
            segment.is_emergency,
            segment.is_pds,
            segment.ugcexpire,
            [prod.get_product_id()],
        ),
    )


def _do_sql_vtec_new(prod, txn, segment, vtec: VTEC):
    """Do the NEW style actions."""
    bts = prod.valid if vtec.begints is None else vtec.begints
    # If this product has no expiration time, but db needs a value
    ets = vtec.endts
    if vtec.endts is None:
        ets = bts + DEFAULT_EXPIRE_DELTA
    # akrherz/pyIEM#925 Need to cross-check watches for PDS status
    # Hawaii "rolls their own", so no cross check is possible
    if (
        vtec.phenomena in ["TO", "SV"]
        and vtec.significance == "A"
        and vtec.office4 != "PHFO"
    ):
        _cross_check_watch_pds(prod, txn, segment, vtec)

    # For each UGC code in this segment, we create a database entry
    for ugc in segment.ugcs:
        # Check to see if we have entries already for this UGC
        # Some previous entries may not be in a terminated state, so
        # also check the expiration time
        txn.execute(
            "SELECT issue, expire, updated from warnings "
            "WHERE vtec_year = %s and ugc = %s and eventid = %s and "
            "significance = %s and wfo = %s and phenomena = %s and "
            "status not in ('CAN', 'UPG') and expire > %s",
            (
                vtec.year,
                str(ugc),
                vtec.etn,
                vtec.significance,
                vtec.office,
                vtec.phenomena,
                prod.valid,
            ),
        )
        if txn.rowcount > 0:
            if prod.is_correction():
                # We'll delete old entries, gulp
                txn.execute(
                    "DELETE from warnings WHERE vtec_year = %s and ugc = %s "
                    "and eventid = %s and significance = %s and "
                    "wfo = %s and phenomena = %s and "
                    "status in ('NEW', 'EXB', 'EXA') ",
                    (
                        vtec.year,
                        str(ugc),
                        vtec.etn,
                        vtec.significance,
                        vtec.office,
                        vtec.phenomena,
                    ),
                )
                if txn.rowcount != 1:
                    prod.warnings.append(
                        f"{vtec.s3()} {str(ugc)} duplicated via "
                        f"product correction, deleted {txn.rowcount} "
                        "old rows instead of 1"
                    )

            else:
                prod.warnings.append(
                    "Duplicate(s) WWA found, "
                    f"rowcount: {txn.rowcount} for UGC: {ugc}"
                )
        create_warning_record(
            txn,
            prod,
            segment,
            vtec,
            ugc,
            bts,
            ets,
        )


def _do_sql_vtec_cor(prod, txn, segment, vtec):
    """A Product Correction."""
    # For corrections, we only update the SVS and updated
    txn.execute(
        "UPDATE warnings SET updated = %s, purge_time = %s, "
        "is_emergency = (case when %s then true else is_emergency end), "
        "product_ids = array_append(product_ids, %s) WHERE vtec_year = %s "
        "and wfo = %s and eventid = %s and ugc = any(%s) and "
        "significance = %s and phenomena = %s and "
        "(expire + '1 hour'::interval) >= %s ",
        (
            prod.valid,
            segment.ugcexpire,
            segment.is_emergency,
            prod.get_product_id(),
            vtec.year,
            vtec.office,
            vtec.etn,
            segment.get_ugcs_list(),
            vtec.significance,
            vtec.phenomena,
            prod.valid,
        ),
    )
    if txn.rowcount != len(segment.ugcs):
        prod.warnings.append(
            _debug_warning(prod, txn, vtec, segment, vtec.endts)
        )


def _do_sql_vtec_can(prod, txn, segment, vtec):
    """Database work for EXT, UPG, CAN actions."""
    ets = vtec.endts
    # These are terminate actions, so we act accordingly
    if vtec.action in ["CAN", "UPG"]:
        ets = prod.valid
    # If we are extending into infinity, but need a value
    if vtec.action == "EXT" and vtec.endts is None:
        ets = prod.valid + DEFAULT_EXPIRE_DELTA

    # An EXT action could change the issuance time, gasp
    issuesql = ""
    if vtec.action == "EXT" and vtec.begints is not None:
        issuesql = f" issue = '{vtec.begints}', "
    txn.execute(
        SQL(
            """UPDATE warnings SET {} expire = %s,
        status = %s, updated = %s, purge_time = %s,
        is_emergency = (case when %s then true else is_emergency end),
        product_ids = array_append(product_ids, %s)
        WHERE vtec_year = %s and wfo = %s and eventid = %s and ugc =
        ANY(%s) and significance = %s and phenomena = %s
        and status not in ('CAN', 'UPG') and
        (expire + '1 hour'::interval) >= %s
        """
        ).format(
            SQL(issuesql),
        ),
        (
            ets,
            vtec.action,
            prod.valid,
            segment.ugcexpire,
            segment.is_emergency,
            prod.get_product_id(),
            vtec.year,
            vtec.office,
            vtec.etn,
            segment.get_ugcs_list(),
            vtec.significance,
            vtec.phenomena,
            prod.valid,
        ),
    )
    if txn.rowcount != len(segment.ugcs):
        if not prod.is_correction():
            prod.warnings.append(_debug_warning(prod, txn, vtec, segment, ets))


def _do_sql_vtec_con(prod, txn, segment, vtec):
    """Continue."""
    # These are no-ops, just updates
    ets = vtec.endts
    if vtec.endts is None:
        ets = prod.valid + DEFAULT_EXPIRE_DELTA

    # Offices have 1 hour to expire something :), actually 30 minutes
    ugcs_in = segment.get_ugcs_list()
    txn.execute(
        "UPDATE warnings SET status = %s, updated = %s, "
        "expire = %s, purge_time = %s, "
        "is_emergency = (case when %s then true else is_emergency end), "
        "is_pds = (case when %s then true else is_pds end), "
        "product_ids = array_append(product_ids, %s) "
        "WHERE vtec_year = %s and wfo = %s and eventid = %s and ugc = any(%s) "
        "and significance = %s and phenomena = %s and "
        "status not in ('CAN', 'UPG') and "
        "(expire + '1 hour'::interval) >= %s returning ugc",
        (
            vtec.action,
            prod.valid,
            ets,
            segment.ugcexpire,
            segment.is_emergency,
            segment.is_pds,
            prod.get_product_id(),
            vtec.year,
            vtec.office,
            vtec.etn,
            ugcs_in,
            vtec.significance,
            vtec.phenomena,
            prod.valid,
        ),
    )
    if txn.rowcount != len(segment.ugcs):
        ugcs_out = [row["ugc"] for row in txn.fetchall()]
        prod.warnings.append(_debug_warning(prod, txn, vtec, segment, ets))
        # Here lies CON creates logic.  Better to have a database entry than
        # not
        added = []
        for ugc in ugcs_in:
            if ugc in ugcs_out:
                continue
            added.append(ugc)
            create_warning_record(
                txn,
                prod,
                segment,
                vtec,
                ugc,
                prod.valid if vtec.begints is None else vtec.begints,
                ets,
            )
        prod.warnings.append(
            f"CON create for {vtec.s3()} added {len(added)} new rows for "
            f"UGCs: {','.join(added)}"
        )
