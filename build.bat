@echo off
REM Build script for Windows to create distributable executable using PyInstaller

echo Building Squiddler executable...
echo.

REM Check if PyInstaller is installed
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
)

REM Install the game's requirements (pymunk among them): PyInstaller only warns about a missing module
echo Installing requirements...
pip install -r requirements.txt
python -c "import pymunk" 2>nul
if errorlevel 1 (
    echo.
    echo Build failed! pymunk is not installed ^(pip install -r requirements.txt^).
    pause
    exit /b 1
)

REM Build the executable using python -m PyInstaller (more reliable on Windows)
REM --clean flag automatically removes build artifacts and cache
python -m PyInstaller pyinstaller.spec --clean

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

