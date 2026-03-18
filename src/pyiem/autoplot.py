"""Content from util for IEM Autoplot work."""

import re
from datetime import date, datetime, timedelta
from html import escape

from pyiem.exceptions import IncompleteWebRequest, UnknownStationException
from pyiem.network import Table as NetworkTable
from pyiem.reference import state_names

WFO_FOURCHAR = ["AFG", "GUM", "AFG", "HFO", "AFC", "AJK"]


def _handle_date_err(exp, value, fmt):
    """Attempt to fix up a date string, when possible."""
    if "day" not in str(exp) and "range" not in str(exp):
        raise exp
    tokens = value.split(" ")
    datepart = tokens[0]
    (yyyy, mm, _dd) = datepart.split("-")
    # construct a new month date and then substract one day
    lastday = (date(int(yyyy), int(mm), 15) + timedelta(days=20)).replace(
        day=1
    ) - timedelta(days=1)
    # Reconstruct the date string
    res = lastday.strftime("%Y-%m-%d")
    if len(tokens) > 1:
        res += " " + tokens[1]
    # Careful here, we don't want a recursive loop
    return _strptime(res, fmt, rectify=False)


def _strptime(ins: str, fmt: str, rectify: bool = False) -> datetime:
    """Wrapper around strptime."""
    # Forgive an encoded space
    ins = ins.replace("+", " ")
    try:
        return datetime.strptime(ins, fmt)
    except ValueError as exp:
        if rectify:
            return _handle_date_err(exp, ins, fmt)
        raise IncompleteWebRequest(
            f"String provided: `{ins}` does not match format: `{fmt}`"
        ) from exp


def _float(val):
    """Convert string to float, if possible."""
    try:
        return float(val)
    except ValueError as exp:
        raise IncompleteWebRequest(f"Invalid float value: {val}") from exp


def _text_handler(value: str, pattern: str, default: str) -> str:
    """Handle text type with pattern."""
    if not re.match(pattern, value):
        return default
    return value


def _station_handler(
    value: str, opt: dict, name: str, fdict: dict, ctx: dict, default: str
) -> str:
    """Handle station."""
    # A bit of hackery here if we have a name ending in a number
    _n = name[-1] if name[-1] in ["1", "2", "3", "4", "5"] else ""
    netname = f"network{_n}"
    # The network variable tags along and within a non-PHP context,
    # this variable is unset, so we do some more hackery here
    ctx[netname] = fdict.get(netname, opt.get("network"))
    # Convience we load up the network metadata
    ntname = f"_nt{_n}"

    ctx[ntname] = NetworkTable(ctx[netname], only_online=False)
    # stations starting with _ are virtual and should not error
    if value is None:
        value = default
    if not value.startswith("_") and value not in ctx[ntname].sts:
        # HACK for three/four char ugliness
        if ctx[netname] == "WFO" and value in WFO_FOURCHAR:
            value = f"P{value}"
        elif ctx[netname] == "WFO" and value in ["JSJ", "SJU"]:
            value = "TJSJ"
        else:
            raise UnknownStationException("Unknown station provided.")
    # A helper to remove downstream boilerplate
    sname = ctx[ntname].sts.get(value, {"name": f"(({value}))"})["name"]
    ctx[f"_sname{_n}"] = f"[{value}] {sname}"
    return value


def _cmap_handler(value: str, default: str) -> str:
    """Handle colormap."""
    # Ensure that our value is a valid colormap known to matplotlib
    import matplotlib

    if value not in matplotlib.colormaps:
        value = default
    return value


def _select_handler(value: str, opt: dict, default: str) -> str:
    """Handle select type options."""
    options = opt.get("options", {})
    # Allow for legacy variable aliases
    alias = opt.get("alias", {})
    # in case of multi, value could be a list
    if value is None:
        value = default
    elif isinstance(value, str):
        if value in alias:
            value = alias[value]
        if value not in options:
            value = default
        if opt.get("multiple"):
            value = [value]
    else:
        newvalue = []
        for subval in value:
            if subval in alias:
                subval = alias[subval]
            if subval in options:
                newvalue.append(subval)
        value = newvalue
    return value


def _datetime_handler(
    value: str | None,
    default: str | None,
    minval: str | None,
    maxval: str | None,
    **kwargs,
) -> tuple[str | None, str | None, str | None, str | None]:
    """Handle datetime type options."""
    # tricky here, php has YYYY/mm/dd and CGI has YYYY-mm-dd
    if value is not None and value.strip() == "":
        value = default
    if default is not None:
        default = _strptime(default, "%Y/%m/%d %H%M")
    if minval is not None:
        minval = _strptime(minval, "%Y/%m/%d %H%M")
    if maxval is not None:
        maxval = _strptime(maxval, "%Y/%m/%d %H%M")
    if value is not None:
        # A common problem is for the space to be missing
        if value.find(" ") == -1:
            if len(value) == 14:
                value = f"{value[:10]} {value[10:]}"
            else:
                value += " 0000"
        value = _strptime(
            value[:15].replace("/", "-"),
            "%Y-%m-%d %H%M",
            rectify=kwargs.get("rectify_dates", False),
        )
    return value, minval, maxval, default


def _sday_handler(
    value: str, default: str | None, minval: str | None, maxval: str | None
) -> tuple[str | None, str | None, str | None, str | None]:
    """Handle sday type options."""
    # supports legacy uris with yyyy-mm-dd, before migration to sday
    if default is not None:
        default = _strptime(f"2000{default}", "%Y%m%d").date()
    if minval is not None:
        minval = _strptime(f"2000{minval}", "%Y%m%d").date()
    if maxval is not None:
        maxval = _strptime(f"2000{maxval}", "%Y%m%d").date()
    if value is not None:
        if value.find("-") > -1:
            value = _strptime(value, "%Y-%m-%d").date()
        else:
            value = _strptime(f"2000{value}", "%Y%m%d").date()
    return value, minval, maxval, default


def _date_handler(
    value: str,
    default: str | None,
    minval: str | None,
    maxval: str | None,
    **kwargs,
) -> tuple[str | None, str | None, str | None, str | None]:
    # tricky here, php has YYYY/mm/dd and CGI has YYYY-mm-dd
    if default is not None:
        default = _strptime(default, "%Y/%m/%d").date()
    if minval is not None:
        minval = _strptime(minval, "%Y/%m/%d").date()
    if maxval is not None:
        maxval = _strptime(maxval, "%Y/%m/%d").date()
    if value is not None:
        value = _strptime(
            value,
            "%Y-%m-%d",
            rectify=kwargs.get("rectify_dates", False),
        ).date()
    return value, minval, maxval, default


def _vtec_ps_handler(
    name: str, default: str | None, optional: bool, fdict: dict, ctx: dict
):
    # VTEC phenomena and significance
    defaults = {}
    # Only set a default value when the field is not optional
    if default is not None and not optional:
        tokens = default.split(".")
        if len(tokens) == 2 and len(tokens[0]) == 2 and len(tokens[1]) == 1:
            defaults["phenomena"] = tokens[0]
            defaults["significance"] = tokens[1]
    for label in ["phenomena", "significance"]:
        label2 = label + name
        ctx[label2] = fdict.get(label2, defaults.get(label))
        # Prevent empty strings from being set
        if ctx[label2] is not None and ctx[label2] == "":
            ctx[label2] = defaults.get(label)


def _process_option(
    opt: dict, fdict: dict, ctx: dict, enforce_optional: bool, **kwargs
):
    """Process an option dictionary and update the context accordingly."""
    name = opt.get("name")
    default = opt.get("default")
    typ: str = opt.get("type")
    minval = opt.get("min")
    maxval = opt.get("max")
    optional: bool = opt.get("optional", False)
    value: str | None = fdict.get(name)
    # vtec_ps is special since we have special logic to get its value
    if (
        optional
        and typ != "vtec_ps"
        and (
            value is None
            or (enforce_optional and fdict.get(f"_opt_{name}") != "on")
        )
    ):
        return
    if typ == "vtec_ps":
        _vtec_ps_handler(name, default, optional, fdict, ctx)
        return

    if typ == "text":
        value = _text_handler(value or "", opt.get("pattern", ".*"), default)
    elif typ in ["station", "zstation", "sid", "networkselect"]:
        value = _station_handler(value or "", opt, name, fdict, ctx, default)
    elif typ == "cmap":
        value = _cmap_handler(value or "", default)
    elif typ in ["int", "month", "zhour", "hour", "day", "year"]:
        if value is not None:
            value = int(_float(value))
        if default is not None:
            default = int(_float(default))
    elif typ == "float":
        if value is not None:
            value = _float(value)
        if default is not None:
            default = _float(default)
    elif typ == "state":
        if value is not None:
            value = value.upper()
        if value not in state_names and default is not None:
            value = default
    elif typ == "select":
        value = _select_handler(value or "", opt, default)
    elif typ == "datetime":
        value, minval, maxval, default = _datetime_handler(
            value, default, minval, maxval, **kwargs
        )
    elif typ == "sday":
        value, minval, maxval, default = _sday_handler(
            value, default, minval, maxval
        )

    elif typ == "date":
        value, minval, maxval, default = _date_handler(
            value, default, minval, maxval, **kwargs
        )
    elif typ == "dat":
        # Damage Assessment Toolkit
        ctx["datglobalid"] = fdict.get("datglobalid")
    # validation
    if minval is not None and value is not None and value < minval:
        value = default
    if maxval is not None and value is not None and value > maxval:
        value = default
    ctx[name] = value if value is not None else default


def get_autoplot_context(
    fdict: dict, cfg: dict, enforce_optional: bool = False, **kwargs
) -> dict:
    """Get the variables out of a dict of strings

    This helper for IEM autoplot gets values out of a dictionary of strings,
    as provided by CGI.  It does some magic to get types right, defaults right
    and so on.  The typical way this is called

        ctx = iemutils.get_context(fdict, get_description())

    Args:
      fdict (dict): what was likely provided by `cgi.FieldStorage()`
      cfg (dict): autoplot value of get_description
      enforce_optional (bool,optional): Should the `optional` flag be enforced
      rectify_dates (bool,optional): Attempt to fix common date errors like
        June 31.  Default `false`.

    Returns:
      dictionary of variable names and values, with proper types!
    """

    ctx = {}
    # Check for DPI setting
    val = fdict.get("dpi")
    if val is not None:
        ctx["dpi"] = int(val)
    # Copy internal parameters, these are not specified by the autoplot cfg
    for key in filter(lambda x: x.startswith("_"), fdict.keys()):
        ctx[key] = escape(fdict[key])
    # Check over autoplot provided arguments
    for opt in cfg.get("arguments", []):
        _process_option(opt, fdict, ctx, enforce_optional, **kwargs)

    # Ensure defaults are set, if they exist
    for key in cfg.get("defaults", {}):
        if key not in ctx:
            ctx[key] = cfg["defaults"][key]
    return ctx
