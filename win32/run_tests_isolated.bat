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

echo Running tests in an ISOLATED environment
echo ==========================================================================

:: Just to be perfectly sure that this is isolated environment,
:: uninstall the git-fat package.

echo Uninstalling the git-fat package, type 'y' when asked.
echo If type package doesn't exist then it's okay, ignore the message.
echo.
pip uninstall git-fat

echo Checking sources with PEP 8 and Pylint & echo.

set files=git_fat/git_fat.py tests/test_git_fat.py
for %%f in (%files%) do call :RunCheckers "%%f"
goto RunCheckersEndOfLoop

:: ----------------------------------------------------------------------------
:: Loop must call subroutine instead of the do() block, otherwise
:: errorlevel is not set properly.
:RunCheckers

python %~dp0fix_whitespace.py %~dp0..\%~1
if %ERRORLEVEL% neq 0 echo FAILED to automatically fix whitespace & pause
echo.

echo PEP 8: %~1
pep8.exe --ignore=E501 %~dp0..\%~1
if %ERRORLEVEL% neq 0 echo FAILED & pause
if %ERRORLEVEL% equ 0 echo OK
echo.

echo Pylint: %~1
pylint.exe --reports=n --rcfile="%~dp0pylint.rc" %~dp0..\%~1
if %ERRORLEVEL% neq 0 echo FAILED & pause
if %ERRORLEVEL% equ 0 echo OK
echo.

exit /B

:RunCheckersEndOfLoop
:: ----------------------------------------------------------------------------

set PATH=C:\Windows\system32
set PATH=%PATH%;C:\Windows
set PATH=%PATH%;C:\Windows\System32\Wbem
set PATH=%PATH%;C:\Python27
set PATH=%PATH%;C:\Program Files (x86)\Git\bin
echo PATH: "%PATH%"
echo.

echo GIT_FAT_LOG_LEVEL: %GIT_FAT_LOG_LEVEL%

del %~dp0*.log
set "GIT_FAT_LOG_FILE=%~dp0.git-fat.log"
echo GIT_FAT_LOG_FILE: %GIT_FAT_LOG_FILE%

echo GIT_FAT_KEEP_TEMP_DIRS: %GIT_FAT_KEEP_TEMP_DIRS%

set "GIT_FAT_TEST_PRODUCTION="
echo GIT_FAT_TEST_PRODUCTION: %GIT_FAT_TEST_PRODUCTION%

set "GIT_FAT_DISABLE_COVERAGE=1"
echo GIT_FAT_DISABLE_COVERAGE: %GIT_FAT_DISABLE_COVERAGE%

echo --------------------------------------------------------------------------
echo Running actual unit tests
echo --------------------------------------------------------------------------

cd %~dp0../tests/
echo Running tests with the --failfast flag (stop on first error) & echo.
python test_git_fat.py --failfast

echo. & pause
