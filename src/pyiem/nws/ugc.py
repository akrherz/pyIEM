"""
 Something to store UGC information!
"""
# stdlib
import re
import datetime
from collections import OrderedDict

# third party
import pandas as pd
from pandas import read_sql

# local
from pyiem.util import utc, get_dbconnstr
from pyiem.exceptions import UGCParseException

UGC_RE = re.compile(
    r"^(([A-Z]?[A-Z]?[C,Z]?[0-9]{3}[>\-]\s?\n?)+)([0-9]{6})-$", re.M
)


def ugcs_to_text(ugcs):
    """Convert a list of UGC objects to a textual string"""
    states = OrderedDict()
    geotype = "counties"
    for ugc in ugcs:
        code = str(ugc)
        state_abbr = code[:2]
        if code[2] == "Z":
            geotype = "forecast zones"
        if state_abbr not in states:
            states[state_abbr] = []
        states[state_abbr].append(ugc.name)

    txt = []
    for st, state in states.items():
        state.sort()
        part = f" {', '.join(state)} [{st}]"
        if len(part) > 350:
            if st == "LA" and geotype == "counties":
                geotype = "parishes"
            part = f" {len(state)} {geotype} in [{st}]"
        txt.append(part)

    return (" and".join(txt)).strip()


def str2time(text, valid):
    """Convert a string that is the UGC product expiration to a valid
    datetime
    @param text string to convert
    @param valid datetime instance
    """
    if text in ["000000", "123456"]:
        return None
    day = int(text[:2])
    hour = int(text[2:4])
    minute = int(text[4:])
    if day < 5 and valid.day > 25:  # Next month
        valid = valid + datetime.timedelta(days=25)
    # elif day > 25 and valid.day < 5: # previous month
    #    valid = valid - datetime.timedelta(days=25)

    return valid.replace(day=day, hour=hour, minute=minute)


def parse(text, valid, ugc_provider=None, is_firewx=False):
    """Return UGC list and expiration time.

    Arguments:
      text (str): text to parse.
      valid (datetime): the text product's valid time.
      ugc_provider (UGCProvider): what will generate UGC instances for us.
      is_firewx (bool): is this product a fire weather product.
    """
    if ugc_provider is None or isinstance(ugc_provider, dict):
        ugc_provider = UGCProvider(legacy_dict=ugc_provider)

    def _construct(code):
        return ugc_provider.get(code, is_firewx=is_firewx)

    ugcs = []
    expire = None
    tokens = UGC_RE.findall(text)
    if not tokens:
        return ugcs, expire
    # TODO: perhaps we should be more kind when we find products with this
    #       formatting error, but we can recover.  Note that typically the
    #       UGC codes are the same, but the product expiration time may be off
    # if len(tokens) == 2 and tokens[0] == tokens[1]:
    #    pass
    if len(tokens) > 1:
        raise UGCParseException(
            f"More than 1 UGC encoding in text:\n{tokens}\n"
        )

    parts = re.split("-", tokens[0][0].replace(" ", "").replace("\n", ""))
    expire = str2time(tokens[0][2], valid)
    state_code = ""
    for i, part in enumerate(parts):
        if i == 0:
            if len(part) >= 6:
                ugc_type = part[2]
            else:
                # This is bad encoding
                raise UGCParseException(
                    f'WHOA, bad UGC encoding detected "{"-".join(parts)}"'
                )
        this_part = parts[i].strip()
        if len(this_part) == 6:  # We have a new state ID
            state_code = this_part[:3]
            ugcs.append(_construct(this_part))
        elif len(this_part) == 3:  # We have an individual Section
            ugcs.append(
                _construct(
                    "%s%s%s" % (state_code[:2], state_code[2], this_part)
                )
            )
        elif len(this_part) > 6:  # We must have a > in there somewhere
            new_parts = re.split(">", this_part)
            first_part = new_parts[0]
            second_part = new_parts[1]
            if len(first_part) > 3:
                state_code = first_part[:3]
            first_val = int(first_part[-3:])
            last_val = int(second_part)
            if ugc_type == "C":
                for j in range(0, last_val + 2 - first_val, 2):
                    str_code = "%03i" % (first_val + j,)
                    ugcs.append(
                        _construct(
                            "%s%s%s"
                            % (state_code[:2], state_code[2], str_code)
                        )
                    )
            else:
                for j in range(first_val, last_val + 1):
                    str_code = "%03i" % (j,)
                    ugcs.append(
                        _construct(
                            "%s%s%s"
                            % (state_code[:2], state_code[2], str_code)
                        )
                    )
    return ugcs, expire


def _load_from_database(pgconn=None, valid=None):
    """Build dataframe from a IEM Schema database.

    Args:
        pgconn (database engine): something pandas can query
        valid (timestamp, optional): timestamp version of database to use.
    """
    pgconn = pgconn if pgconn is not None else get_dbconnstr("postgis")
    valid = valid if valid is not None else utc()
    return read_sql(
        "SELECT ugc, replace(name, '...', ' ') as name, wfo, source "
        "from ugcs WHERE begin_ts <= %s and "
        "(end_ts is null or end_ts > %s)",
        pgconn,
        params=(valid, valid),
        index_col=None,
    )


class UGCProvider:
    """Wrapper around dataframe to provide UGC information."""

    def __init__(self, legacy_dict=None, pgconn=None, valid=None):
        """Constructor.

        Args:
          legacy_dict(dict, optional): Build based on legacy dictionary.
          pgconn (database engine): something to query to get ugc data.
          valid (timestamp): database version to use.
        """
        rows = []
        if legacy_dict is not None:
            for key, _ugc in legacy_dict.items():
                rows.append(
                    {
                        "ugc": key,
                        "name": _ugc.name.replace("...", " "),
                        "wfo": "".join(_ugc.wfos),
                        "source": "",
                    }
                )
            self.df = pd.DataFrame(
                rows, columns=["ugc", "name", "wfo", "source"]
            )
        else:
            self.df = _load_from_database(pgconn, valid)

    def get(self, key, is_firewx=False):
        """Return a UGC instance."""
        df2 = self.df[self.df["ugc"] == key]
        if df2.empty:
            return UGC(key[:2], key[2], int(key[3:]))

        def _gen(row):
            """helper"""
            return UGC(
                key[:2],
                key[2],
                int(key[3:]),
                name=row["name"],
                wfos=re.findall(r"([A-Z][A-Z][A-Z])", row["wfo"]),
            )

        if len(df2.index) == 1:
            row = df2.iloc[0]
            return _gen(row)
        # Ambiguous
        for _idx, row in df2.iterrows():
            if is_firewx and row["source"] == "fz":
                return _gen(row)
            if not is_firewx and row["source"] != "fz":
                return _gen(row)
        # This really should not happen
        return UGC(key[:2], key[2], int(key[3:]))

    def __getitem__(self, key):
        """Dictionary access helper."""
        return self.get(key)


class UGC:
    """Representation of a single UGC"""

    def __init__(self, state, geoclass, number, name=None, wfos=None):
        """
        Constructor for UGC instances
        """
        self.state = state
        self.geoclass = geoclass
        self.number = int(number)
        self.name = name if name is not None else f"(({self.__str__()}))"
        self.wfos = wfos if wfos is not None else []

    def __str__(self):
        """Override str()"""
        return "%s%s%03i" % (self.state, self.geoclass, self.number)

    def __repr__(self):
        """Override repr()"""
        return "%s%s%03i" % (self.state, self.geoclass, self.number)

    def __eq__(self, other):
        """Compare this UGC with another"""
        return (
            self.state == other.state
            and self.geoclass == other.geoclass
            and self.number == other.number
        )

    def __ne__(self, other):
        """Compare this UGC with another"""
        return not self == other

    __hash__ = None  # unhashable
