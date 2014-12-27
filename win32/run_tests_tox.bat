:: Run unit tests in an isolated environment. Only C:\Python27
:: should be in path and standard Windows directories. The
:: test_git_fat.py script will additionally add the tests/
:: to PATH, so that the git-fat and git-fat.bat scripts residing
:: in the tests/ directory are used by git.

:: If you would like to log git-fat messages globally, even when
:: not running unit tests, for example during normal work, then
:: set the GIT_FAT_LOG_FILE and GIT_FAT_LOG_LEVEL environment
:: variables.

@echo OFF
cls

echo Running tests in an ISOLATED environment with the TOX virtualenv library
echo ==========================================================================

:: The Python/Scripts directory will always be added to PATH by
:: python itself, so to be sure that the right git-fat script is
:: is run we must uninstall the package.

echo Uninstalling the git-fat package, type 'y' when asked.
echo If type package doesn't exist then it's okay, ignore the message.
pip uninstall git-fat

set "GIT_FAT_LOG_LEVEL=warning"
echo GIT_FAT_LOG_LEVEL: %GIT_FAT_LOG_LEVEL%

del %~dp0*.log
set "GIT_FAT_LOG_FILE=%~dp0.git-fat.log"
echo GIT_FAT_LOG_FILE: %GIT_FAT_LOG_FILE%

echo GIT_FAT_KEEP_TEMP_DIRS: %GIT_FAT_KEEP_TEMP_DIRS%

set "GIT_FAT_TEST_PRODUCTION="
echo GIT_FAT_TEST_PRODUCTION: %GIT_FAT_TEST_PRODUCTION%

set "GIT_FAT_DISABLE_COVERAGE="
echo GIT_FAT_DISABLE_COVERAGE: %GIT_FAT_DISABLE_COVERAGE%

echo --------------------------------------------------------------------------
echo Running actual unit tests
echo --------------------------------------------------------------------------

cd %~dp0../
python setup.py test
cd %~dp0

echo. & pause
