"""Custom Exceptions."""


class BadWebRequest(Exception):
    """Raised when a bad web request is made."""


class CLIException(Exception):
    """Custom Exception for CLI Parsing Issues"""


class HWOException(Exception):
    """Exception for HWO Parsing."""


class IncompleteWebRequest(Exception):
    """Raised for a HTTP GET request without required params (422)."""


class InvalidArguments(Exception):
    """Provided method arguments were not valid (invalid units)."""


class InvalidPolygon(Exception):
    """Parsing of polygon raised a known error condition."""


class InvalidSHEFEncoding(Exception):
    """Product is not encoded to SHEF standard specification."""


class InvalidSHEFValue(Exception):
    """SHEF element value fails to be processed to a float."""


class MCDException(Exception):
    """Exception"""


class NHCException(Exception):
    """Exception"""


class NewDatabaseConnectionFailure(Exception):
    """Exception for when a new database connection fails."""


class NoDataFound(Exception):
    """Exception for when no data was found for request."""


class SAWException(Exception):
    """Custom local exception"""


class SIGMETException(Exception):
    """Custom SIGMET Parsing Exception."""


class TextProductException(Exception):
    """Exception for Text Parsing."""


class UGCParseException(Exception):
    """Custom Exception this parser can raise"""


class UnitsError(Exception):
    """Exception for bad Units."""


class UnknownStationException(Exception):
    """Exception for unknown station."""
