"""A NWS TextProduct that contains VTEC information."""
# Standard Library Imports
from datetime import timedelta

from pyiem.nws.product import TextProduct, TextProductException
from pyiem.nws.ugc import ugcs_to_text
from pyiem.reference import TWEET_CHARS
from pyiem.nws.products._vtec_util import (
    _associate_vtec_year,
    _check_unique_ugc,
    _resent_match,
    _do_sql_vtec_new,
    _do_sql_vtec_cor,
    _do_sql_vtec_can,
    _do_sql_vtec_con,
    DEFAULT_EXPIRE_DELTA,
    check_dup_ps,
    do_sql_hvtec,
    _load_database_status,
)


class VTECProductException(TextProductException):
    """Something we can raise when bad things happen!"""


class VTECProduct(TextProduct):
    """A TextProduct that contains VTEC information."""

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

    def sql(self, txn):
        """Persist to the database

        Args:
          txn (psycopg2.transaction): A database transaction object that we can
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
        txn -- A pyscopg2 transaction
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
                    segment.giswkt = f"SRID=4326;{txn.fetchone()[2]}"
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
            "hvtec_record, windthreat, hailthreat) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,"
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

    def get_action(self):
        """How to describe the action of this product"""
        keys = []
        for segment in self.segments:
            for vtec in segment.vtec:
                if vtec.action not in keys:
                    keys.append(vtec.action)
        if len(keys) == 1:
            return self.segments[0].vtec[0].get_action_string()
        return "updates"

    def is_homogeneous(self):
        """Test to see if this product contains just one VTEC event"""
        keys = []
        for segment in self.segments:
            for vtec in segment.vtec:
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

    def get_jabbers(self, uri, river_uri=None):
        """Return a list of triples representing how this goes to social
        Arguments:
        uri -- The URL for the VTEC Browser
        river_uri -- The URL of the River App

        Returns:
        [[plain, html, xtra]] -- A list of triples of plain text, html, xtra
        """
        wfo = self.source[1:]
        wfo4 = wfo if self.source.startswith("K") else self.source
        if self.skip_con:
            xtra = {
                "product_id": self.get_product_id(),
                "channels": ",".join(self.get_affected_wfos()) + ",FLS" + wfo,
                "twitter": (
                    f"{wfo} issues updated FLS product {river_uri}?wfo={wfo}"
                ),
            }
            text = (
                f"{wfo} has sent an updated FLS product (continued products "
                "were not reported here).  Consult this website for more "
                f"details. {river_uri}?wfo={wfo}"
            )
            html = (
                f"<p>{wfo} has sent an updated FLS product "
                "(continued products were not reported here).  Consult "
                f'<a href="{river_uri}?wfo={wfo}">this website</a> for more '
                "details.</p>"
            )
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
                        f"{self.afos[:3]}{s}" for s in self.get_affected_wfos()
                    ]
                else:
                    channels = self.get_affected_wfos()
                channels.append(vtec.s2())
                channels.append(self.afos)
                channels.append(f"{self.afos[:3]}...")
                channels.append(
                    f"{vtec.phenomena}.{vtec.significance}.{vtec.office}"
                )
                for ugc in segment.ugcs:
                    # per state channels
                    candidate = (
                        f"{vtec.phenomena}.{vtec.significance}.{ugc.state}"
                    )
                    if candidate not in channels:
                        channels.append(candidate)
                    channels.append(
                        f"{vtec.phenomena}.{vtec.significance}.{str(ugc)}"
                    )
                    channels.append(str(ugc))
                linkyear = (
                    vtec.year if vtec.year is not None else self.valid.year
                )
                xtra = {
                    "product_id": self.get_product_id(),
                    "channels": ",".join(channels),
                    "status": vtec.status,
                    "vtec": vtec.get_id(self.valid.year),
                    "ptype": vtec.phenomena,
                    "twitter": "",
                    "twitter_media": (
                        "https://mesonet.agron.iastate.edu/plotting/auto/plot/"
                        f"208/network:WFO::wfo:{wfo4}::"
                        f"year:{linkyear}::phenomenav:{vtec.phenomena}::"
                        f"significancev:{vtec.significance}::"
                        f"etn:{vtec.etn}::valid:"
                    ),
                }

                long_actions.append(
                    f"{vtec.get_action_string()} {ugcs_to_text(segment.ugcs)}"
                )
                html_long_actions.append(
                    "<span style='font-weight: bold;'>"
                    f"{vtec.get_action_string()}</span> "
                    f"{ugcs_to_text(segment.ugcs)}"
                )
                actions.append(
                    f"{vtec.get_action_string()} {len(segment.ugcs)} area"
                    f"{'s' if len(segment.ugcs) > 1 else ''}"
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
                    "year": linkyear,
                    "phenomena": vtec.phenomena,
                    "eventid": vtec.etn,
                    "significance": vtec.significance,
                    "url": f"{uri}{vtec.url(self.valid.year)}",
                }
                if segment.hvtec and segment.hvtec[0].nwsli.id != "00000":
                    jmsg_dict["county"] = segment.hvtec[0].nwsli.get_name()
                if vtec.begints is not None:
                    jmsg_dict["url"] += f"_{vtec.begints:%Y-%m-%dT%H:%MZ}"
                    xtra["twitter_media"] += vtec.begints.strftime(
                        "%Y-%m-%d%%20%H%M"
                    )
                    if vtec.begints > (self.utcnow + timedelta(hours=1)):
                        jmsg_dict["sts"] = f" {vtec.get_begin_string(self)} "
                else:
                    jmsg_dict["url"] += f"_{self.valid:%Y-%m-%dT%H:%MZ}"
                    xtra["twitter_media"] += self.valid.strftime(
                        "%Y-%m-%d%%20%H%M"
                    )
                xtra["twitter_media"] += ".png"
                jmsg_dict["ets"] = vtec.get_end_string(self)

                # Include the special bulletin for Tornado Warnings
                if vtec.phenomena == "TO" and vtec.significance == "W":
                    jmsg_dict["svs_special"] = segment.svs_search()
                    jmsg_dict["svs_special_html"] = segment.svs_search()

                # PDS
                if segment.is_pds:
                    jmsg_dict["product"] += " (PDS)"
                    channels.append(f"{vtec.phenomena}.PDS")
                    xtra["channels"] += f",{channels[-1]}"

                # Emergencies
                if segment.is_emergency:
                    jmsg_dict["product"] = (
                        jmsg_dict["product"]
                        .replace("Warning", "Emergency")
                        .replace(" (PDS)", "")
                    )
                    channels.append(f"{vtec.phenomena}.EMERGENCY")
                    xtra["channels"] += f",{channels[-1]}"
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
                hvtec_nwsli = segment.get_hvtec_nwsli()
                if hvtec_nwsli is not None and hvtec_nwsli != "00000":
                    xtra["twitter_media"] = (
                        "https://water.weather.gov/resources/hydrographs/"
                        f"{hvtec_nwsli.lower()}_hg.png"
                    )
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
                    f"{self.afos[:3]}{s}" for s in self.get_affected_wfos()
                ]
            else:
                channels = self.get_affected_wfos()
            channels.append(vtec.s2())
            channels.append(self.afos)
            channels.append(
                f"{vtec.phenomena}.{vtec.significance}.{vtec.office}"
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
                        f"{vtec.phenomena}.{vtec.significance}.{str(ugc)}"
                    )
                    channels.append(str(ugc))
            if any(seg.is_emergency for seg in self.segments):
                channels.append(f"{vtec.phenomena}.EMERGENCY")
            if any(seg.is_pds for seg in self.segments):
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
                "url": (
                    f"{uri}{vtec.url(self.valid.year)}_{stamp:%Y-%m-%dT%H:%MZ}"
                ),
            }
            # Include the special bulletin for Tornado Warnings
            if vtec.phenomena in ["TO"] and vtec.significance == "W":
                jdict["svs_special"] = segment.svs_search()
            if vtec.begints is not None and vtec.begints > (
                self.utcnow + timedelta(hours=1)
            ):
                jdict["sts"] = f" {vtec.get_begin_string(self)} "

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
