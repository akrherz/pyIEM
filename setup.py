from distutils.core import setup
from setuptools.command.test import test as TestCommand
import sys
import pyiem


class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        import pytest
        errno = pytest.main(self.test_args)
        sys.exit(errno)

setup(
    name='pyIEM',
    version=pyiem.__version__,
    author='daryl herzmann',
    author_email='akrherz@gmail.com',
    packages=['pyiem', 'pyiem.nws', 'pyiem.nws.products'],
    package_data={'pyiem': ['data/*', ]},
    url='https://github.com/akrherz/pyIEM/',
    download_url='',
    keywords=['weather'],
    classifiers=[],
    license='Apache',
    cmdclass={'test': PyTest},
    description=('Collection of things that may help with processing '
                 'weather data.'),
    include_package_data=True,
)
