; Instalador de C. elegans Lab (Inno Setup). Se compila en CI con:
;   iscc /DAppVersion=<version> installer.iss
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{30DA4B58-BDA1-4E23-95CA-6E5E2D44D839}
AppName=C. elegans Lab
AppVersion={#AppVersion}
AppPublisher=Federico Bianchi
DefaultDirName={localappdata}\Programs\CElegansLab
DefaultGroupName=C. elegans Lab
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=installer_output
OutputBaseFilename=CElegansLab-Setup
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\CElegansLab.exe
; Al actualizar (instalar encima de una instalación ya abierta), cierra la
; app sola antes de copiar los archivos nuevos y la vuelve a abrir al
; terminar -- sin esto, un archivo en uso frena la instalación silenciosa.
CloseApplications=force
RestartApplications=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el Escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "dist\CElegansLab\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\C. elegans Lab"; Filename: "{app}\CElegansLab.exe"
Name: "{group}\Desinstalar C. elegans Lab"; Filename: "{uninstallexe}"
Name: "{autodesktop}\C. elegans Lab"; Filename: "{app}\CElegansLab.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\CElegansLab.exe"; Description: "Abrir C. elegans Lab"; Flags: nowait postinstall skipifsilent
