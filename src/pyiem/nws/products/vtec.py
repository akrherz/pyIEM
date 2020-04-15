"""A NWS TextProduct that contains VTEC information
"""
# Standard Library Imports
import datetime
import itertools

from pyiem.nws.product import TextProduct, TextProductException
from pyiem.nws.ugc import ugcs_to_text
from pyiem.reference import TWEET_CHARS
from pyiem.nws.products._vtec_util import (
    _resent_match,
    _do_sql_vtec_new,
    _do_sql_vtec_cor,
    _do_sql_vtec_can,
    _do_sql_vtec_con,
)

# When a VTEC product has an infinity time 000000T0000Z, we need some value
# for the database to make things logically work.  We arb pick 21 days, which
# seems to be enough time to ensure a WFO issues some followup statement.
DEFAULT_EXPIRE_DELTA = datetime.timedelta(hours=(21 * 24))


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


class VTECProductException(TextProductException):
    """ Something we can raise when bad things happen! """


class VTECProduct(TextProduct):
    """ A TextProduct that contains VTEC information. """

    def __init__(
        self, text, utcnow=None, ugc_provider=None, nwsli_provider=None
    ):
        """ constructor """
        # Make sure we are CRLF above all else
        if text.find("\r\r\n") == -1:
            text = text.replace("\n", "\r\r\n")
        #  Get rid of extraneous whitespace on right hand side only
        text = "\r\r\n".join([a.rstrip() for a in text.split("\r\r\n")])

        TextProduct.__init__(self, text, utcnow, ugc_provider, nwsli_provider)
        # Which time partitioned table does this product belong to
        # defaults to current UTC valid
        self.db_year = self.valid.year
        self.skip_con = self.get_skip_con()

    def debug_warning(self, txn, warning_table, vtec, segment, ets):
        """ Get a more useful warning message for this failure """
        cnt = txn.rowcount
        txn.execute(
            "SELECT ugc, issue at time zone 'UTC' as utc_issue, "
            "expire at time zone 'UTC' as utc_expire, "
            "updated at time zone 'UTC' as utc_updated, "
            f"status from {warning_table} WHERE wfo = %s and eventid = %s "
            f"and ugc in %s and significance = %s "
            "and phenomena = %s ORDER by ugc ASC, issue ASC",
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
            if val is None:
                return "%-16s" % ("((NULL))",)
            return val.strftime("%Y-%m-%d %H:%M")

        for row in txn.fetchall():
            debugmsg += "%s %s %s %s %s\n" % (
                row["ugc"],
                row["status"],
                myfmt(row["utc_issue"]),
                myfmt(row["utc_expire"]),
                myfmt(row["utc_updated"]),
            )
        return (
            f"Warning: {vtec.s3()} do_sql_vtec {warning_table} {vtec.action} "
            f"updated {cnt} row, should {len(segment.ugcs)} rows\n"
            f"UGCS: {segment.ugcs}\n"
            f"valid: {self.valid} expire: {ets}\n{debugmsg}"
        )

    def sql(self, txn):
        """Persist to the database

        Args:
          txn (psycopg2.transaction): A database transaction object that we can
            exec() database calls against.

        """
        for segment in self.segments:
            if len(segment.vtec) > 1 and check_dup_ps(segment):
                self.warnings.append(
                    "Segment has duplicated VTEC for a "
                    "single phenomena / significance"
                )
            if segment.giswkt and not segment.vtec:
                if self.afos[:3] not in ["MWS"]:
                    self.warnings.append(
                        "Product segment has LAT...LON, "
                        "but does not have VTEC?"
                    )
            if not segment.ugcs and segment.vtec:
                self.warnings.append(
                    "UGC is missing for segment " "that has VTEC!"
                )
                continue
            if not segment.ugcs:
                continue
            if not segment.vtec:
                continue
            for vtec in segment.vtec:
                if vtec.status == "T" or vtec.action == "ROU":
                    continue
                # Send all products to the SBW method in case this segment
                # should of had a polygon and did not.
                warning_table = self.which_warning_table(txn, segment, vtec)
                self.do_sbw_geometry(
                    txn,
                    segment,
                    vtec,
                    warning_table.replace("warnings_", "sbw_"),
                )
                # Check for Hydro-VTEC stuff
                if segment.hvtec and segment.hvtec[0].nwsli != "00000":
                    do_sql_hvtec(txn, segment)

                self.do_sql_vtec(txn, segment, vtec, warning_table)

    def which_warning_table(self, txn, segment, vtec):
        """ Figure out which table we should work against """
        if vtec.action in ["NEW"]:
            table = f"warnings_{self.db_year}"
            # Lets piggyback a check to see if this ETN has been reused?
            # Can this realiably be done?
            txn.execute(
                f"SELECT max(updated) from {table} WHERE wfo = %s and "
                "eventid = %s and significance = %s and phenomena = %s",
                (vtec.office, vtec.etn, vtec.significance, vtec.phenomena),
            )
            row = txn.fetchone()
            if row["max"] is not None:
                if (self.valid - row["max"]).total_seconds() > (21 * 86400):
                    self.warnings.append(
                        "Possible Duplicated ETN\n"
                        f"  max(updated) is {row['max']}, "
                        f"prod.valid is {self.valid}\n  table is {table}\n"
                        f"  VTEC: {str(vtec)}\n  "
                        f"product_id: {self.get_product_id()}"
                    )
            return table
        # Lets query the database to look for any matching entries within
        # the past 3, 10, 31 days, to find with the product_issue was,
        # which guides the table that the data is stored within
        for offset in [3, 10, 31]:
            txn.execute(
                "SELECT tableoid::regclass as tablename, hvtec_nwsli, "
                "min(product_issue at time zone 'UTC'), "
                "max(product_issue at time zone 'UTC') from warnings "
                "WHERE wfo = %s and eventid = %s and significance = %s and "
                "phenomena = %s and ((updated > %s and updated <= %s) "
                "or expire > %s) and status not in ('UPG', 'CAN') "
                "GROUP by tablename, hvtec_nwsli ORDER by tablename DESC ",
                (
                    vtec.office,
                    vtec.etn,
                    vtec.significance,
                    vtec.phenomena,
                    self.valid - datetime.timedelta(days=offset),
                    self.valid,
                    self.valid,
                ),
            )
            rows = txn.fetchall()
            if not rows:
                continue
            if len(rows) > 1:
                # We likely have a flood warning and can use the HVTEC NWSLI
                # to resolve ambiguity
                hvtec_nwsli = segment.get_hvtec_nwsli()
                if hvtec_nwsli:
                    for row in rows:
                        if hvtec_nwsli == row["hvtec_nwsli"]:
                            return row["tablename"]

                self.warnings.append(
                    (
                        "VTEC %s product: %s returned %s rows when "
                        "searching for current table"
                    )
                    % (str(vtec), self.get_product_id(), txn.rowcount)
                )
            row = rows[0]
            if row["min"] is not None:
                year = row["min"].year
                if row["max"].year != year:
                    print(
                        "VTEC Product appears to cross 1 Jan UTC "
                        f"minyear: {year} maxyear: {row['max'].year} "
                        f"VTEC: {str(vtec)} productid: {self.get_product_id()}"
                    )
                self.db_year = int(row["tablename"].replace("warnings_", ""))
                return row["tablename"]

        # Give up
        table = f"warnings_{self.db_year}"
        if not self.is_correction():
            self.warnings.append(
                "Failed to find year of product issuance:\n"
                f"  VTEC:{str(vtec)}\n  PRODUCT: {self.get_product_id()}\n"
                f"  defaulting to use table: {table}\n"
                f"  {list_rows(txn, table, vtec)}"
            )
        return table

    def do_sql_vtec(self, txn, segment, vtec, warning_table):
        """ Persist the non-SBW stuff to the database

        Arguments:
        txn -- A pyscopg2 transaction
        segment -- A TextProductSegment instance
        vtec -- A vtec instance
        """
        # If this product is ...RESENT, lets check to make sure we did not
        # already get it
        if self.is_resent() and _resent_match(self, txn, warning_table, vtec):
            return

        if vtec.action in ["NEW", "EXB", "EXA"]:
            _do_sql_vtec_new(self, txn, warning_table, segment, vtec)

        elif vtec.action in ["COR"]:
            _do_sql_vtec_cor(self, txn, warning_table, segment, vtec)

        elif vtec.action in ["CAN", "UPG", "EXT"]:
            _do_sql_vtec_can(self, txn, warning_table, segment, vtec)

        elif vtec.action in ["CON", "EXP", "ROU"]:
            _do_sql_vtec_con(self, txn, warning_table, segment, vtec)

        else:
            self.warnings.append(
                f"do_sql_vtec() encountered {vtec.action} VTEC status"
            )

    def do_sbw_geometry(self, txn, segment, vtec, sbw_table):
        """Storage of Storm Based Warning geometry

        The IEM uses a seperate table for the Storm Based Warning geometries.

        Args:
          txn (psycopg2): Database transaction/cursor
          segment (TextProduct.TextProductSegment): Segment
          vtec (pyiem.vtec.VTEC): VTEC instance
        """
        # The following time columns are set in the database
        # issue         - VTEC encoded issuance time, can be null
        # init_expire   - VTEC encoded expiration
        # expire        - VTEC encoded expiration
        # polygon_begin - Time domain this polygon is valid for inclusive
        # polygon_end   - Time domain this polygon is valid for exclusive
        # updated       - Product time of this product

        # Figure out when this polygon begins and ends
        polygon_begin = self.valid
        if vtec.action == "NEW" and vtec.begints is not None:
            polygon_begin = vtec.begints
        polygon_end = self.valid
        if vtec.action not in ["CAN", "UPG"]:
            if vtec.endts is not None:
                polygon_end = vtec.endts
            else:
                polygon_end = self.valid + DEFAULT_EXPIRE_DELTA

        if segment.sbw and self.is_correction() and vtec.action == "NEW":
            # Go delete the previous NEW polygon
            txn.execute(
                f"DELETE from {sbw_table} WHERE status = 'NEW' and "
                "eventid = %s and wfo = %s and phenomena = %s and "
                "significance = %s",
                (vtec.etn, vtec.office, vtec.phenomena, vtec.significance),
            )
            if txn.rowcount != 1:
                self.warnings.append(
                    f"{vtec.s3()} product is a correction, but SBW delete "
                    f"removed {txn.rowcount} rows instead of 1"
                )

        # Lets go find the initial warning (status == NEW)
        txn.execute(
            "SELECT issue, expire, st_astext(geom) as giswkt "
            f"from {sbw_table} WHERE status = 'NEW' and "
            "eventid = %s and wfo = %s and phenomena = %s "
            "and significance = %s",
            (vtec.etn, vtec.office, vtec.phenomena, vtec.significance),
        )
        if txn.rowcount > 0:
            if not segment.sbw:
                self.warnings.append(
                    f"{vtec.s3()} should have contained a polygon and did not."
                )
                if (
                    self.is_homogeneous()
                    and vtec.action == "CAN"
                    and self.is_single_action()
                ):
                    self.warnings.append(
                        f"{vtec.s3()} adding polygon from issuance to product"
                    )
                    segment.giswkt = "SRID=4326;%s" % (txn.fetchone()[2],)
            if vtec.action == "NEW":  # Uh-oh, we have a duplicate
                self.warnings.append(
                    f"{vtec.s3()} is a SBW duplicate! {txn.rowcount} "
                    "other row(s) found."
                )
        # We are done with our piggybacked checks :(  akrherz/pyIEM#203
        if segment.giswkt is None:
            return

        # Lets go find our current active polygon
        txn.execute(
            f"SELECT polygon_end from {sbw_table} WHERE eventid = %s and "
            "wfo = %s and phenomena = %s and significance = %s and "
            "polygon_begin != polygon_end ORDER by updated DESC LIMIT 1",
            (vtec.etn, vtec.office, vtec.phenomena, vtec.significance),
        )
        current = None
        if txn.rowcount == 0 and vtec.action != "NEW":
            self.warnings.append(
                f"{sbw_table} searched for {vtec.s3()} and no results found"
            )
        if txn.rowcount > 0:
            current = txn.fetchone()

        # If ncessary, lets find the current active polygon and truncate it
        # to when our new polygon starts
        if vtec.action != "NEW" and current is not None:
            txn.execute(
                (
                    f"UPDATE {sbw_table} SET polygon_end = %s WHERE "
                    "eventid = %s and wfo = %s and phenomena = %s "
                    "and significance = %s and polygon_end != polygon_begin "
                    "and polygon_end = %s and status != 'CAN'"
                ),
                (
                    polygon_begin,
                    vtec.etn,
                    vtec.office,
                    vtec.phenomena,
                    vtec.significance,
                    current["polygon_end"],
                ),
            )
            if txn.rowcount != 1:
                self.warnings.append(
                    f"{vtec.s3()} SBW prev polygon update resulted in update "
                    f"of {txn.rowcount} rows, should be 1"
                )

        # Prepare the TIME...MOT...LOC information
        tml_valid = None
        tml_column = "tml_geom"
        if segment.tml_giswkt and segment.tml_giswkt.find("LINE") > 0:
            tml_column = "tml_geom_line"
        if segment.tml_valid:
            tml_valid = segment.tml_valid

        # OK, ready to insert away!
        sql = (
            f"INSERT into {sbw_table} (wfo, eventid, "
            "significance, phenomena, issue, expire, init_expire, "
            "polygon_begin, polygon_end, geom, status, report, windtag, "
            "hailtag, tornadotag, tornadodamagetag, tml_valid, "
            f"tml_direction, tml_sknt, {tml_column}, updated, "
            "waterspouttag, is_emergency, is_pds, floodtag_heavyrain, "
            "floodtag_flashflood, floodtag_damage, floodtag_leeve, "
            "floodtag_dam, hvtec_nwsli) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, "
            "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
        )
        myargs = (
            vtec.office,
            vtec.etn,
            vtec.significance,
            vtec.phenomena,
            vtec.begints,
            vtec.endts if vtec.endts is not None else polygon_end,
            vtec.endts if vtec.endts is not None else polygon_end,
            polygon_begin,  # polygon_begin
            polygon_end,  # polygon_end
            segment.giswkt,
            vtec.action,
            self.unixtext,
            segment.windtag,
            segment.hailtag,
            segment.tornadotag,
            segment.tornadodamagetag,
            tml_valid,
            segment.tml_dir,
            segment.tml_sknt,
            segment.tml_giswkt,
            self.valid,
            segment.waterspouttag,
            segment.is_emergency,
            segment.is_pds,
            segment.flood_tags.get("EXPECTED RAINFALL"),
            segment.flood_tags.get("FLASH FLOOD"),
            segment.flood_tags.get("FLASH FLOOD DAMAGE THREAT"),
            segment.flood_tags.get("LEVEE FAILURE"),
            segment.flood_tags.get("DAM FAILURE"),
            segment.get_hvtec_nwsli(),
        )
        txn.execute(sql, myargs)
        if txn.rowcount != 1:
            self.warnings.append(
                f"{vtec.s3()} sbw table insert "
                f"resulted in {txn.rowcount} rows, should be 1"
            )

        # If this is a CAN, UPG action and single purpose, update expiration
        if vtec.action in ["CAN", "UPG"] and self.is_single_action():
            txn.execute(
                (
                    f"UPDATE {sbw_table} SET expire = %s WHERE wfo = %s and "
                    "phenomena = %s and significance = %s and eventid = %s "
                    "and expire >= %s "
                ),
                (
                    self.valid,
                    vtec.office,
                    vtec.phenomena,
                    vtec.significance,
                    vtec.etn,
                    self.valid,
                ),
            )
            if txn.rowcount == 0:
                self.warnings.append(
                    f"{vtec.s3()} sbw CAN,UPG update "
                    f"resulted in 0 rows updated, valid: {self.valid}"
                )

    def is_single_action(self):
        """Is this product just 1 VTEC action?"""
        keys = []
        for segment in self.segments:
            for vtec in segment.vtec:
                keys.append(vtec.action)
        return len(keys) == 1

    def get_action(self):
        """ How to describe the action of this product """
        keys = []
        for segment in self.segments:
            for vtec in segment.vtec:
                if vtec.action not in keys:
                    keys.append(vtec.action)
        if len(keys) == 1:
            return self.segments[0].vtec[0].get_action_string()
        return "updates"

    def is_homogeneous(self):
        """ Test to see if this product contains just one VTEC event """
        keys = []
        for segment in self.segments:
            for vtec in segment.vtec:
                key = vtec.s3()
                if key not in keys:
                    keys.append(key)

        return len(keys) == 1

    def get_first_non_cancel_vtec(self):
        """ Return the first non-CANcel VTEC """
        for segment in self.segments:
            for vtec in segment.vtec:
                if vtec.action != "CAN":
                    return vtec
        return None

    def get_first_non_cancel_segment(self):
        """ Return the first segment that is a non-CAN """
        for segment in self.segments:
            if segment.vtec and segment.vtec[0].action != "CAN":
                return segment
        return None

    def get_jabbers(self, uri, river_uri=None):
        """Return a list of triples representing how this goes to social
        Arguments:
        uri -- The URL for the VTEC Browser
        river_uri -- The URL of the River App

        Returns:
        [[plain, html, xtra]] -- A list of triples of plain text, html, xtra
        """
        wfo = self.source[1:]
        if self.skip_con:
            xtra = {
                "product_id": self.get_product_id(),
                "channels": ",".join(self.get_affected_wfos()) + ",FLS" + wfo,
                "twitter": ("%s issues updated FLS product %s?wfo=%s")
                % (wfo, river_uri, wfo),
            }
            text = (
                f"{wfo} has sent an updated FLS product (continued products "
                "were not reported here).  Consult this website for more "
                f"details. {river_uri}?wfo={wfo}"
            )
            html = (
                "<p>%s has sent an updated FLS product "
                "(continued products were not reported here).  Consult "
                '<a href="%s?wfo=%s">this website</a> for more '
                "details.</p>"
            ) % (wfo, river_uri, wfo)
            return [(text, html, xtra)]
        msgs = []

        actions = []
        long_actions = []
        html_long_actions = []

        for segment in self.segments:
            for vtec in segment.vtec:
                if vtec.action == "ROU" or vtec.status == "T":
                    continue
                # CRITICAL: redefine this for each loop as it gets passed by
                # reference below and is subsequently overwritten otherwise!
                if self.afos[:3] in ["MWW", "RFW"]:
                    channels = [
                        "%s%s" % (self.afos[:3], s)
                        for s in self.get_affected_wfos()
                    ]
                else:
                    channels = self.get_affected_wfos()
                channels.append(vtec.s2())
                channels.append(self.afos)
                channels.append("%s..." % (self.afos[:3],))
                channels.append(
                    f"{vtec.phenomena}.{vtec.significance}.{vtec.office}"
                )
                for ugc in segment.ugcs:
                    # per state channels
                    candidate = "%s.%s.%s" % (
                        vtec.phenomena,
                        vtec.significance,
                        ugc.state,
                    )
                    if candidate not in channels:
                        channels.append(candidate)
                    channels.append(
                        "%s.%s.%s"
                        % (vtec.phenomena, vtec.significance, str(ugc))
                    )
                    channels.append(str(ugc))
                xtra = {
                    "product_id": self.get_product_id(),
                    "channels": ",".join(channels),
                    "status": vtec.status,
                    "vtec": vtec.get_id(self.db_year),
                    "ptype": vtec.phenomena,
                    "twitter": "",
                }

                long_actions.append(
                    f"{vtec.get_action_string()} {ugcs_to_text(segment.ugcs)}"
                )
                html_long_actions.append(
                    ("<span style='font-weight: bold;'>" "%s</span> %s")
                    % (vtec.get_action_string(), ugcs_to_text(segment.ugcs))
                )
                actions.append(
                    "%s %s area%s"
                    % (
                        vtec.get_action_string(),
                        len(segment.ugcs),
                        "s" if len(segment.ugcs) > 1 else "",
                    )
                )

                if segment.giswkt is not None:
                    xtra["category"] = "SBW"
                    xtra["geometry"] = segment.giswkt.replace("SRID=4326;", "")
                if vtec.endts is not None:
                    xtra["expire"] = vtec.endts.strftime("%Y%m%dT%H:%M:00")
                # Set up Jabber Dict for stuff to fill in
                jmsg_dict = {
                    "wfo": vtec.office,
                    "product": vtec.product_string(),
                    "county": ugcs_to_text(segment.ugcs),
                    "sts": " ",
                    "ets": " ",
                    "svr_special": segment.special_tags_to_text(),
                    "svs_special": "",
                    "svs_special_html": "",
                    "year": self.db_year,
                    "phenomena": vtec.phenomena,
                    "eventid": vtec.etn,
                    "significance": vtec.significance,
                    "url": "%s%s" % (uri, vtec.url(self.db_year)),
                }
                if segment.hvtec and segment.hvtec[0].nwsli.id != "00000":
                    jmsg_dict["county"] = segment.hvtec[0].nwsli.get_name()
                if vtec.begints is not None:
                    jmsg_dict["url"] += "_%s" % (
                        vtec.begints.strftime("%Y-%m-%dT%H:%MZ"),
                    )
                    if vtec.begints > (
                        self.utcnow + datetime.timedelta(hours=1)
                    ):
                        jmsg_dict["sts"] = " %s " % (
                            vtec.get_begin_string(self),
                        )
                else:
                    jmsg_dict["url"] += "_%s" % (
                        self.utcnow.strftime("%Y-%m-%dT%H:%MZ"),
                    )
                jmsg_dict["ets"] = vtec.get_end_string(self)

                # Include the special bulletin for Tornado Warnings
                if vtec.phenomena == "TO" and vtec.significance == "W":
                    jmsg_dict["svs_special"] = segment.svs_search()
                    jmsg_dict["svs_special_html"] = segment.svs_search()

                # PDS
                if segment.is_pds:
                    jmsg_dict["product"] += " (PDS)"
                    channels.append(f"{vtec.phenomena}.PDS")
                    xtra["channels"] += ",%s" % (channels[-1],)

                # Emergencies
                if segment.is_emergency:
                    jmsg_dict["product"] = (
                        jmsg_dict["product"]
                        .replace("Warning", "Emergency")
                        .replace(" (PDS)", "")
                    )
                    channels.append(f"{vtec.phenomena}.EMERGENCY")
                    xtra["channels"] += ",%s" % (channels[-1],)
                    _btext = segment.svs_search()
                    if vtec.phenomena == "FF":
                        jmsg_dict["svs_special"] = _btext
                        jmsg_dict["svs_special_html"] = _btext.replace(
                            "FLASH FLOOD EMERGENCY",
                            (
                                '<span style="color: #FF0000;">'
                                "FLASH FLOOD EMERGENCY</span>"
                            ),
                        )
                    elif vtec.phenomena == "TO":
                        jmsg_dict["svs_special_html"] = _btext.replace(
                            "TORNADO EMERGENCY",
                            (
                                '<span style="color: #FF0000;">'
                                "TORNADO EMERGENCY</span>"
                            ),
                        )
                    else:
                        self.warnings.append(
                            "Segment is_emergency, but not TO,FF phenomena?"
                        )

                plain = (
                    "%(wfo)s %(product)s %(svr_special)s%(sts)s for "
                    "%(county)s %(ets)s %(svs_special)s "
                    "%(url)s"
                ) % jmsg_dict
                html = (
                    '<p>%(wfo)s <a href="%(url)s">%(product)s</a> '
                    "%(svr_special)s%(sts)s for %(county)s "
                    "%(ets)s %(svs_special_html)s</p>"
                ) % jmsg_dict
                xtra["twitter"] = (
                    "%(wfo)s %(product)s%(svr_special)s%(sts)sfor %(county)s "
                    "%(ets)s %(url)s"
                ) % jmsg_dict
                # brute force removal of duplicate spaces
                xtra["twitter"] = " ".join(xtra["twitter"].split())
                msgs.append(
                    [" ".join(plain.split()), " ".join(html.split()), xtra]
                )

        # If we have a homogeneous product and we have more than one
        # message, lets try to condense it down, some of the xtra settings
        # from above will be used here, this is probably bad design
        if self.is_homogeneous() and len(msgs) > 1:
            vtec = self.get_first_non_cancel_vtec()
            if vtec is None:
                vtec = self.segments[0].vtec[0]
            segment = self.get_first_non_cancel_segment()
            if segment is None:
                segment = self.segments[0]
            if self.afos[:3] in ["MWW", "RFW"]:
                channels = [
                    "%s%s" % (self.afos[:3], s)
                    for s in self.get_affected_wfos()
                ]
            else:
                channels = self.get_affected_wfos()
            channels.append(vtec.s2())
            channels.append(self.afos)
            channels.append(
                "%s.%s.%s" % (vtec.phenomena, vtec.significance, vtec.office)
            )
            # Need to figure out a timestamp to associate with this
            # consolidated message.  Default to utcnow
            stamp = self.utcnow
            for seg in self.segments:
                for v in seg.vtec:
                    if (
                        v.begints is not None
                        and v.begints > stamp
                        and v.status not in ["CAN", "EXP"]
                    ):
                        stamp = v.begints
                for ugc in seg.ugcs:
                    channels.append(
                        "%s.%s.%s"
                        % (vtec.phenomena, vtec.significance, str(ugc))
                    )
                    channels.append(str(ugc))
            if any([seg.is_emergency for seg in self.segments]):
                channels.append(f"{vtec.phenomena}.EMERGENCY")
            if any([seg.is_pds for seg in self.segments]):
                channels.append(f"{vtec.phenomena}.PDS")
            xtra["channels"] = ",".join(channels)
            jdict = {
                "as": ", ".join(actions),
                "asl": ", ".join(long_actions),
                "hasl": ", ".join(html_long_actions),
                "wfo": vtec.office,
                "ets": vtec.get_end_string(self),
                "svr_special": segment.special_tags_to_text(),
                "svs_special": "",
                "sts": "",
                "action": self.get_action(),
                "product": vtec.get_ps_string(),
                "url": "%s%s_%s"
                % (
                    uri,
                    vtec.url(self.db_year),
                    stamp.strftime("%Y-%m-%dT%H:%MZ"),
                ),
            }
            # Include the special bulletin for Tornado Warnings
            if vtec.phenomena in ["TO"] and vtec.significance == "W":
                jdict["svs_special"] = segment.svs_search()
            if vtec.begints is not None and vtec.begints > (
                self.utcnow + datetime.timedelta(hours=1)
            ):
                jdict["sts"] = " %s " % (vtec.get_begin_string(self),)

            plain = (
                "%(wfo)s %(action)s %(product)s%(svr_special)s"
                "%(sts)s (%(asl)s) %(ets)s. %(svs_special)s %(url)s"
            ) % jdict
            xtra["twitter"] = (
                "%(wfo)s %(action)s %(product)s"
                "%(svr_special)s%(sts)s (%(asl)s) "
                "%(ets)s"
            ) % jdict
            # 25 is an aggressive reservation for URLs, which may not be needed
            if len(xtra["twitter"]) > (TWEET_CHARS - 25):
                xtra["twitter"] = (
                    "%(wfo)s %(action)s %(product)s%(sts)s " "(%(as)s) %(ets)s"
                ) % jdict
                if len(xtra["twitter"]) > (TWEET_CHARS - 25):
                    xtra["twitter"] = (
                        "%(wfo)s %(action)s %(product)s%(sts)s " "%(ets)s"
                    ) % jdict
            xtra["twitter"] += " %(url)s" % jdict
            html = (
                '<p>%(wfo)s <a href="%(url)s">%(action)s %(product)s</a>'
                "%(svr_special)s%(sts)s "
                "(%(hasl)s) %(ets)s. %(svs_special)s</p>"
            ) % jdict
            return [(" ".join(plain.split()), " ".join(html.split()), xtra)]

        return msgs

    def get_skip_con(self):
        """ Should this product be skipped from generating jabber messages"""
        if self.afos[:3] == "FLS" and len(self.segments) > 4:
            return True
        return False


def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    """ Helper function that actually converts the raw text and emits an
    VTECProduct instance or returns an exception"""
    prod = VTECProduct(
        text,
        utcnow=utcnow,
        ugc_provider=ugc_provider,
        nwsli_provider=nwsli_provider,
    )
    return prod
