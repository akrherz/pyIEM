from distutils.core import setup

setup(
    name='pyIEM',
    version='0.0.1',
    author='daryl herzmann',
    author_email='akrherz@gmail.com',
    packages=['pyiem'],
    url='https://github.com/akrherz/pyIEM/',
    package_dir={'pyiem':'src/pyiem'},
    license='Apache',
    description='Collection of things that may help with processing weather data.',
)