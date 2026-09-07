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
SetupIconFile=assets\icon.ico
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
; Bootstrapper oficial de Microsoft para el motor que muestra la app en su
; propia ventana (WebView2). Ya viene instalado de fábrica en casi
; cualquier Windows 10/11 actualizado; este archivo revisa eso solo y no
; hace nada si ya está — solo baja e instala el motor en el caso raro de
; que falte. Se descarga en el workflow de GitHub Actions antes de
; compilar (build.yml), no está commiteado al repo.
Source: "vendor\MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall skipifsourcedoesntexist

[Icons]
Name: "{group}\C. elegans Lab"; Filename: "{app}\CElegansLab.exe"
Name: "{group}\Desinstalar C. elegans Lab"; Filename: "{uninstallexe}"
Name: "{autodesktop}\C. elegans Lab"; Filename: "{app}\CElegansLab.exe"; Tasks: desktopicon

[Run]
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "Preparando componentes de Windows..."; Flags: waituntilterminated; Check: ExisteBootstrapperWebView2
Filename: "{app}\CElegansLab.exe"; Description: "Abrir C. elegans Lab"; Flags: nowait postinstall skipifsilent

[Code]
function ExisteBootstrapperWebView2(): Boolean;
begin
  { Solo lo corre si el archivo se pudo copiar -- en un build local (Opción
    B del README) sin el .exe pre-descargado, el instalador sigue
    funcionando igual, solo que sin este paso. }
  Result := FileExists(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe'));
end;
