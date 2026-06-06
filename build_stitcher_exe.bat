@echo off
chcp 65001 >nul
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
set "PYTHON=%SCRIPT_DIR%.venv_stitcher\Scripts\python.exe"
set "SPEC=%SCRIPT_DIR%stitcher.spec"
set "ICON=%SCRIPT_DIR%stitch.ico"
set "DIST=%SCRIPT_DIR%dist"
set "TARGET=%DIST%\stitcher"

echo [INFO] Stitcher - building EXE (onedir mode)
echo [INFO] Python: %PYTHON%
echo [INFO] Spec:   %SPEC%
echo.

if not exist "%PYTHON%" (
  echo [ERROR] Python venv not found: %PYTHON%
  if "%NO_PAUSE%"=="" pause
  exit /b 1
)

if not exist "%SPEC%" (
  echo [ERROR] Spec file not found: %SPEC%
  if "%NO_PAUSE%"=="" pause
  exit /b 1
)

if not exist "%ICON%" (
  echo [ERROR] Icon file not found: %ICON%
  if "%NO_PAUSE%"=="" pause
  exit /b 1
)

echo [INFO] Cleaning __pycache__ directories...
for /d /r "%SCRIPT_DIR%" %%d in (__pycache__) do @if exist "%%d" rmdir /S /Q "%%d"

"%PYTHON%" -m PyInstaller --clean --noconfirm "%SPEC%"
if %ERRORLEVEL% neq 0 (
  echo [ERROR] PyInstaller failed.
  if "%NO_PAUSE%"=="" pause
  exit /b 1
)

echo.
echo [INFO] Copying external resources to dist\stitcher\...

rem config.toml (локальный, для portable smoke test)
if exist "%SCRIPT_DIR%config.toml" (
  copy /Y "%SCRIPT_DIR%config.toml" "%TARGET%\config.toml" >nul
  echo [OK] config.toml copied.
) else (
  echo [WARN] config.toml not found in project root.
)

rem config.example.toml (для installer)
if exist "%SCRIPT_DIR%config.example.toml" (
  copy /Y "%SCRIPT_DIR%config.example.toml" "%TARGET%\config.example.toml" >nul
  echo [OK] config.example.toml copied.
) else (
  echo [WARN] config.example.toml not found in project root.
)

rem profiles\
if exist "%SCRIPT_DIR%profiles\" (
  robocopy "%SCRIPT_DIR%profiles" "%TARGET%\profiles" /E /NFL /NDL /NJH /NJS >nul
  echo [OK] profiles\ copied.
) else (
  echo [WARN] profiles\ not found in project root.
)

rem tools\
if exist "%SCRIPT_DIR%tools\" (
  robocopy "%SCRIPT_DIR%tools" "%TARGET%\tools" /E /NFL /NDL /NJH /NJS >nul
  echo [OK] tools\ copied.
) else (
  echo [WARN] tools\ not found in project root.
)

rem secrets\
if exist "%SCRIPT_DIR%secrets\" (
  robocopy "%SCRIPT_DIR%secrets" "%TARGET%\secrets" /E /NFL /NDL /NJH /NJS >nul
  echo [OK] secrets\ copied.
) else (
  echo [WARN] secrets\ not found in project root.
)

rem run_debug.bat
if exist "%SCRIPT_DIR%run_debug.bat" (
  copy /Y "%SCRIPT_DIR%run_debug.bat" "%TARGET%\run_debug.bat" >nul
  echo [OK] run_debug.bat copied.
) else (
  echo [WARN] run_debug.bat not found in project root.
)

rem stitch.ico
copy /Y "%ICON%" "%TARGET%\stitch.ico" >nul
echo [OK] stitch.ico copied to portable root.

rem гарантируем создание пустых рабочих папок в portable build
if not exist "%TARGET%\logs"   mkdir "%TARGET%\logs"   >nul 2>&1
if not exist "%TARGET%\state"  mkdir "%TARGET%\state"  >nul 2>&1
if not exist "%TARGET%\temp"   mkdir "%TARGET%\temp"   >nul 2>&1
if not exist "%TARGET%\output" mkdir "%TARGET%\output" >nul 2>&1

echo.
echo [OK] Build complete.
echo [OK] Portable root: %TARGET%
echo.
echo Structure:
echo   stitcher.exe
echo   run_debug.bat
echo   stitch.ico
echo   config.toml
echo   config.example.toml
echo   profiles\
echo   tools\
echo     _yt-dlp\
echo       yt-dlp.exe
echo     _ffmpeg\bin\
echo       ffmpeg.exe
echo     _deno\
echo       deno.exe
echo   secrets\
echo     README.txt
echo     credentials.json   (если есть локально)
echo     token.json         (если есть локально)
echo     cookies.txt        (если есть локально)
echo   logs\
echo   state\
echo   temp\
echo   output\
echo   _internal\
echo.
echo Smoke test:
echo   %TARGET%\stitcher.exe --dry-run
echo.
echo [INFO] To produce an installer .exe, run build_release.bat or build_local.bat.
if "%NO_PAUSE%"=="" pause
