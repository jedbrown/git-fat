from distutils.core import setup

from git_fat import __version__

setup(
    name='git-fat',
    maintainer='Alan Braithwaite',
    maintainer_email='alan.braithwaite@cyaninc.com',
    url='https://github.com/cyaninc/git-fat',
    version=__version__,
    packages=['git_fat'],
    scripts=['bin/git-fat'],
    license='BSD 2-Clause',
    description="Manage large binary files with git",
    long_description=open('README.rst').read(),
)
