pyIEM
=====

A collection of python code that support various other python projects I have
and the [Iowa Environmental Mesonet](https://mesonet.agron.iastate.edu). A goal here is to upstream anything useful into [Unidata's MetPy](https://github.com/Unidata/MetPy) and also remove any redundant code.

[![CodeCov](https://codecov.io/gh/akrherz/pyIEM/branch/main/graph/badge.svg)](https://codecov.io/gh/akrherz/pyIEM)
[![Documentation](https://img.shields.io/badge/docs-gh--pages-blue)](https://akrherz.github.io/pyIEM/)

Current release info
--------------------

| Name | Downloads | Version | Platforms |
| --- | --- | --- | --- |
| [![Conda Recipe](https://img.shields.io/badge/recipe-pyiem-green.svg)](https://anaconda.org/conda-forge/pyiem) | [![Conda Downloads](https://img.shields.io/conda/dn/conda-forge/pyiem.svg)](https://anaconda.org/conda-forge/pyiem) | [![Conda Version](https://img.shields.io/conda/vn/conda-forge/pyiem.svg)](https://anaconda.org/conda-forge/pyiem) | [![Conda Platforms](https://img.shields.io/conda/pn/conda-forge/pyiem.svg)](https://anaconda.org/conda-forge/pyiem) |

Dependencies
------------

Python 3.11+ is required. Python releases 3.11 through 3.14 are actively tested
and supported within this repository.

The codebase currently makes direct database calls with hardcoded assumptions
of the hostname `iemdb.local` and database names.  Someday, I'll use a proper ORM
and software design techniques to make this more extensible for others!

Installation
------------

Since this library depends on `Cartopy`, you likely do **not** want to let `pip`
install `Cartopy`.  So the installation options are either:

1. Install `Cartopy` via some other mechanism than `pip`.
2. Install `pyiem` via pip.

Or:

1. Install `pyiem` via `conda` using the `conda-forge` channel.

How to use NWS product ingestors
--------------------------------

This library provides a number of parsers for various NWS products. The implementation of these parsers can be found with my [pyWWA project](https://github.com/akrherz/pyWWA).  The main limitation is that the `pyWWA` parsers use [Twisted Python](https://twistedmatrix.com) and thus have a somewhat steep learning curve.  The `pyIEM` parsers do not require the usage of Twisted though, so how does one use them?

The general entry point for a text product is the `parser` method of `pyiem.nws.products`. So given a NWS text file, the code would look like.

```python
from pyiem.nws.products import parser
text = open('MYFILE.txt').read()
prod = parser(text)
print(prod.get_product_id())
```

The actual methods and attributes on the `prod` object above will vary depending on the type of product involved.
