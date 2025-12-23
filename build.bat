@echo off
REM Build script for Windows to create distributable executable using PyInstaller

echo Building ASTRO VOID executable...
echo.

REM Check if PyInstaller is installed
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
)

REM Build the executable using python -m PyInstaller (more reliable on Windows)
REM --clean flag automatically removes build artifacts and cache
python -m PyInstaller astrovoid.spec --clean

if errorlevel 1 (
    echo.
    echo Build failed!
    pause
    exit /b 1
)

echo.
echo Build complete! Executable is in the dist folder.
echo.
pause

