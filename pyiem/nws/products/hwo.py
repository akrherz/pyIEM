import re
from pyiem.nws.product import TextProduct


class HWOException(Exception):
    """ Exception """
    pass


class HWOProduct(TextProduct):
    """
    Represents a HWO
    """

    def __init__(self, text, utcnow=None, ugc_provider=None,
                 nwsli_provider=None):
        ''' constructor '''
        TextProduct.__init__(self, text, utcnow=utcnow,
                             ugc_provider=ugc_provider,
                             nwsli_provider=nwsli_provider)

    def get_channels(self):
        """ overridden TextProduct#get_channels """
        no_storms_day1 = True
        no_storms_day27 = True
        for segnum, segment in enumerate(self.segments):
            if len(segment.ugcs) == 0:
                continue
            day1 = segment.unixtext.upper().find(".DAY ONE...")
            if day1 == -1 and self.afos != 'HWOSPN':
                raise HWOException("segment %s is missing DAY ONE section" % (
                                                                    segnum,))
            day27 = segment.unixtext.upper().find(".DAYS TWO THROUGH SEVEN...")
            if day27 == -1 and self.afos != 'HWOSPN':
                raise HWOException(("segment %s is missing DAYS TWO "
                                    "THROUGH SEVEN section") % (segnum, ))

            day1text = re.search((r'(NO HAZARDOUS WEATHER IS EXPECTED AT '
                                  'THIS TIME|THE PROBABILITY FOR WIDESPREAD '
                                  'HAZARDOUS WEATHER IS LOW)'),
                                 segment.unixtext[day1:day27], re.IGNORECASE)
            day27text = re.search((r'(NO HAZARDOUS WEATHER IS EXPECTED AT '
                                   'THIS TIME|THE PROBABILITY FOR WIDESPREAD '
                                   'HAZARDOUS WEATHER IS LOW)'),
                                  segment.unixtext[day27:], re.IGNORECASE)
            if day1text is None:
                no_storms_day1 = False
            if day27text is None:
                no_storms_day27 = False

        channels = [self.afos, ]
        if no_storms_day1 and no_storms_day27:
            channels[0] = "%s.NONE" % (self.afos,)

        return channels


def parser(text, utcnow=None, ugc_provider=None, nwsli_provider=None):
    ''' Helper function '''
    return HWOProduct(text, utcnow=utcnow, ugc_provider=ugc_provider,
                      nwsli_provider=nwsli_provider)
