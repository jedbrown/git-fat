from setuptools import setup
from setuptools.dist import Distribution
from setuptools.command.build_py import build_py
from git_fat import __version__


class BinaryDistribution(Distribution):
    def is_pure(self):
        return False


def main():
    setup(
        description="Manage large binary files with git",
        license='BSD 2-Clause',
        long_description=open('README.rst').read(),
        maintainer='Alan Braithwaite',
        maintainer_email='alan.braithwaite@cyaninc.com',
        name='git-fat',
        packages=['git_fat'],
        # 'console_scripts' will create git-fat.exe in the Python/Scripts
        # directory.
        entry_points={'console_scripts': [
                      'git-fat = git_fat:main']},
        scripts=['win32/git-fat',
                 'win32/git-fat.bat',
                 'win32/git-fat_gawk.exe',
                 'win32/git-fat_rsync.exe',
                 'win32/git-fat_ssh.exe',
                 'win32/msys-1.0.dll',
                 'win32/msys-crypto-1.0.0.dll',
                 'win32/msys-iconv-2.dll',
                 'win32/msys-intl-8.dll',
                 'win32/msys-minires.dll',
                 'win32/msys-popt-0.dll',
                 'win32/msys-z.dll'],
        url='https://github.com/cyaninc/git-fat',
        version=__version__,
        cmdclass={'build_py': build_py},
        distclass=BinaryDistribution,
    )


if __name__ == "__main__":
    main()
