"""
Utility functions that generate HTML.
"""

from pyiem.network import Table as NetworkTable


def station_select(
    network, selected, name, select_all=False, only_online=False
) -> str:
    """Select a station from a given network.

    Args:
      network (str): IEM Network identifier.
      selected (str): The option value to flag as selected.
      name (str): The HTML select name attribute.
      select_all (bool): Add an option with key of `_ALL`.
      only_online (bool): Include stations in the network that are online only,
        default is `False`.

    Returns
    -------
      html_string
    """
    nt = NetworkTable(network, only_online=only_online)
    ar = {}
    for sid in nt.sts:
        meta = nt.sts[sid]
        ab = "" if meta["archive_begin"] is None else meta["archive_begin"]
        ae = "now" if meta["archive_end"] is None else meta["archive_end"]
        ar[sid] = f"{meta['name']} [{ab} till {ae}]"
    if select_all:
        ar["_ALL"] = " -- All Sites --"
    return make_select(name, selected, ar, cssclass="iemselect2")


def make_select(
    name,
    selected,
    data,
    jscallback=None,
    cssclass=None,
    multiple=False,
    showvalue=True,
) -> str:
    """Generate a HTML select element.

    The trick here is what ``data`` looks like. The basic form is a ``dict``.
    You can get ``optgroup`` by having the dictionary keys be additional
    lists or dicts.

    Args:
      name (str): The select name attribute to assign.
      selected (mixed): The option value that should be set to selected.
      data (dict): The structure to build our select from.
      jscallback (str): javascript to place in the ``onChange`` attribute.
      cssclass (str): CSS class to assign to the select element.
      showvalue (bool): Should option label be prepended by key label.

    Returns
    -------
      html_string
    """
    if not isinstance(selected, (list, tuple)):
        selected = [selected]
    s = '<select name="%s"%s%s%s>\n' % (
        name,
        (
            ""
            if jscallback is None
            else f' onChange="{jscallback}(this.value)"'
        ),
        "" if cssclass is None else f' class="{cssclass}"',
        "" if not multiple else " MULTIPLE",
    )
    for key, val in data.items():
        if isinstance(val, (tuple, list)):
            val = dict(list(zip(val, val, strict=False)))
        if not isinstance(val, dict):  # simple
            s += '<option value="%s"%s>%s%s</option>\n' % (
                key,
                ' selected="selected"' if key in selected else "",
                f"[{key}] " if showvalue else "",
                val,
            )
            continue
        s += f'<optgroup label="{key}">\n'
        for key2, val2 in val.items():
            s += '<option value="%s"%s>%s%s</option>\n' % (
                key2,
                ' selected="selected"' if key2 in selected else "",
                f"[{key2}] " if showvalue else "",
                val2,
            )
        s += "</optgroup>\n"
    s += "</select>\n"
    return s
