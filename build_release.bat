@echo off
chcp 65001 >nul
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"

echo [INFO] Building RELEASE installer (no secrets bundled).

set "NO_PAUSE=1"
call "%SCRIPT_DIR%build_stitcher_exe.bat"
if %ERRORLEVEL% neq 0 (
  echo [ERROR] Portable build failed.
  pause & exit /b 1
)

if not "%VERSION%"=="" set "MyAppVersion=%VERSION%"
if "%MyAppVersion%"=="" set "MyAppVersion=0.1.0"

if not exist "%SCRIPT_DIR%dist\installer" mkdir "%SCRIPT_DIR%dist\installer" >nul 2>&1

rem === wipe secrets staging — в release-installer не должно попасть ничего личного ===
set "STAGE_SECRETS=%SCRIPT_DIR%dist\stitcher\secrets"
if exist "%STAGE_SECRETS%" (
  del /F /Q "%STAGE_SECRETS%\*" >nul 2>&1
  for /D %%D in ("%STAGE_SECRETS%\*") do rmdir /S /Q "%%D" 2>nul
) else (
  mkdir "%STAGE_SECRETS%" >nul 2>&1
)
if exist "%SCRIPT_DIR%secrets\README.txt" (
  copy /Y "%SCRIPT_DIR%secrets\README.txt" "%STAGE_SECRETS%\README.txt" >nul
  echo [OK] dist\stitcher\secrets wiped, only README.txt restored.
) else (
  echo [ERROR] secrets\README.txt not found - release secrets staging cannot be reseeded.
  pause & exit /b 1
)

rem === заменить config.toml на example для release ===
set "STAGE_ROOT=%SCRIPT_DIR%dist\stitcher"
if exist "%STAGE_ROOT%\config.example.toml" (
  copy /Y "%STAGE_ROOT%\config.example.toml" "%STAGE_ROOT%\config.toml" >nul
  echo [OK] dist\stitcher\config.toml replaced with config.example.toml ^(release build^).
) else (
  echo [ERROR] config.example.toml missing in staging - cannot proceed safely.
  pause & exit /b 1
)

rem === валидация: в staging\config.toml sheets_id обязан быть пустой ===
rem Если sheets_id внутри кавычек непустой — release сборка прерывается.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$line = Get-Content -LiteralPath '%STAGE_ROOT%\config.toml' | Where-Object { $_ -match '^\s*sheets_id\s*=' } | Select-Object -First 1; if (-not $line) { exit 1 }; $value = (($line -split '=', 2)[1]).Trim().Trim([char]34); if ($value.Trim().Length -gt 0) { exit 1 }; exit 0"
if %ERRORLEVEL% neq 0 (
  echo [ERROR] Non-empty sheets_id detected in release staging config.toml.
  echo [ERROR] Check that config.example.toml has sheets_id = "" before publishing.
  pause & exit /b 1
)
echo [OK] release config.toml validated: sheets_id is empty.

rem === финальная страховочная проверка: ни одного личного файла не должно остаться ===
for %%F in (credentials.json token.json cookies.txt .env) do (
  if exist "%STAGE_SECRETS%\%%F" (
    echo [ERROR] %%F still present in release staging. Aborting.
    pause & exit /b 1
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

"%ISCC%" ^
  /DMyAppVersion=%MyAppVersion% ^
  /DIncludeSecrets=0 ^
  /DOutputBaseFilename=stitcher-setup-%MyAppVersion% ^
  /DSourceDir="%SCRIPT_DIR%dist\stitcher" ^
  /DOutputDir="%SCRIPT_DIR%dist\installer" ^
  "%SCRIPT_DIR%installer.iss"
if %ERRORLEVEL% neq 0 (
  echo [ERROR] Release installer build failed.
  pause & exit /b 1
)

echo [OK] Release installer built: dist\installer\stitcher-setup-%MyAppVersion%.exe
echo [INFO] This installer contains NO real secrets and NO personal config.
echo [INFO] Suitable for GitHub Releases.
pause
