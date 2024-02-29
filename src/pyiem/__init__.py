"""Python Utilities developed for/by Iowa Environmental Mesonet

Python is an important part of the Iowa Environmental Mesonet (IEM).  This
package is used by many parts of the IEM codebase and hopefully somewhat
useful to others!?!?
"""

import os
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("pyiem")
    pkgdir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    if not pkgdir.endswith("site-packages"):
        __version__ += "-dev"
except PackageNotFoundError:
    # package is not installed
    __version__ = "dev"
