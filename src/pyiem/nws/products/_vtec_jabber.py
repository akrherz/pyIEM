"""Consolidate VTEC to jabber logic."""

from datetime import timedelta
from typing import TYPE_CHECKING

from pyiem.nws.ugc import ugcs_to_text
from pyiem.nws.vtec import VTEC, get_action_string, get_ps_string
from pyiem.reference import TWEET_CHARS

if TYPE_CHECKING:
    from pyiem.nws.products.vtec import VTECProduct


def build_channels(prod: "VTECProduct", segment, vtec: VTEC) -> list:
    """Build a list of channels for the given segment/vtec."""
    ps = f"{vtec.phenomena}.{vtec.significance}"
    channels = []
    # Noisey products that don't default to the main WFO channel
    if prod.afos[:3] == "RFW" or (
        prod.afos[:3] == "MWW" and vtec.phenomena in ("SC", "GL", "MF", "SE")
    ):
        channels.append(f"{prod.afos[:3]}{prod.source[1:]}")
    else:
        channels.append(prod.source[1:])
    # GH604 - Append a -ACTION for CON, EXP, CAN actions
    suffix = f"-{vtec.action}" if vtec.action in ["CON", "EXP", "CAN"] else ""
    if vtec.action not in ["EXP", "CAN"] and segment.damagetag is not None:
        channels.append(f"{ps}.{segment.damagetag}")
    channels.append(f"{vtec.s2()}{suffix}")
    channels.append(prod.afos)
    channels.append(f"{prod.afos[:3]}...")
    channels.append(f"{ps}.{vtec.office}{suffix}")
    # Tsunami Warning, Watch is a special case
    if vtec.phenomena == "TS":
        for ugc in segment.ugcs:
            for wfo in prod.ugc_provider[ugc].wfos:
                if wfo not in channels:
                    channels.append(wfo)
    for ugc in segment.ugcs:
        # per state channels
        candidate = f"{ps}.{ugc.state}{suffix}"
        if candidate not in channels:
            channels.append(candidate)
        channels.append(f"{ps}.{str(ugc)}{suffix}")
        channels.append(str(ugc))
    return channels


def _get_action(prod: "VTECProduct") -> str:
    """How to describe the action of this product"""
    actions = set()
    for segment in prod.segments:
        for vtec in segment.vtec:
            actions.add(vtec.action)
    if len(actions) == 1:
        return get_action_string(actions.pop())
    return "updates"


def _ulabel(ugcs):
    """What to call all these ugcs..."""
    states = []
    types = []
    for ugc in [str(u) for u in ugcs]:
        if ugc[:2] not in states:
            states.append(ugc[:2])
        if ugc[2] not in types:
            types.append(ugc[2])

    res = f"area{'s' if len(ugcs) > 1 else ''}"
    if len(types) == 1 and types[0] == "Z":
        res = f"zone{'s' if len(ugcs) > 1 else ''}"
    if len(types) == 1 and types[0] == "C":
        if len(states) == 1 and states[0] == "LA":
            res = f"parish{'es' if len(ugcs) > 1 else ''}"
        else:
            res = f"count{'ies' if len(ugcs) > 1 else 'y'}"
    return res


def _get_jabbers(
    prod: "VTECProduct", uri: str, river_uri: str | None = None
) -> list[tuple[str, str, dict]]:
    """Return a list of triples representing how this goes to social

    Returns:
    [[plain, html, xtra]] -- A list of triples of plain text, html, xtra
    """
    wfo = prod.source[1:]
    if prod.is_skip_con():
        xtra = {
            "product_id": prod.get_product_id(),
            "channels": ",".join(prod.get_affected_wfos()) + f",FLS{wfo}",
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

    wfo4 = wfo if prod.source.startswith("K") else prod.source
    msgs = []
    actions = {}

    for segment in prod.segments:
        for vtec_index, vtec in enumerate(segment.vtec):
            if vtec.action in ["ROU", "UPG"] or vtec.status == "T":
                continue
            linkyear = vtec.year if vtec.year is not None else prod.valid.year
            xtra = {
                "product_id": prod.get_product_id(),
                "channels": ",".join(build_channels(prod, segment, vtec)),
                "status": vtec.status,
                "vtec": vtec.get_id(prod.valid.year),
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
            # collect up ugcs against VTEC actions
            action_key = f"{vtec.action}.{vtec.phenomena}.{vtec.significance}"
            actions.setdefault(action_key, []).extend(segment.ugcs)
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
                "url": f"{uri}{vtec.url(prod.valid.year)}",
            }
            if vtec_index > 0 and segment.vtec[vtec_index - 1].action == "UPG":
                vtec_last = segment.vtec[vtec_index - 1]
                ps_last = get_ps_string(
                    vtec_last.phenomena, vtec_last.significance
                )
                jmsg_dict["product"] = (
                    f"upgrades {ps_last} to "
                    f"{get_ps_string(vtec.phenomena, vtec.significance)}"
                )
            if segment.hvtec and segment.hvtec[0].nwsli.id != "00000":
                jmsg_dict["county"] = segment.hvtec[0].nwsli.get_name()
            if vtec.begints is not None:
                jmsg_dict["url"] += f"_{vtec.begints:%Y-%m-%dT%H:%MZ}"
                xtra["twitter_media"] += vtec.begints.strftime(
                    "%Y-%m-%d%%20%H%M"
                )
                if vtec.begints > (prod.utcnow + timedelta(hours=1)):
                    jmsg_dict["sts"] = f" {vtec.get_begin_string(prod)} "
            else:
                jmsg_dict["url"] += f"_{prod.valid:%Y-%m-%dT%H:%MZ}"
                xtra["twitter_media"] += prod.valid.strftime(
                    "%Y-%m-%d%%20%H%M"
                )
            xtra["twitter_media"] += "::_r:86.png"
            jmsg_dict["ets"] = vtec.get_end_string(prod)

            # Include the special bulletin for Tornado Warnings
            if vtec.phenomena == "TO" and vtec.significance == "W":
                jmsg_dict["svs_special"] = segment.svs_search()
                jmsg_dict["svs_special_html"] = segment.svs_search()

            # PDS
            if segment.is_pds:
                jmsg_dict["product"] += " (PDS)"
                xtra["channels"] += f",{vtec.phenomena}.PDS"

            # Emergencies
            if segment.is_emergency:
                jmsg_dict["product"] = (
                    jmsg_dict["product"]
                    .replace("Warning", "Emergency")
                    .replace(" (PDS)", "")
                )
                xtra["channels"] += f",{vtec.phenomena}.EMERGENCY"
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
                    prod.warnings.append(
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
                    "https://water.noaa.gov/resources/hydrographs/"
                    f"{hvtec_nwsli.lower()}_hg.png"
                )
            msgs.append(
                [" ".join(plain.split()), " ".join(html.split()), xtra]
            )
    # We only want to consolidate in the case of a homogeneous product
    if prod.is_homogeneous() and len(msgs) > 1:
        vtec = prod.get_first_non_cancel_vtec()
        if vtec is None:
            vtec = prod.segments[0].vtec[0]
        segment = prod.get_first_non_cancel_segment()
        if segment is None:
            segment = prod.segments[0]
        # Enforce the check
        starts = []
        ends = []
        for seg in prod.segments:
            for v in seg.vtec:
                if v.status not in ["EXP", "CAN"]:
                    if v.begints not in starts:
                        starts.append(v.begints)
                    if v.endts not in ends:
                        ends.append(v.endts)
        constant_start_stop = len(starts) == 1 and len(ends) == 1
        channels = build_channels(prod, segment, vtec)
        # Need to figure out a timestamp to associate with this
        # consolidated message.  Default to utcnow
        stamp = prod.utcnow
        for seg in prod.segments:
            for v in seg.vtec:
                if (
                    v.begints is not None
                    and v.begints > stamp
                    and v.status not in ["CAN", "EXP"]
                ):
                    stamp = v.begints
            if seg != segment:
                for ugc in seg.ugcs:
                    channels.append(
                        f"{vtec.phenomena}.{vtec.significance}.{str(ugc)}"
                    )
                    channels.append(str(ugc))
        if any(seg.is_emergency for seg in prod.segments):
            channels.append(f"{vtec.phenomena}.EMERGENCY")
        if any(seg.is_pds for seg in prod.segments):
            channels.append(f"{vtec.phenomena}.PDS")
        xtra["channels"] = ",".join(channels)
        short_actions = []
        long_actions = []
        html_long_actions = []
        psextra = f" {get_ps_string(vtec.phenomena, vtec.significance)}"
        for s3, ugcs in actions.items():
            (va, vp, vs) = s3.split(".")
            if va == "UPG":
                continue
            this_psextra = f" {get_ps_string(vp, vs)}"
            if this_psextra == psextra:
                this_psextra = ""
            long_actions.append(
                f"{get_action_string(va)}{this_psextra} {ugcs_to_text(ugcs)}"
            )
            html_long_actions.append(
                "<span style='font-weight: bold;'>"
                f"{get_action_string(va)}{this_psextra}</span> "
                f"{ugcs_to_text(ugcs)}"
            )
            short_actions.append(
                f"{get_action_string(va)}{this_psextra} "
                f"{len(ugcs)} {_ulabel(ugcs)}"
            )
        if len(short_actions) == 1:
            _, ugcs = list(actions.items())[0]
            long_actions = [
                ugcs_to_text(ugcs),
            ]
            html_long_actions = [
                ugcs_to_text(ugcs),
            ]
            short_actions = [
                f"{len(ugcs)} {_ulabel(ugcs)}",
            ]

        jdict = {
            "as": ", ".join(short_actions),
            "asl": ", ".join(long_actions),
            "hasl": ", ".join(html_long_actions),
            "wfo": vtec.office,
            "ets": vtec.get_end_string(prod),
            "svr_special": segment.special_tags_to_text(),
            "svs_special": "",
            "sts": "",
            "action": _get_action(prod),
            "product": vtec.get_ps_string(),
            "url": (
                f"{uri}{vtec.url(prod.valid.year)}_{stamp:%Y-%m-%dT%H:%MZ}"
            ),
        }

        # Include the special bulletin for Tornado Warnings
        if vtec.phenomena in ["TO"] and vtec.significance == "W":
            jdict["svs_special"] = segment.svs_search()
        if vtec.begints is not None and vtec.begints > (
            prod.utcnow + timedelta(hours=1)
        ):
            jdict["sts"] = f" {vtec.get_begin_string(prod)} "
        if not constant_start_stop:
            jdict["ets"] = ""
            jdict["sts"] = ""

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
                "%(wfo)s %(action)s %(product)s%(sts)s (%(as)s) %(ets)s"
            ) % jdict
            if len(xtra["twitter"]) > (TWEET_CHARS - 25):
                xtra["twitter"] = (
                    "%(wfo)s %(action)s %(product)s%(sts)s %(ets)s"
                ) % jdict
        xtra["twitter"] += " %(url)s" % jdict
        html = (
            '<p>%(wfo)s <a href="%(url)s">%(action)s %(product)s</a>'
            "%(svr_special)s%(sts)s "
            "(%(hasl)s) %(ets)s. %(svs_special)s</p>"
        ) % jdict
        return [(" ".join(plain.split()), " ".join(html.split()), xtra)]

    return msgs
