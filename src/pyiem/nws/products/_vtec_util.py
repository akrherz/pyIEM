"""Off-loaded private stuff from `vtec.py`."""
# pylint: disable=too-many-arguments
from datetime import timedelta, timezone
import itertools

import pandas as pd
from pyiem.util import LOG

# When a VTEC product has an infinity time 000000T0000Z, we need some value
# for the database to make things logically work.  We arb pick 21 days, which
# seems to be enough time to ensure a WFO issues some followup statement.
DEFAULT_EXPIRE_DELTA = timedelta(hours=(21 * 24))


def which_year(txn, prod, segment, vtec):
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
            "SELECT tableoid::regclass as tablename, hvtec_nwsli, "
            "min(product_issue at time zone 'UTC'), "
            "max(product_issue at time zone 'UTC'), "
            "min(issue at time zone 'UTC') as min_issue from warnings "
            "WHERE wfo = %s and eventid = %s and significance = %s and "
            "phenomena = %s and ((updated > %s and updated <= %s) "
            "or expire > %s) and status not in ('UPG', 'CAN') "
            "GROUP by tablename, hvtec_nwsli ORDER by tablename DESC ",
            (
                vtec.office,
                vtec.etn,
                vtec.significance,
                vtec.phenomena,
                prod.valid - timedelta(days=offset),
                prod.valid,
                prod.valid,
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
                        return int(row["tablename"].replace("warnings_", ""))
            # We likely have a flood warning and can use the HVTEC NWSLI
            # to resolve ambiguity
            hvtec_nwsli = segment.get_hvtec_nwsli()
            if hvtec_nwsli:
                for row in rows:
                    if hvtec_nwsli == row["hvtec_nwsli"]:
                        return int(row["tablename"].replace("warnings_", ""))

            prod.warnings.append(
                f"VTEC {vtec} product: {prod.get_product_id()} "
                f"returned {txn.rowcount} rows when searching "
                "for current table"
            )
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
            return int(row["tablename"].replace("warnings_", ""))

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
                "ugc": row[0],
                "status": row[1],
                "year": vtec.year,
                "phenomena": vtec.phenomena,
                "significance": vtec.significance,
                "etn": vtec.etn,
                "updated": row[2],
                "expire": row[3],
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

    for _key, combo in combos.items():
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
        if bsu.startswith("IMPACT"):
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


def _debug_warning(prod, txn, warning_table, vtec, segment, ets):
    """Get a more useful warning message for this failure"""
    cnt = txn.rowcount
    txn.execute(
        "SELECT ugc, issue at time zone 'UTC' as utc_issue, "
        "expire at time zone 'UTC' as utc_expire, "
        "updated at time zone 'UTC' as utc_updated, "
        f"status from {warning_table} WHERE wfo = %s and eventid = %s and "
        "ugc in %s and significance = %s and phenomena = %s "
        "ORDER by ugc ASC, issue ASC",
        (
            vtec.office,
            vtec.etn,
            segment.get_ugcs_tuple(),
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
        f"Warning: {vtec.s3()} do_sql_vtec {warning_table} {vtec.action} "
        f"updated {cnt} row, should {len(segment.ugcs)} rows\n"
        f"UGCS: {segment.ugcs}\n"
        f"valid: {prod.valid} expire: {ets}\n{debugmsg}"
    )


def _resent_match(prod, txn, warning_table, vtec):
    """Check if this is a resent match."""
    txn.execute(
        f"SELECT max(updated) as maxtime from {warning_table} "
        "WHERE eventid = %s and significance = %s and wfo = %s and "
        "phenomena = %s",
        (vtec.etn, vtec.significance, vtec.office, vtec.phenomena),
    )
    maxtime = txn.fetchone()["maxtime"]
    if maxtime is not None and maxtime == prod.valid:
        LOG.warning(
            "RESENT Match, skipping SQL for %s!", prod.get_product_id()
        )
        return True
    return False


def _do_sql_vtec_new(prod, txn, warning_table, segment, vtec):
    """Do the NEW style actions."""
    bts = prod.valid if vtec.begints is None else vtec.begints
    # If this product has no expiration time, but db needs a value
    ets = vtec.endts
    if vtec.endts is None:
        ets = bts + DEFAULT_EXPIRE_DELTA

    fcster = prod.get_signature()
    if fcster is not None:
        fcster = fcster[:24]

    # For each UGC code in this segment, we create a database entry
    for ugc in segment.ugcs:
        # Check to see if we have entries already for this UGC
        # Some previous entries may not be in a terminated state, so
        # also check the expiration time
        txn.execute(
            f"SELECT issue, expire, updated from {warning_table} "
            "WHERE ugc = %s and eventid = %s and significance = %s "
            "and wfo = %s and phenomena = %s and "
            "status not in ('CAN', 'UPG') and expire > %s",
            (
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
                    f"DELETE from {warning_table} WHERE ugc = %s "
                    "and eventid = %s and significance = %s and "
                    "wfo = %s and phenomena = %s and "
                    "status in ('NEW', 'EXB', 'EXA') ",
                    (
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

        txn.execute(
            f"INSERT into {warning_table} (issue, expire, updated, "
            "wfo, eventid, status, fcster, report, ugc, phenomena, "
            "significance, gid, init_expire, product_issue, "
            "hvtec_nwsli, hvtec_severity, hvtec_cause, hvtec_record, "
            "is_emergency, is_pds) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
            "get_gid(%s, %s, %s), %s, %s, %s, %s, %s, %s, %s, %s) "
            "RETURNING gid",
            (
                bts,
                ets,
                prod.valid,
                vtec.office,
                vtec.etn,
                vtec.action,
                fcster,
                prod.unixtext,
                str(ugc),
                vtec.phenomena,
                vtec.significance,
                str(ugc),
                prod.valid,
                vtec.phenomena == "FW",
                ets,
                prod.valid,
                segment.get_hvtec_nwsli(),
                segment.get_hvtec_severity(),
                segment.get_hvtec_cause(),
                segment.get_hvtec_record(),
                segment.is_emergency,
                segment.is_pds,
            ),
        )
        # For unit tests, these mostly get filtered out
        if txn.fetchone().get("gid") is None:
            prod.warnings.append(
                f"get_gid({str(ugc)}, {prod.valid}, {vtec.phenomena == 'FW'}) "
                "was null"
            )


def _do_sql_vtec_cor(prod, txn, warning_table, segment, vtec):
    """A Product Correction."""
    # For corrections, we only update the SVS and updated
    txn.execute(
        f"UPDATE {warning_table} SET "
        "svs = (CASE WHEN (svs IS NULL) THEN '__' ELSE svs END) "
        "|| %s || '__', updated = %s WHERE wfo = %s and "
        f"eventid = %s and ugc in %s and significance = %s "
        "and phenomena = %s and (expire + '1 hour'::interval) >= %s ",
        (
            prod.unixtext,
            prod.valid,
            vtec.office,
            vtec.etn,
            segment.get_ugcs_tuple(),
            vtec.significance,
            vtec.phenomena,
            prod.valid,
        ),
    )
    if txn.rowcount != len(segment.ugcs):
        prod.warnings.append(
            _debug_warning(prod, txn, warning_table, vtec, segment, vtec.endts)
        )


def _do_sql_vtec_can(prod, txn, warning_table, segment, vtec):
    """A Product Correction."""
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
        f"UPDATE {warning_table} SET {issuesql} expire = %s, "
        "status = %s, updated = %s, "
        "svs = (CASE WHEN (svs IS NULL) THEN '__' ELSE svs END) "
        "|| %s || '__' WHERE wfo = %s and eventid = %s and ugc in "
        f"%s and significance = %s and phenomena = %s "
        "and status not in ('CAN', 'UPG') and "
        "(expire + '1 hour'::interval) >= %s",
        (
            ets,
            vtec.action,
            prod.valid,
            prod.unixtext,
            vtec.office,
            vtec.etn,
            segment.get_ugcs_tuple(),
            vtec.significance,
            vtec.phenomena,
            prod.valid,
        ),
    )
    if txn.rowcount != len(segment.ugcs):
        if not prod.is_correction():
            prod.warnings.append(
                _debug_warning(prod, txn, warning_table, vtec, segment, ets)
            )


def _do_sql_vtec_con(prod, txn, warning_table, segment, vtec):
    """Continue."""
    # These are no-ops, just updates
    ets = vtec.endts
    if vtec.endts is None:
        ets = prod.valid + DEFAULT_EXPIRE_DELTA

    # Offices have 1 hour to expire something :), actually 30 minutes
    txn.execute(
        f"UPDATE {warning_table} SET status = %s, updated = %s, "
        "svs = (CASE WHEN (svs IS NULL) THEN '__' ELSE svs END) "
        "|| %s || '__' , expire = %s, "
        "is_emergency = (case when %s then true else is_emergency end), "
        "is_pds = (case when %s then true else is_pds end) "
        f"WHERE wfo = %s and eventid = %s and ugc in %s "
        "and significance = %s and phenomena = %s and "
        "status not in ('CAN', 'UPG') and "
        "(expire + '1 hour'::interval) >= %s",
        (
            vtec.action,
            prod.valid,
            prod.unixtext,
            ets,
            segment.is_emergency,
            segment.is_pds,
            vtec.office,
            vtec.etn,
            segment.get_ugcs_tuple(),
            vtec.significance,
            vtec.phenomena,
            prod.valid,
        ),
    )
    if txn.rowcount != len(segment.ugcs):
        prod.warnings.append(
            _debug_warning(prod, txn, warning_table, vtec, segment, ets)
        )
