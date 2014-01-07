import os

from distutils import log
from distutils.command.build_scripts import build_scripts as _build_scripts
from distutils.core import setup
from distutils.util import convert_path

from git_fat import __version__


SYS_PATH_PATCH = '''
### this trick solves issue with running scripts in isolated env ###
import sys
git_fat_lib_location = '%s'
if git_fat_lib_location not in sys.path:
    # no sense for current $PYTHONPATH configuration - we always knowns
    # where are sources and can import git_fat
    sys.path.insert(0, git_fat_lib_location)
### end of trick ###
'''


class build_scripts(_build_scripts):
    def run(self):
        # installing scripts normal way
        _build_scripts.run(self)

        # making patch with actual target location for git_fat sources
        install_lib = self.get_finalized_command('install_lib')
        patch = SYS_PATH_PATCH % install_lib.install_dir

        if not self.dry_run:
            for script in self.scripts:
                script = convert_path(script)
                outfile = os.path.join(self.build_dir, os.path.basename(script))
                with open(outfile, 'r+') as f:
                    lines = f.readlines()
                    for i, l in enumerate(lines):
                        # placing patch after first shebang or comment
                        if not l.startswith('#'):
                            lines[i] = patch + l
                            break
                    # rewriting updated script
                    f.seek(0)
                    f.truncate()
                    log.info("patching %s", outfile)
                    f.writelines(lines)


setup(
    name='git-fat',
    maintainer='Alan Braithwaite',
    maintainer_email='alan.braithwaite@cyaninc.com',
    url='https://github.com/cyaninc/git-fat',
    version=__version__,
    packages=['git_fat'],
    cmdclass={"build_scripts": build_scripts},
    scripts=['bin/git-fat'],
    license='BSD 2-Clause',
    description="Manage large binary files with git",
    long_description=open('README.rst').read(),
)
