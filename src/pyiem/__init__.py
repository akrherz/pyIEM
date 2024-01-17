"""Python Utilities developed for/by Iowa Environmental Mesonet

Python is an important part of the Iowa Environmental Mesonet (IEM).  This
package is used by many parts of the IEM codebase and hopefully somewhat
useful to others!?!?
"""
import os
import sys
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("pyiem")
    if (
        os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        in sys.path
    ):
        __version__ += "-dev"
except PackageNotFoundError:
    # package is not installed
    __version__ = "dev"
