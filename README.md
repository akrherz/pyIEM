pyIEM
=====

A collection of python code that support various other python projects I have
and the (Iowa Environmental Mesonet)[https://mesonet.agron.iastate.edu].

[![Build Status](https://travis-ci.org/akrherz/pyIEM.svg)](https://travis-ci.org/akrherz/pyIEM)
[![Coverage Status](https://coveralls.io/repos/akrherz/pyIEM/badge.svg?branch=master&service=github)](https://coveralls.io/github/akrherz/pyIEM?branch=master)
[![Code Health](https://landscape.io/github/akrherz/pyIEM/master/landscape.svg?style=flat)](https://landscape.io/github/akrherz/pyIEM/master)

Dependencies
------------

The codebase currently makes direct database calls with hardcoded assumptions
of the hostname `iemdb` and database names.  Someday, I'll use a proper ORM
and software design techniques to make this more extensible for others!
