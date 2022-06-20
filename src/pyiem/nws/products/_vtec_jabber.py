"""Consolidate VTEC to jabber logic."""
# Standard Library Imports
from datetime import timedelta

# Third Party
import pandas as pd

# Local
from pyiem.nws.ugc import ugcs_to_text
from pyiem.nws.vtec import get_action_string
from pyiem.reference import TWEET_CHARS


def build_channels(prod, segment, vtec) -> list:
    """Build a list of channels for the given segment/vtec."""
    channels = []
    # Two noisey products that don't default to the main WFO channel
    if prod.afos[:3] in ["MWW", "RFW"]:
        channels.append(f"{prod.afos[:3]}{prod.source[1:]}")
    else:
        channels.append(prod.source[1:])
    # GH604 - Append a -ACTION for CON, EXP, CAN actions
    suffix = f"-{vtec.action}" if vtec.action in ["CON", "EXP", "CAN"] else ""
    channels.append(f"{vtec.s2()}{suffix}")
    channels.append(prod.afos)
    channels.append(f"{prod.afos[:3]}...")
    channels.append(
        f"{vtec.phenomena}.{vtec.significance}.{vtec.office}{suffix}"
    )
    for ugc in segment.ugcs:
        # per state channels
        candidate = f"{vtec.phenomena}.{vtec.significance}.{ugc.state}{suffix}"
        if candidate not in channels:
            channels.append(candidate)
        channels.append(
            f"{vtec.phenomena}.{vtec.significance}.{str(ugc)}{suffix}"
        )
        channels.append(str(ugc))
    return channels


def _get_action(df: pd.DataFrame) -> str:
    """How to describe the action of this product"""
    if df.action.unique().size == 1:
        return get_action_string(df.action.iloc[0])
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


def build_df(prod):
    """Build a dataframe for the given product."""
    rows = []
    for segment in prod.segments:
        for vtec in segment.vtec:
            for ugc in segment.ugcs:
                entry = [
                    str(ugc),
                    vtec.phenomena,
                    vtec.significance,
                    vtec.action,
                    vtec.etn,
                ]
                rows.append(entry)
    df = pd.DataFrame(
        rows,
        columns=["ugc", "phenomena", "significance", "action", "etn"],
    )
    return df


def _get_jabbers(prod, uri, river_uri=None):
    """Return a list of triples representing how this goes to social
    Arguments:
    uri -- The URL for the VTEC Browser
    river_uri -- The URL of the River App

    Returns:
    [[plain, html, xtra]] -- A list of triples of plain text, html, xtra
    """
    df = build_df(prod)
    wfo = prod.source[1:]
    wfo4 = wfo if prod.source.startswith("K") else prod.source
    if prod.skip_con:
        xtra = {
            "product_id": prod.get_product_id(),
            "channels": ",".join(prod.get_affected_wfos()) + ",FLS" + wfo,
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

    actions = {}

    for segment in prod.segments:
        for vtec in segment.vtec:
            if vtec.action == "ROU" or vtec.status == "T":
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
            (actions.setdefault(vtec.action, []).extend(segment.ugcs))
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
            xtra["twitter_media"] += ".png"
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
                    "https://water.weather.gov/resources/hydrographs/"
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
        for va, ugcs in actions.items():
            long_actions.append(
                f"{get_action_string(va)} {ugcs_to_text(ugcs)}"
            )
            html_long_actions.append(
                "<span style='font-weight: bold;'>"
                f"{get_action_string(va)}</span> "
                f"{ugcs_to_text(ugcs)}"
            )
            short_actions.append(
                f"{get_action_string(va)} {len(ugcs)} {_ulabel(ugcs)}"
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
            "action": _get_action(df),
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
