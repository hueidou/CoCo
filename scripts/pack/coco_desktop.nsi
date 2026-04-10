; CoCo Desktop NSIS installer. Run makensis from repo root after
; building dist/win-unpacked (see scripts/pack/build_win.ps1).
; Usage: makensis /DCOCO_VERSION=1.2.3 /DOUTPUT_EXE=dist\CoCo-Setup-1.2.3.exe scripts\pack\coco_desktop.nsi

!include "MUI2.nsh"
!define MUI_ABORTWARNING
; Use custom icon from unpacked env (copied by build_win.ps1)
!define MUI_ICON "${UNPACKED}\icon.ico"
!define MUI_UNICON "${UNPACKED}\icon.ico"

!ifndef COCO_VERSION
  !define COCO_VERSION "0.0.0"
!endif
!ifndef OUTPUT_EXE
  !define OUTPUT_EXE "dist\CoCo-Setup-${COCO_VERSION}.exe"
!endif

Name "CoCo Desktop"
OutFile "${OUTPUT_EXE}"
InstallDir "$LOCALAPPDATA\CoCo"
InstallDirRegKey HKCU "Software\CoCo" "InstallPath"
RequestExecutionLevel user

!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"

; Pass /DUNPACKED=full_path from build_win.ps1 so path works when cwd != repo root
!ifndef UNPACKED
  !define UNPACKED "dist\win-unpacked"
!endif

Section "CoCo Desktop" SEC01
  SetOutPath "$INSTDIR"
  File /r "${UNPACKED}\*.*"
  WriteRegStr HKCU "Software\CoCo" "InstallPath" "$INSTDIR"
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; Main shortcut - uses VBS to hide console window
  CreateShortcut "$SMPROGRAMS\CoCo Desktop.lnk" "$INSTDIR\CoCo Desktop.vbs" "" "$INSTDIR\icon.ico" 0
  CreateShortcut "$DESKTOP\CoCo Desktop.lnk" "$INSTDIR\CoCo Desktop.vbs" "" "$INSTDIR\icon.ico" 0
  
  ; Debug shortcut - shows console window for troubleshooting
  CreateShortcut "$SMPROGRAMS\CoCo Desktop (Debug).lnk" "$INSTDIR\CoCo Desktop (Debug).bat" "" "$INSTDIR\icon.ico" 0
SectionEnd

Section "Uninstall"
  Delete "$SMPROGRAMS\CoCo Desktop.lnk"
  Delete "$SMPROGRAMS\CoCo Desktop (Debug).lnk"
  Delete "$DESKTOP\CoCo Desktop.lnk"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKCU "Software\CoCo"
SectionEnd
