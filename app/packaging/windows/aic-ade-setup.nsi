!include "MUI2.nsh"
!define SRC_DIR "/home/tvd/AI-Company/aic-ide/release/win-unpacked"
!define OUT_DIR "/home/tvd/AI-Company/aic-ide/release"
Name "AIC ADE"
OutFile "${OUT_DIR}/AIC-ADE-Setup-2.1.7a.exe"
InstallDir "$LOCALAPPDATA\AIC ADE"
RequestExecutionLevel user
Unicode True
SetCompressor zlib
!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"
Section "Install"
  SetOutPath "$INSTDIR"
  File /r "${SRC_DIR}\*.*"
  CreateDirectory "$SMPROGRAMS\AIC ADE"
  CreateShortCut "$SMPROGRAMS\AIC ADE\AIC ADE.lnk" "$INSTDIR\AIC ADE.exe"
  CreateShortCut "$DESKTOP\AIC ADE.lnk" "$INSTDIR\AIC ADE.exe"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AICADE" "DisplayName" "AIC ADE"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AICADE" "UninstallString" "$\"$INSTDIR\Uninstall.exe$\""
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AICADE" "DisplayIcon" "$INSTDIR\AIC ADE.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AICADE" "Publisher" "AIC Company"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AICADE" "DisplayVersion" "2.1.7a"
SectionEnd
Section "Uninstall"
  Delete "$SMPROGRAMS\AIC ADE\AIC ADE.lnk"
  RMDir "$SMPROGRAMS\AIC ADE"
  Delete "$DESKTOP\AIC ADE.lnk"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\AICADE"
  RMDir /r "$INSTDIR"
SectionEnd
