#!/bin/bash
# Build script for Linux/macOS to create distributable executable using PyInstaller

echo "Building Squiddler executable..."
echo

# Check if PyInstaller is installed
if ! python -c "import PyInstaller" 2>/dev/null; then
    echo "PyInstaller not found. Installing..."
    pip install pyinstaller
fi

# Install the game's requirements (pymunk among them): PyInstaller only warns about a missing module
echo "Installing requirements..."
pip install -r requirements.txt
if ! python -c "import pymunk" 2>/dev/null; then
    echo
    echo "Build failed! pymunk is not installed (pip install -r requirements.txt)."
    exit 1
fi

# Clean previous builds
rm -rf build dist

# Build the executable using python -m PyInstaller (more reliable)
python -m PyInstaller pyinstaller.spec

if [ $? -ne 0 ]; then
    echo
    echo "Build failed!"
    exit 1
fi

echo
echo "Build complete! Executable is in the dist folder."
echo

