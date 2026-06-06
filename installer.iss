#ifndef MyAppVersion
#define MyAppVersion "0.1.0"
#endif

#ifndef IncludeSecrets
#define IncludeSecrets 0
#endif

#ifndef SecretsSource
#define SecretsSource ""
#endif

#ifndef SourceDir
#define SourceDir "dist\stitcher"
#endif

#ifndef OutputDir
#define OutputDir "dist\installer"
#endif

#ifndef OutputBaseFilename
#define OutputBaseFilename "stitcher-setup-" + MyAppVersion
#endif

[Setup]
AppName=Stitcher
AppId={{B6A4F2C0-7D33-4F8A-9D9E-B0ADC0020001}}
AppPublisher=Vi0rel
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\Stitcher
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
DisableDirPage=no
DisableProgramGroupPage=yes
OutputBaseFilename={#OutputBaseFilename}
OutputDir={#OutputDir}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile={#SourceDir}\stitch.ico
UninstallDisplayIcon={app}\stitcher.exe
UninstallDisplayName=Stitcher
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=force
RestartIfNeededByRun=no

[Files]
Source: "{#SourceDir}\stitcher.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\run_debug.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\stitch.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceDir}\tools\*"; DestDir: "{app}\tools"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
Source: "{#SourceDir}\profiles\*"; DestDir: "{app}\profiles"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceDir}\config.example.toml"; DestDir: "{app}"; Flags: ignoreversion

#if IncludeSecrets
; Local installer: подкладываем личный config.toml как есть.
; build_release.bat перед запуском ISCC подменяет staging\config.toml на копию example,
; так что в release-сборке здесь будет тот же шаблон с пустым sheets_id.
Source: "{#SourceDir}\config.toml"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
#else
; Release installer: разворачиваем config.toml из example-шаблона.
Source: "{#SourceDir}\config.example.toml"; DestDir: "{app}"; DestName: "config.toml"; Flags: ignoreversion onlyifdoesntexist
#endif

Source: "{#SourceDir}\secrets\README.txt"; DestDir: "{app}\secrets"; Flags: ignoreversion onlyifdoesntexist skipifsourcedoesntexist

#if IncludeSecrets
Source: "{#SecretsSource}\credentials.json"; DestDir: "{app}\secrets"; Flags: ignoreversion onlyifdoesntexist skipifsourcedoesntexist
Source: "{#SecretsSource}\token.json"; DestDir: "{app}\secrets"; Flags: ignoreversion onlyifdoesntexist skipifsourcedoesntexist
Source: "{#SecretsSource}\cookies.txt"; DestDir: "{app}\secrets"; Flags: ignoreversion onlyifdoesntexist skipifsourcedoesntexist
#endif

[Dirs]
Name: "{app}\state"
Name: "{app}\logs"
Name: "{app}\temp"
Name: "{app}\output"
Name: "{app}\secrets"

[Icons]
Name: "{autodesktop}\Stitcher"; Filename: "{app}\run_debug.bat"; IconFilename: "{app}\stitch.ico"; WorkingDir: "{app}"
