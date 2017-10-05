"""
 Something to store UGC information!
"""
from __future__ import print_function
import re
import datetime
from collections import OrderedDict

UGC_RE = re.compile(
    r"^(([A-Z]?[A-Z]?[C,Z]?[0-9]{3}[>\-]\s?\n?)+)([0-9]{6})-$", re.M)


class UGCParseException(Exception):
    """Custom Exception this parser can raise"""
    pass


def ugcs_to_text(ugcs):
    """ Convert a list of UGC objects to a textual string """
    states = OrderedDict()
    geotype = "counties"
    for ugc in ugcs:
        code = str(ugc)
        state_abbr = code[:2]
        if code[2] == 'Z':
            geotype = "forecast zones"
        if state_abbr not in states:
            states[state_abbr] = []
        if ugc.name is None:
            name = "((%s))" % (code,)
        else:
            name = ugc.name
        states[state_abbr].append(name)

    txt = []
    for st in states.keys():
        states[st].sort()
        part = " %s [%s]" % (", ".join(states[st]), st)
        if len(part) > 350:
            if st == 'LA' and geotype == 'counties':
                geotype = 'parishes'
            part = " %s %s in [%s]" % (len(states[st]), geotype, st)
        txt.append(part)

    return (" and".join(txt)).strip()


def str2time(text, valid):
    """ Convert a string that is the UGC product expiration to a valid
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


def parse(text, valid, ugc_provider=None):
    """ Helper method that parses text and yields UGC and expiration time
    @param text to parse
    @param valid is the issue time of the product this text was found in
    @param ugc_provider of UGC objects
    """
    if ugc_provider is None:
        ugc_provider = dict()

    def _construct(code):
        return ugc_provider.get(code, UGC(code[:2], code[2], code[3:]))
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
        raise UGCParseException("More than 1 UGC encoding in text:\n%s\n" % (
                                                            str(tokens),))

    parts = re.split('-', tokens[0][0].replace(" ", "").replace("\n", ""))
    expire = str2time(tokens[0][2], valid)
    state_code = ""
    for i, part in enumerate(parts):
        if i == 0:
            if len(part) >= 6:
                ugc_type = part[2]
            else:
                # This is bad encoding
                raise UGCParseException(('WHOA, bad UGC encoding detected "%s"'
                                         ) % ('-'.join(parts),))
        this_part = parts[i].strip()
        if len(this_part) == 6:  # We have a new state ID
            state_code = this_part[:3]
            ugcs.append(_construct(this_part))
        elif len(this_part) == 3:  # We have an individual Section
            ugcs.append(_construct("%s%s%s" % (state_code[:2], state_code[2],
                                               this_part)))
        elif len(this_part) > 6:  # We must have a > in there somewhere
            new_parts = re.split('>', this_part)
            first_part = new_parts[0]
            second_part = new_parts[1]
            if len(first_part) > 3:
                state_code = first_part[:3]
            first_val = int(first_part[-3:])
            last_val = int(second_part)
            if ugc_type == "C":
                for j in range(0, last_val+2 - first_val, 2):
                    str_code = "%03i" % (first_val+j,)
                    ugcs.append(_construct("%s%s%s" % (state_code[:2],
                                                       state_code[2],
                                                       str_code)))
            else:
                for j in range(first_val, last_val+1):
                    str_code = "%03i" % (j,)
                    ugcs.append(_construct("%s%s%s" % (state_code[:2],
                                                       state_code[2],
                                                       str_code)))
    return ugcs, expire


class UGC(object):
    """Representation of a single UGC"""

    def __init__(self, state, geoclass, number, name=None, wfos=None):
        """
        Constructor for UGC instances
        """
        self.state = state
        self.geoclass = geoclass
        self.number = int(number)
        self.name = name
        self.wfos = wfos if wfos is not None else []

    def __str__(self):
        """ Override str() """
        return "%s%s%03i" % (self.state, self.geoclass, self.number)

    def __repr__(self):
        """ Override repr() """
        return "%s%s%03i" % (self.state, self.geoclass, self.number)

    def __eq__(self, other):
        """ Compare this UGC with another """
        return (self.state == other.state and
                self.geoclass == other.geoclass and
                self.number == other.number)
