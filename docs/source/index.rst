pyIEM Documentation
====================

**pyIEM** is a Python library that provides utilities for processing weather 
data, particularly data from the `Iowa Environmental Mesonet (IEM) 
<https://mesonet.agron.iastate.edu>`_ and the National Weather Service (NWS).

Installation
------------

Install from PyPI:

.. code-block:: bash

   pip install pyiem

Or from conda-forge:

.. code-block:: bash

   conda install -c conda-forge pyiem


Features
--------

- Parse NWS text products including VTEC-enabled products
- Work with SHEF-encoded hydrological data
- Generate plots with IEM styling and map backgrounds
- Access IEM databases and web services
- Process METAR observations
- Handle various meteorological data formats


Quick Start
-----------

.. code-block:: python

   from pyiem.nws.products import parser
   from pyiem.util import utc
   
   # Parse a NWS text product
   text = open("warning.txt").read()
   prod = parser(text, utcnow=utc())
   
   for segment in prod.segments:
       for vtec in segment.vtec:
           print(f"{vtec.phenomena}.{vtec.significance} ETN:{vtec.etn}")


API Reference
-------------

.. toctree::
   :maxdepth: 2
   :caption: API Reference:

   api/pyiem
   api/pyiem.grid
   api/pyiem.models
   api/pyiem.ncei
   api/pyiem.nws
   api/pyiem.plot
   api/pyiem.templates


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

