"""
 Something to store UGC information!
"""

import re
import datetime

#_re = "([A-Z][A-Z][C,Z][0-9][0-9][0-9][A-Z,0-9,\-,>]+)"
_re = "^(([A-Z]?[A-Z]?[C,Z]?[0-9]{3}[>\-]\s?\n?)+)([0-9]{6})-$"

class UGCParseException(Exception):
    pass

def ugcs_to_text(ugcs):
    """ Convert a list of UGC objects to a textual string """
    states = {}
    geotype = "counties"
    for u in ugcs:
        code = str(u)
        stateAB = code[:2]
        if code[2] == 'Z':
            geotype = "forecast zones"
        if not states.has_key(stateAB):
            states[stateAB] = []
        if u.name is None:
            name = "((%s))" % (code,)
        else:
            name = u.name
        states[stateAB].append(name)

    txt = []
    for st in states.keys():
        states[st].sort()
        s = " %s [%s]" % (", ".join(states[st]), st)
        if len(s) > 350:
            if st == 'LA' and geotype == 'counties':
                geotype = 'parishes'
            s = " %s %s in [%s]" % (len(states[st]), geotype, st)
        txt.append(s)

    return (" and".join( txt )).strip()


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
    if day < 5 and valid.day > 25: # Next month
        valid = valid + datetime.timedelta(days=25)
    #elif day > 25 and valid.day < 5: # previous month
    #    valid = valid - datetime.timedelta(days=25)

    return valid.replace(day=day,hour=hour,minute=minute)

def parse(text, valid, ugc_provider={}):
    """ Helper method that parses text and yields UGC and expiration time 
    @param text to parse
    @param valid is the issue time of the product this text was found in\
    @param ugc_provider of UGC objects
    """
    def _construct( code ):
        return ugc_provider.get(code, UGC(code[:2], code[2], code[3:]))
    ugcs = []
    expire = None
    tokens = re.findall(_re, text, re.M)
    if len(tokens) == 0:
        return ugcs, expire
    if len(tokens) > 1:
        raise UGCParseException("More than 1 UGC encoding in text:\n%s\n" % (
                                                            str(tokens),))
    
    parts = re.split('-', tokens[0][0].replace(" ","").replace("\n", ""))
    expire = str2time( tokens[0][2], valid)
    stateCode = ""
    for i, part in enumerate(parts):
        if i == 0 and len(part) >= 6:
            ugcType = part[2]
        if i == 0 and len(part) < 6:
            # This is bad encoding
            raise UGCParseException('WHOA, bad UGC encoding detected "%s"' % (
                                                            '-'.join(parts),))
        thisPart = parts[i].strip() 
        if len(thisPart) == 6: # We have a new state ID
            stateCode = thisPart[:3]
            ugcs.append( _construct(thisPart) )
        elif len(thisPart) == 3: # We have an individual Section
            ugcs.append( _construct("%s%s%s" % (stateCode[:2], stateCode[2],
                                                thisPart) ) )
        elif len(thisPart) > 6: # We must have a > in there somewhere
            newParts = re.split('>', thisPart)
            firstPart = newParts[0]
            secondPart = newParts[1]
            if len(firstPart) > 3:
                stateCode = firstPart[:3]
            firstVal = int( firstPart[-3:] )
            lastVal = int( secondPart )
            if ugcType == "C":
                for j in range(0, lastVal+2 - firstVal, 2):
                    strCode = "%03i" % (firstVal+j,)
                    ugcs.append( _construct("%s%s%s" % (stateCode[:2], 
                                                        stateCode[2], strCode)))
            else:
                for j in range(firstVal, lastVal+1):
                    strCode = "%03i" % (j,)
                    ugcs.append( _construct("%s%s%s" % (stateCode[:2], 
                                                        stateCode[2], strCode)))
    return ugcs, expire

class UGC:

    def __init__(self, state, geoclass, number, name=None, wfos=[]):
        '''
        Constructor for UGC instances
        '''
        self.state = state
        self.geoclass = geoclass
        self.number = int(number)
        self.name = name
        self.wfos = wfos
        
    def __str__(self):
        """ Override str() """
        return "%s%s%03i" % (self.state, self.geoclass, self.number)
    
    def __repr__(self):
        """ Override repr() """
        return "%s%s%03i" % (self.state, self.geoclass, self.number)
    
    def __eq__(self, other):
        """ Compare this UGC with another """
        return (self.state == other.state and self.geoclass == other.geoclass 
               and self.number == other.number)
