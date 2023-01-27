# pyIEM MapPlot backgrounds

The goal is to have pretty things in the background of plots and to remember
how I set this mess up!  So the directory nomenclature is as such:

    <name>/<sector>_<epsg>.{png,wld}

There should be a `default_4326.png` that covers the NW quad of the globe
in a modest fashion.  We then go down the rabbit hole of providing pre-projected
scenes for various common sector + epsg combinations.

The ne2 source is [here](https://www.naturalearthdata.com/downloads/10m-raster-data/10m-natural-earth-2/),
"Natural Earth II with Shaded Relief, Water, and Drainages".

There's a `util/cookie_cutter.py` that generates scenes we want.
