from distutils.core import setup
from setuptools.command.test import test as TestCommand  # noqa
import sys


class Tox(TestCommand):

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        import tox
        errno = tox.cmdline(self.test_args)
        sys.exit(errno)

from git_fat import __version__

setup(
    description="Manage large binary files with git",
    license='BSD 2-Clause',
    long_description=open('README.rst').read(),
    maintainer='Alan Braithwaite',
    maintainer_email='alan.braithwaite@cyaninc.com',
    name='git-fat',
    packages=['git_fat'],
    scripts=['bin/git-fat'],
    url='https://github.com/cyaninc/git-fat',
    version=__version__,
    cmdclass={"test": Tox},
)
