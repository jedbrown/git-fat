@echo OFF

set PATH=C:\Windows\system32
set PATH=%PATH%;C:\Windows
set PATH=%PATH%;C:\Windows\System32\Wbem
echo PATH: %PATH%
echo.

:: Download depends.exe from: http://www.dependencywalker.com/

depends.exe git-fat_gawk.exe
depends.exe git-fat_rsync.exe
depends.exe git-fat_ssh.exe

pause
