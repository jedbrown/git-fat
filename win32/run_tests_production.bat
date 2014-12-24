:: Install git-fat to C:\Python27\Scripts and run unit tests
:: without modifying the PATH environment variable, so that
:: the installed git-fat binaries are used during tests.

@echo OFF
cls

echo Running tests in a PRODUCTION environment
echo ==========================================================================

set "GIT_FAT_LOG_LEVEL=warning"
echo GIT_FAT_LOG_LEVEL: %GIT_FAT_LOG_LEVEL%

del %~dp0*.log
set "GIT_FAT_LOG_FILE="
echo GIT_FAT_LOG_FILE: %GIT_FAT_LOG_FILE%

set "GIT_FAT_TEST_PRODUCTION=1"
echo GIT_FAT_TEST_PRODUCTION: %GIT_FAT_TEST_PRODUCTION%

set "GIT_FAT_KEEP_TEMP_DIRS="
echo GIT_FAT_KEEP_TEMP_DIRS: %GIT_FAT_KEEP_TEMP_DIRS%

set "GIT_FAT_DISABLE_COVERAGE=1"
echo GIT_FAT_DISABLE_COVERAGE: %GIT_FAT_DISABLE_COVERAGE%

call setup_wheel.bat

echo --------------------------------------------------------------------------
echo Running actual unit tests
echo --------------------------------------------------------------------------

cd %~dp0../tests/
python test_git_fat.py

echo. & pause

