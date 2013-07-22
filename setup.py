from distutils.core import setup

setup(
    name='pyIEM',
    version='0.0.2',
    author='daryl herzmann',
    author_email='akrherz@gmail.com',
    packages=['pyiem', 'pyiem.nws'],
    url='https://github.com/akrherz/pyIEM/',
    package_dir={'pyiem':'src/pyiem',
                 'pyiem.nws': 'src/pyiem/nws'},
    package_data={'pyiem': ['data/iowa_bnds.txt',
		'data/conus_bnds.txt',
		'data/conus_marine_bnds.txt',
		'data/midwest_bnds.txt',
		]},
    license='Apache',
    description='Collection of things that may help with processing weather data.',
)
