"""
Something to store UGC information!
"""

# stdlib
import re
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Optional, Union

# third party
import pandas as pd

# local
from pyiem.database import get_dbconnstr, sql_helper
from pyiem.exceptions import UGCParseException
from pyiem.util import LOG, utc

UGC_RE = re.compile(
    r"^(([A-Z]?[A-Z]?[C,Z]?[0-9]{3}[>\-]\s?\n?)+)([0-9]{6})-\s*$", re.M
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
        valid = valid + timedelta(days=25)

    return valid.replace(day=day, hour=hour, minute=minute)


def _load_from_database(pgconn=None, valid=None):
    """Build dataframe from a IEM Schema database.

    Args:
        pgconn (database engine): something pandas can query
        valid (timestamp, optional): timestamp version of database to use.
    """
    # This is sometimes autoloaded and we should alert folks when it is
    # happening
    LOG.warning("UGC load with valid: %s", valid)
    pgconn = (
        pgconn
        if pgconn is not None
        else get_dbconnstr("postgis").replace(
            "postgresql", "postgresql+psycopg"
        )
    )
    valid = valid if valid is not None else utc()
    # UGC is **not** unique here, so we sort by area attempting to at least
    # default to the most 'important' UGC  see fun in akrherz/pyIEM#997
    return pd.read_sql(
        sql_helper("""
    SELECT ugc, replace(name, '...', ' ') as name, wfo, source
    from ugcs WHERE begin_ts <= :valid and
    (end_ts is null or end_ts > :valid) ORDER by area2163 desc"""),
        pgconn,
        params={"valid": valid},
        index_col=None,
    )


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
        return f"{self.state}{self.geoclass}{self.number:03.0f}"

    def __repr__(self):
        """Override repr()"""
        return f"{self.state}{self.geoclass}{self.number:03.0f}"

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


class UGCProvider:
    """Wrapper around dataframe to provide UGC information."""

    # We only hold an instance, if we loaded from the database.
    _instance = None

    def __new__(cls, *args, **kwargs):
        """Singleton, if the price is right."""
        if kwargs.get("legacy_dict") is not None:
            return super(UGCProvider, cls).__new__(cls)
        if not cls._instance:
            cls._instance = super(UGCProvider, cls).__new__(cls)
        return cls._instance

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
            df = pd.DataFrame(rows, columns=["ugc", "name", "wfo", "source"])
        else:
            df = _load_from_database(pgconn, valid)
        self.df = df

    def __contains__(self, key: Union[str, UGC]) -> bool:
        """Check if this provider knows about this UGC.

        Args:
            key (str or UGC): the UGC to lookup

        Returns:
            bool
        """
        return not self.df[self.df["ugc"] == str(key)].empty

    def get(self, key: Union[str, UGC], is_firewx=False) -> UGC:
        """Return what this provider knows about a given UGC.

        The complication is that we always want something, either a newly
        created `UGC` instance or a new one materialized by the internal
        dataframe stored metadata.

        Args:
            key (str or UGC): the UGC to lookup
            is_firewx (bool): is this a fire weather product, so firewx zones

        Returns:
            UGC instance
        """
        # Our internal storage is based on a string key
        ugc_code: str = key if isinstance(key, str) else str(key)

        matchedrows = self.df[self.df["ugc"] == ugc_code]

        # If the UGC is unknown
        if matchedrows.empty:
            # Return the original UGC if it is already an object
            if isinstance(key, UGC):
                return key
            # Otherwise, we need to create a new UGC instance
            return UGC(key[:2], key[2], int(key[3:]))

        def _gen(row: dict) -> "UGC":
            """helper"""
            return UGC(
                ugc_code[:2],
                ugc_code[2],
                int(ugc_code[3:]),
                name=row["name"],
                wfos=re.findall(r"([A-Z][A-Z][A-Z])", row["wfo"]),
            )

        # If we have a single match, we can just return that
        if len(matchedrows) == 1:
            return _gen(matchedrows.iloc[0])
        # Ambiguous
        for _idx, row in matchedrows.iterrows():
            if is_firewx and row["source"] == "fz":
                return _gen(row)
            if not is_firewx and row["source"] != "fz":
                return _gen(row)
        # This really should not happen
        LOG.warning("Ambiguous UGC lookup for %s, please review.", ugc_code)
        return UGC(ugc_code[:2], ugc_code[2], int(ugc_code[3:]))

    def __getitem__(self, key):
        """Dictionary access helper."""
        return self.get(key)


def parse(
    text: str,
    valid: datetime,
    ugc_provider: Optional[UGCProvider] = None,
    is_firewx: bool = False,
) -> tuple[list[UGC], Optional[datetime]]:
    """Return UGC list and expiration time.

    Arguments:
      text (str): text to parse.
      valid (datetime): the text product's valid time.
      ugc_provider (UGCProvider): what will generate UGC instances for us.
      is_firewx (bool): is this product a fire weather product.
    """
    if ugc_provider is None:
        ugc_provider = UGCProvider()

    def _construct(code: str) -> UGC:
        return ugc_provider.get(code, is_firewx=is_firewx)

    ugcs = []
    expire = None
    tokens = UGC_RE.findall(text)
    if not tokens:
        return ugcs, expire
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
        this_part = part.strip()
        if len(this_part) == 6:  # We have a new state ID
            state_code = this_part[:3]
            ugcs.append(_construct(this_part))
        elif len(this_part) == 3:  # We have an individual Section
            ugcs.append(
                _construct(f"{state_code[:2]}{state_code[2]}{this_part}")
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
                    str_code = f"{(first_val + j):03.0f}"
                    ugcs.append(
                        _construct(
                            f"{state_code[:2]}{state_code[2]}{str_code}"
                        )
                    )
            else:
                for j in range(first_val, last_val + 1):
                    str_code = f"{j:03.0f}"
                    ugcs.append(
                        _construct(
                            f"{state_code[:2]}{state_code[2]}{str_code}"
                        )
                    )
    return ugcs, expire
