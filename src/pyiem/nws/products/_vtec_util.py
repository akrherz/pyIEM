"""Off-loaded private stuff from `vtec.py`."""
# pylint: disable=too-many-arguments
import datetime
import itertools

# When a VTEC product has an infinity time 000000T0000Z, we need some value
# for the database to make things logically work.  We arb pick 21 days, which
# seems to be enough time to ensure a WFO issues some followup statement.
DEFAULT_EXPIRE_DELTA = datetime.timedelta(hours=(21 * 24))


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

    for key in combos:
        if len(combos[key]) == 1:
            continue
        for one, two in itertools.permutations(combos[key], 2):
            # We check for overlap
            if one[0] >= two[0] and one[0] < two[1]:
                return True
    return False


def do_sql_hvtec(txn, segment):
    """ Process the HVTEC in this product """
    nwsli = segment.hvtec[0].nwsli.id
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
        if bsu.startswith("IMPACT..."):
            impact_text = bullet.strip()[9:]

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
    """ Get a more useful warning message for this failure """
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
        """ Be more careful """
        default = "%-16s" % ("((NULL))",)
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
        print(f"RESENT Match, skipping SQL for {prod.get_product_id()}!")
        return True
    return False


def _do_sql_vtec_new(prod, txn, warning_table, segment, vtec):
    """ Do the NEW style actions."""
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
            "hvtec_nwsli, is_emergency, is_pds) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
            "get_gid(%s, %s), %s, %s, %s, %s, %s) RETURNING gid",
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
                ets,
                prod.valid,
                segment.get_hvtec_nwsli(),
                segment.is_emergency,
                segment.is_pds,
            ),
        )
        # For unit tests, these mostly get filtered out
        if txn.fetchone().get("gid") is None:
            prod.warnings.append(f"get_gid({str(ugc)},{prod.valid}) was null")


def _do_sql_vtec_cor(prod, txn, warning_table, segment, vtec):
    """A Product Correction."""
    # A previous issued product is being corrected
    txn.execute(
        f"UPDATE {warning_table} SET "
        "expire = coalesce(%s, expire), status = %s, "
        "svs = (CASE WHEN (svs IS NULL) THEN '__' ELSE svs END) "
        "|| %s || '__', issue = coalesce(%s, issue), "
        "init_expire = coalesce(%s, init_expire) WHERE wfo = %s and "
        f"eventid = %s and ugc in %s and significance = %s "
        "and phenomena = %s and (expire + '1 hour'::interval) >= %s ",
        (
            vtec.endts,
            vtec.action,
            prod.unixtext,
            vtec.begints,
            vtec.endts,
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
        issuesql = " issue = '%s', " % (vtec.begints,)
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
