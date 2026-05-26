@echo off
title ContraCORE Build
cd /d "%~dp0"
echo.
echo ============================================================
echo   ContraCORE Production Build
echo ============================================================
echo.
if not exist "build_tools\dist\ContraCORELauncher.exe" (
    echo [!] ContraCORELauncher.exe bulunamadi, once build aliniyor...
    echo.
    python build_tools/build_launcher.py
    if errorlevel 1 (
        echo.
        echo [HATA] Launcher build basarisiz!
        pause
        exit /b 1
    )
)
echo [1/2] ContraCORE derleniyor...
echo.
python build_tools/build_contracore.py --clean --zip
if errorlevel 1 (
    echo.
    echo [HATA] ContraCORE build basarisiz!
    pause
    exit /b 1
)
echo.
echo [2/2] Setup hazirlaniyor...
echo.
python build_tools/build_setup.py
if errorlevel 1 (
    echo.
    echo [HATA] Setup build basarisiz!
    pause
    exit /b 1
)
echo.
echo ============================================================
echo   BUILD TAMAMLANDI
echo ============================================================
echo.
echo   EXE   : release\ContraCORE\ContraCORE.exe
echo   ZIP   : release\ContraCORE_update.zip
echo   SETUP : release\setup\
echo.
echo GitHub adimlari:
echo   1. update.json dosyasini main branche push et
echo   2. GitHub Release olustur, ContraCORE_update.zip yukle
echo.
pause
