; Inno Setup script para LaEsquinaManager
; Genera un instalador de Windows con accesos directos y desinstalador.
; La base de datos NO se incluye ni se elimina: vive en
; %LOCALAPPDATA%\LaEsquinaManager\data

#define MyAppName "La Esquina Manager"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "GS"
#define MyAppExeName "LaEsquinaManager.exe"

[Setup]
AppId={{E6E8D739-5E8F-4B74-A5F4-7B25E1641D0D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\LaEsquinaManager
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=LaEsquinaManager_Setup_1.0.0
SetupIconFile=..\GS_LaEsquinaManager.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no

[Files]
Source: "..\dist\LaEsquinaManager.exe"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
Name: "{localappdata}\LaEsquinaManager"
Name: "{localappdata}\LaEsquinaManager\data"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el Escritorio"; GroupDescription: "Accesos directos:"; Flags: checkedonce

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Intencionalmente NO borrar %LOCALAPPDATA%\LaEsquinaManager\data
; para conservar ventas, productos, clientes y configuración al actualizar.
