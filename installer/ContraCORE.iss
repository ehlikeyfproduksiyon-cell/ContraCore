; ContraCORE — Inno Setup Script
; Kullanım: build_tools/build_setup.py tarafından otomatik çağrılır.
; Manuel: ISCC /DMyAppVersion=1.0.0 installer\ContraCORE.iss
;
; Çıktı: release\setup\ContraCORE_Setup_vX.Y.Z.exe

#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif

#define MyAppName        "ContraCORE"
#define MyAppPublisher   "Serkan ŞAHİN"
#define MyAppExeName     "ContraCORELauncher.exe"
#define MyAppMainExe     "ContraCORE.exe"
#define MySourceDir      "..\release\ContraCORE"
#define MyOutputDir      "..\release\setup"
#define MySetupIcon      "..\Icon\SETUP.ico"
#define MyAppIcon        "Icon\contralogoo.ico"

; ── Uygulama Bilgisi ──────────────────────────────────────────────────────────

[Setup]
AppId={{A3F8B2C1-44D7-4E9A-BC3F-D7A2E5F61089}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=
AppSupportURL=
AppUpdatesURL=

; Kurulum dizini
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}

; Çıktı
OutputDir={#MyOutputDir}
OutputBaseFilename=ContraCORE_Setup_v{#MyAppVersion}

; Setup ikonu + sıkıştırma
SetupIconFile={#MySetupIcon}
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; Windows minimum sürüm: Windows 10
MinVersion=10.0

; Program Files altına kurulum — UAC isteği yapar
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

; Wizard görünümü
WizardStyle=modern
; WizardResizable — Inno Setup 6'da artık desteklenmiyor, kaldırıldı

; Dil
LanguageDetectionMethod=locale

; Uninstaller
UninstallDisplayName={#MyAppName} {#MyAppVersion}
UninstallDisplayIcon={app}\{#MyAppMainExe},0

; Kurulum öncesi çalışan ContraCORE örneğini kapat
CloseApplications=yes
CloseApplicationsFilter=ContraCORE.exe,ContraCORELauncher.exe

; ── Dil ──────────────────────────────────────────────────────────────────────

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

; ── Mesajlar (Türkçe özel) ────────────────────────────────────────────────────

[CustomMessages]
turkish.RunAfterInstall=ContraCORE'u Başlat

; ── Dosyalar ─────────────────────────────────────────────────────────────────

[Files]
; Tüm release/ContraCORE içeriği — alt dizinler dahil
; __pycache__, geçici dosyalar, yedek klasörler hariç
Source: "{#MySourceDir}\*"; \
  DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs; \
  Excludes: "__pycache__,*.log,*.tmp,*.pyc,*.pyo,_backup,_temp_apply"

; ── Kısayollar ───────────────────────────────────────────────────────────────

[Icons]
; Başlat Menüsü
Name: "{group}\{#MyAppName}"; \
  Filename: "{app}\{#MyAppExeName}"; \
  WorkingDir: "{app}"

Name: "{group}\{#MyAppName} Kaldır"; \
  Filename: "{uninstallexe}"

; Masaüstü
Name: "{autodesktop}\{#MyAppName}"; \
  Filename: "{app}\{#MyAppExeName}"; \
  WorkingDir: "{app}"; \
  Tasks: desktopicon

; ── Görevler (kurulum sihirbazı seçenekleri) ─────────────────────────────────

[Tasks]
Name: "desktopicon"; \
  Description: "Masaüstü kısayolu oluştur"; \
  GroupDescription: "Ek kısayollar:"; \
  Flags: unchecked

; ── Kurulum sonrası çalıştır ─────────────────────────────────────────────────

[Run]
Filename: "{app}\{#MyAppExeName}"; \
  Description: "{cm:RunAfterInstall}"; \
  Flags: postinstall skipifsilent nowait; \
  WorkingDir: "{app}"

; ── Kayıt Defteri ────────────────────────────────────────────────────────────

[Registry]
; Add/Remove Programs bilgisi (Inno otomatik ekler, ek alan için)
Root: HKLM; \
  Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppName}_is1"; \
  ValueType: string; \
  ValueName: "DisplayVersion"; \
  ValueData: "{#MyAppVersion}"; \
  Flags: uninsdeletekey

Root: HKLM; \
  Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppName}_is1"; \
  ValueType: string; \
  ValueName: "DisplayIcon"; \
  ValueData: "{app}\{#MyAppMainExe},0"
