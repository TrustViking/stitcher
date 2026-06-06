@echo off
chcp 65001 >nul
cd /d "%~dp0"
stitcher.exe %*
echo.
echo Exit code: %ERRORLEVEL%
pause
