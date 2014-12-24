:: This script will install the package.

:: Additionally an .egg will be created in the dist/ directory.
:: A Python Egg on Windows can be installed using easy_installer.

:: pip cannot install eggs, it needs a Python Wheel package. See
:: You can create a .whl package using the setup_wheel.bat
:: script.

@echo OFF

echo Uninstalling the git-fat package, type 'y' when asked.
echo If type package doesn't exist then it's okay, ignore the message.
echo.
pip uninstall git-fat

cd %~dp0../
echo Running the Setuptools installation script & echo.
python setup_win.py install
cd %~dp0

echo. & pause
