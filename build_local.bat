@echo off
chcp 65001 >nul
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"

echo [WARN] Building LOCAL installer (bundles real secrets - do NOT publish).

set "NO_PAUSE=1"
call "%SCRIPT_DIR%build_stitcher_exe.bat"
if %ERRORLEVEL% neq 0 (
  echo [ERROR] Portable build failed.
  pause & exit /b 1
)

if not exist "%SCRIPT_DIR%secrets\credentials.json" (
  echo [ERROR] secrets\credentials.json not found. Local installer needs real Google OAuth credentials.
  pause & exit /b 1
)

if not exist "%SCRIPT_DIR%config.toml" (
  echo [ERROR] config.toml not found in project root. Local installer needs a real local config
  echo         ^(with personal sheets_id^), otherwise the installed app starts with empty config.
  pause & exit /b 1
)

rem === валидация: в проекте config.toml sheets_id обязан быть НЕпустой ===
rem Симметрично release: проверяем sheets_id с хотя бы одним непробельным символом в кавычках.
rem Если строки нет или она пустая — local installer бесполезен, прерываемся.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$line = Get-Content -LiteralPath '%SCRIPT_DIR%config.toml' | Where-Object { $_ -match '^\s*sheets_id\s*=' } | Select-Object -First 1; if (-not $line) { exit 1 }; $value = (($line -split '=', 2)[1]).Trim().Trim([char]34); if ($value.Trim().Length -gt 0) { exit 0 }; exit 1"
if %ERRORLEVEL% neq 0 (
  echo [ERROR] config.toml has empty sheets_id - local installer would not be self-contained.
  echo         Fill in [google].sheets_id in config.toml before building a local installer.
  pause & exit /b 1
)
echo [OK] local config.toml validated: sheets_id is non-empty.

rem === также проверим что в staging\config.toml лежит копия личного config.toml ===
rem (build_stitcher_exe.bat уже скопировал config.toml в staging; здесь только
rem диагностируем рассинхрон, если кто-то правил staging вручную)
if exist "%SCRIPT_DIR%dist\stitcher\config.toml" (
  fc /B "%SCRIPT_DIR%config.toml" "%SCRIPT_DIR%dist\stitcher\config.toml" >nul 2>&1
  if %ERRORLEVEL% neq 0 (
    echo [WARN] dist\stitcher\config.toml differs from project config.toml.
    echo [WARN] Restoring staging config.toml from project root...
    copy /Y "%SCRIPT_DIR%config.toml" "%SCRIPT_DIR%dist\stitcher\config.toml" >nul
  )
)

where /q ISCC.exe
if %ERRORLEVEL%==0 (
  set "ISCC=ISCC.exe"
  goto :iscc_found
)
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" & goto :iscc_found
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe" & goto :iscc_found
echo [ERROR] ISCC.exe not found. Install Inno Setup 6 and either add it to PATH or use the default install location.
pause & exit /b 1
:iscc_found

if not "%VERSION%"=="" set "MyAppVersion=%VERSION%"
if "%MyAppVersion%"=="" set "MyAppVersion=0.2.0"

if not exist "%SCRIPT_DIR%dist\installer" mkdir "%SCRIPT_DIR%dist\installer" >nul 2>&1

"%ISCC%" ^
  /DMyAppVersion=%MyAppVersion% ^
  /DIncludeSecrets=1 ^
  /DOutputBaseFilename=stitcher-setup-local-%MyAppVersion% ^
  /DSecretsSource="%SCRIPT_DIR%secrets" ^
  /DSourceDir="%SCRIPT_DIR%dist\stitcher" ^
  /DOutputDir="%SCRIPT_DIR%dist\installer" ^
  "%SCRIPT_DIR%installer.iss"
if %ERRORLEVEL% neq 0 (
  echo [ERROR] Local installer build failed.
  pause & exit /b 1
)

echo [OK] Local installer built: dist\installer\stitcher-setup-local-%MyAppVersion%.exe
echo [WARN] This installer contains REAL secrets. DO NOT upload to GitHub.
pause
