:: Create a Python Wheel binary package

:: NOTE on the missing git-fat script in the Python/Scripts directory:
:: -------------------------------------------------------------------
:: I couldn't make the Wheel package to install the "git-fat" script
:: (without extension) to the Python/Scripts directory. It's not
:: necessary, but it would be a safety precaution in case another
:: package installs such script in that location (for example the
:: .tar.gz Linux source package). When packages are managed using
:: pip then it should be okay. On the other hand when installing
:: package using the "setup.bat" script it will install an .egg
:: package along with the git-fat script in the Python/Scripts dir.

@echo OFF

echo Uninstalling the git-fat package, type 'y' when asked.
echo If type package doesn't exist then it's okay, ignore the message.
echo.
pip uninstall git-fat

cd %~dp0../
echo Running Setuptools to create a Python Wheel binary package & echo.
python setup_win.py bdist_wheel
cd %~dp0

:: Pip requires slashes in path, backslashes won't work
set "distdir=%~dp0../dist/"
set "distdir=%distdir:\=/%"

echo Installing git-fat .whl package from the local directory: %distdir%
echo.
pip install --upgrade git-fat --no-index --find-links="file://%distdir%"

echo. & pause
