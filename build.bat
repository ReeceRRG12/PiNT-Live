@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
    echo Usage: build.bat v0.7.0-beta.3
    echo First install: python -m pip install . "pyinstaller>=6.10,<7"
    exit /b 2
)
python scripts\build_release.py --tag "%~1"
exit /b %errorlevel%
