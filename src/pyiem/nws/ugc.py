"""
 Something to store UGC information!
"""

import re
import datetime

#_re = "([A-Z][A-Z][C,Z][0-9][0-9][0-9][A-Z,0-9,\-,>]+)"
_re = "(([A-Z]?[A-Z]?[C,Z]?[0-9]{3}[>\-])+)([0-9]{6})-"

def str2time(text, valid):
    """ Convert a string that is the UGC product expiration to a valid 
    datetime
    @param text string to convert
    @param valid datetime instance
    """
    day = int(text[:2])
    hour = int(text[2:4])
    minute = int(text[4:])
    if day < 5 and valid.day > 25: # Next month
        valid = valid + datetime.timedelta(days=25)
    elif day > 25 and valid.day < 5: # previous month
        valid = valid - datetime.timedelta(days=25)

    return valid.replace(day=day,hour=hour,minute=minute)

def parse(text, valid):
    """ Helper method that parses text and yields UGC and expiration time 
    @param text to parse
    @param valid is the issue time of the product this text was found in
    """
    ugcs = []
    expire = None
    tokens = re.findall(_re, text)
    if len(tokens) == 0:
        return ugcs, expire
    
    parts = re.split('-', tokens[0][0])
    expire = str2time( tokens[0][2], valid)
    stateCode = ""
    for i in range(len(parts) ):
        if i == 0:
            ugcType = parts[0][2]
        thisPart = parts[i]
        if len(thisPart) == 6: # We have a new state ID
            stateCode = thisPart[:3]
            ugcs.append( UGC(thisPart[:2], thisPart[2], thisPart[3:]) )
        elif len(thisPart) == 3: # We have an individual Section
            ugcs.append( UGC(stateCode[:2], stateCode[2], thisPart) )
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
                    ugcs.append( UGC(stateCode[:2], stateCode[2], strCode) )
            else:
                for j in range(firstVal, lastVal+1):
                    strCode = "%03i" % (j,)
                    ugcs.append( UGC(stateCode[:2], stateCode[2], strCode) )
    
    return ugcs, expire

class UGC:

    def __init__(self, state, geoclass, number):
        self.state = state
        self.geoclass = geoclass
        self.number = int(number)
        
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
