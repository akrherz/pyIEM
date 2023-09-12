"""A NWS TextProduct that contains VTEC information."""

from pyiem.nws.product import TextProduct, TextProductException
from pyiem.nws.products._vtec_jabber import _get_jabbers
from pyiem.nws.products._vtec_util import (
    DEFAULT_EXPIRE_DELTA,
    _associate_vtec_year,
    _check_unique_ugc,
    _check_vtec_polygon,
    _do_sql_vtec_can,
    _do_sql_vtec_con,
    _do_sql_vtec_cor,
    _do_sql_vtec_new,
    _load_database_status,
    _resent_match,
    check_dup_ps,
    do_sql_hvtec,
)


class VTECProductException(TextProductException):
    """Something we can raise when bad things happen!"""


class VTECProduct(TextProduct):
    """A TextProduct that contains VTEC information."""

    get_jabbers = _get_jabbers

    def __init__(
        self, text, utcnow=None, ugc_provider=None, nwsli_provider=None
    ):
        """constructor"""
        # Make sure we are CRLF above all else
        if text.find("\r\r\n") == -1:
            text = text.replace("\n", "\r\r\n")
        #  Get rid of extraneous whitespace on right hand side only
        text = "\r\r\n".join([a.rstrip() for a in text.split("\r\r\n")])

        TextProduct.__init__(self, text, utcnow, ugc_provider, nwsli_provider)
        self.skip_con = self.get_skip_con()
        # If there was no/bad MND header, a backwards way to know is that the
        # product time zone will be None, add a warning
        if self.z is None:
            self.warnings.append("Could not find local timezone in text.")
        # Special check for truncated TSUs
        if (
            self.afos is not None
            and self.afos.startswith("TSU")
            and self.unixtext.find("$$") == -1
        ):
            raise ValueError("Aborting processing of TSU without $$")
        # Arb checks
        _check_unique_ugc(self)
        _check_vtec_polygon(self)

    def sql(self, txn):
        """Persist to the database

        Args:
          txn (psycopg.transaction): A database transaction object that we can
            exec() database calls against.

        """
        # Associate a year to each VTEC found in the product, this informs
        # which database table to use
        _associate_vtec_year(self, txn)
        # Build a pandas dataframe to track what we are doing here.
        dbdf = _load_database_status(txn, self)
        dbdf["missed"] = True

        for segment in self.segments:
            if len(segment.vtec) > 1 and check_dup_ps(segment):
                self.warnings.append(
                    "Segment has duplicated VTEC for a "
                    "single phenomena / significance"
                )
            if segment.giswkt and not segment.vtec:
                if self.afos is not None and self.afos[:3] not in ["MWS"]:
                    self.warnings.append(
                        "Product segment has LAT...LON, "
                        "but does not have VTEC?"
                    )
            if not segment.ugcs and segment.vtec:
                self.warnings.append(
                    "UGC is missing for segment that has VTEC!"
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
                self.do_sbw_geometry(txn, segment, vtec)
                # Check for Hydro-VTEC stuff
                if segment.hvtec and segment.hvtec[0].nwsli != "00000":
                    do_sql_hvtec(txn, segment)

                self.do_sql_vtec(txn, segment, vtec)
                if dbdf.empty:
                    continue
                for ugc in segment.ugcs:
                    dbdf.loc[
                        (dbdf["ugc"] == str(ugc))
                        & (dbdf["phenomena"] == vtec.phenomena)
                        & (dbdf["significance"] == vtec.significance)
                        & (dbdf["etn"] == vtec.etn)
                        & (dbdf["year"] == vtec.year),
                        "missed",
                    ] = False
        if dbdf.empty:
            return
        df = dbdf[dbdf["missed"]]
        # Tropical and Earthquake products with ETNs over 1000 are too complex
        # to check in this manner, I suppose an office could issue 1000 SVRs,
        # but alas.  See akrherz/pyIEM#316
        if df.empty or df["etn"].min() >= 1000:
            return
        self.warnings.append(f"Product failed to cover all UGC\n{df}")

    def do_sql_vtec(self, txn, segment, vtec):
        """Persist the non-SBW stuff to the database

        Arguments:
        txn -- A psycopg transaction
        segment -- A TextProductSegment instance
        vtec -- A vtec instance
        """
        warning_table = f"warnings_{vtec.year}"
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

    def do_sbw_geometry(self, txn, segment, vtec):
        """Storage of Storm Based Warning geometry

        The IEM uses a seperate table for the Storm Based Warning geometries.

        Args:
          txn (psycopg): Database transaction/cursor
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

        sbw_table = f"sbw_{vtec.year}"
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
                    segment.giswkt = f"SRID=4326;{txn.fetchone()['giswkt']}"
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
            "hailtag, tornadotag, damagetag, "
            f"tml_valid, tml_direction, tml_sknt, {tml_column}, updated, "
            "waterspouttag, is_emergency, is_pds, floodtag_heavyrain, "
            "floodtag_flashflood, floodtag_damage, floodtag_leeve, "
            "floodtag_dam, hvtec_nwsli, hvtec_severity, hvtec_cause, "
            "hvtec_record, windthreat, hailthreat, squalltag) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,"
            "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
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
            segment.damagetag,
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
            segment.get_hvtec_severity(),
            segment.get_hvtec_cause(),
            segment.get_hvtec_record(),
            segment.windthreat,
            segment.hailthreat,
            segment.squalltag,
        )
        txn.execute(sql, myargs)

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

    def is_homogeneous(self):
        """Test to see if this product contains just one VTEC event"""
        keys = []
        for segment in self.segments:
            for vtec in segment.vtec:
                # Upgrades do not count in this calculation
                if vtec.action == "UPG":
                    continue
                key = vtec.s3()
                if key not in keys:
                    keys.append(key)
        return len(keys) == 1

    def get_first_non_cancel_vtec(self):
        """Return the first non-CANcel VTEC"""
        for segment in self.segments:
            for vtec in segment.vtec:
                if vtec.action != "CAN":
                    return vtec
        return None

    def get_first_non_cancel_segment(self):
        """Return the first segment that is a non-CAN"""
        for segment in self.segments:
            if segment.vtec and segment.vtec[0].action != "CAN":
                return segment
        return None

    def get_skip_con(self):
        """Should this product be skipped from generating jabber messages"""
        if (
            self.afos is not None
            and self.afos[:3] == "FLS"
            and len(self.segments) > 4
        ):
            return True
        return False


def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    """Helper function that actually converts the raw text and emits an
    VTECProduct instance or returns an exception"""
    prod = VTECProduct(
        text,
        utcnow=utcnow,
        ugc_provider=ugc_provider,
        nwsli_provider=nwsli_provider,
    )
    return prod
