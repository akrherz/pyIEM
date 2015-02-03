from distutils.core import setup

import pyiem

setup(
    name='pyIEM',
    version=pyiem.__version__,
    author='daryl herzmann',
    author_email='akrherz@gmail.com',
    packages=['pyiem', 'pyiem.nws', 'pyiem.nws.products', 'pyiem.windrose'],
    package_data={'pyiem': ['data/*',]},
    url='https://github.com/akrherz/pyIEM/',
    license='Apache',
    description='Collection of things that may help with processing weather data.',
)
