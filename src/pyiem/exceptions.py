"""Custom Exceptions."""


class NoDataFound(Exception):
    """Exception for when no data was found for request."""


class UnitsError(Exception):
    """Exception for bad Units."""


class TextProductException(Exception):
    """Exception for Text Parsing."""


class HWOException(Exception):
    """Exception for HWO Parsing."""


class MCDException(Exception):
    """Exception"""


class NHCException(Exception):
    """Exception"""


class SAWException(Exception):
    """Custom local exception"""


class SIGMETException(Exception):
    """Custom SIGMET Parsing Exception."""


class UGCParseException(Exception):
    """Custom Exception this parser can raise"""


class CLIException(Exception):
    """Custom Exception for CLI Parsing Issues"""


class InvalidPolygon(Exception):
    """Parsing of polygon raised a known error condition."""


class InvalidArguments(Exception):
    """Provided method arguments were not valid (invalid units)."""


class InvalidSHEFEncoding(Exception):
    """Product is not encoded to SHEF standard specification."""


class InvalidSHEFValue(Exception):
    """SHEF element value fails to be processed to a float."""
