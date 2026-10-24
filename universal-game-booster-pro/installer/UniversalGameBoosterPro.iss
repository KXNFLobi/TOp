; Compile on Windows after PyInstaller has created dist\UniversalGameBoosterPro.
#define AppName "Universal Game Booster Pro"
#define AppVersion "1.1.0"
#define AppExeName "UniversalGameBoosterPro.exe"
#define BundleDir AddBackslash(SourcePath) + "..\dist\UniversalGameBoosterPro"

[Setup]
AppId={{05F15807-05B7-48C5-86FB-2AE71395AF92}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Universal Game Booster Pro
DefaultDirName={localappdata}\Programs\UniversalGameBoosterPro
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
DisableProgramGroupPage=yes
OutputDir={#AddBackslash(SourcePath)}..\dist\installer
OutputBaseFilename=UniversalGameBoosterPro-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExeName}
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Abrir {#AppName}"; Flags: nowait postinstall skipifsilent
