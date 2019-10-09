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
    """ Exception """


class NHCException(Exception):
    """ Exception """


class SAWException(Exception):
    """Custom local exception"""


class UGCParseException(Exception):
    """Custom Exception this parser can raise"""
