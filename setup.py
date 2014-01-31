from distutils.core import setup

import pyiem

setup(
    name='pyIEM',
    version=pyiem.__version__,
    author='daryl herzmann',
    author_email='akrherz@gmail.com',
    packages=['pyiem', 'pyiem.nws', 'pyiem.nws.products'],
    url='https://github.com/akrherz/pyIEM/',
    package_dir={'pyiem':'pyiem',
                 'pyiem.nws': 'pyiem/nws',
                 'pyiem.nws.products': 'pyiem/nws/products'},
    package_data={'pyiem': ['data/iowa_ccw.npy',
		'data/conus_ccw.npy',
		'data/conus_marine_bnds.txt',
		'data/midwest_ccw.npy',
		]},
    license='Apache',
    description='Collection of things that may help with processing weather data.',
)
