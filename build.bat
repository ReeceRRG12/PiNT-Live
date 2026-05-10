@echo off
REM PiNT Live — build standalone exe
REM Run this from the project root (where PiNT_Live.spec lives)

echo.
echo  ╔══════════════════════════════════════╗
echo  ║       PiNT Live — Build Tool         ║
echo  ╚══════════════════════════════════════╝
echo.

REM Clean previous build artefacts
echo [1/3] Cleaning previous build...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist
echo       Done.
echo.

REM Run PyInstaller with the spec file
echo [2/3] Building exe (this takes a minute)...
python -m PyInstaller PiNT_Live.spec
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: PyInstaller failed. See output above.
    pause
    exit /b 1
)
echo.

REM Report result
echo [3/3] Build complete!
echo.
echo  Output: dist\PiNT Live.exe
echo.
echo  This file is self-contained and can be shared directly.
echo  No Python install required on the target machine.
echo.
pause
