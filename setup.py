from distutils.core import setup

setup(
    name='git-fat',
    maintainer='Alan Braithwaite',
    maintainer_email='alan.braithwaite@cyaninc.com',
    url='https://github.com/cyaninc/git-fat',
    version='0.1.0',
    packages=['git_fat'],
    scripts=['bin/git-fat'],
    license='BSD 2-Clause',
    description="Manage large binary files with git",
    long_description=open('README.md').read(),
)
