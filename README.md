pyIEM
=====

A collection of python code that support various other python projects I have
and the [Iowa Environmental Mesonet](https://mesonet.agron.iastate.edu). A goal here is to upstream anything useful into [Unidata's MetPy](https://github.com/Unidata/MetPy) and also remove any redundant code.

[![Docs](https://readthedocs.org/projects/pyiem/badge/?version=latest)](https://readthedocs.org/projects/pyiem/)
[![Build Status](https://travis-ci.org/akrherz/pyIEM.svg)](https://travis-ci.org/akrherz/pyIEM)
[![Coverage Status](https://coveralls.io/repos/akrherz/pyIEM/badge.svg?branch=master&service=github)](https://coveralls.io/github/akrherz/pyIEM?branch=master)
[![Code Health](https://landscape.io/github/akrherz/pyIEM/master/landscape.svg?style=flat)](https://landscape.io/github/akrherz/pyIEM/master)
[![CodeCov](https://codecov.io/gh/akrherz/pyIEM/branch/master/graph/badge.svg)](https://codecov.io/gh/akrherz/pyIEM)

Dependencies
------------

The codebase currently makes direct database calls with hardcoded assumptions
of the hostname `iemdb` and database names.  Someday, I'll use a proper ORM
and software design techniques to make this more extensible for others!

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
