#!/bin/bash
# Build script for Linux/macOS to create distributable executable using PyInstaller

echo "Building ASTRO VOID executable..."
echo

# Check if PyInstaller is installed
if ! python -c "import PyInstaller" 2>/dev/null; then
    echo "PyInstaller not found. Installing..."
    pip install pyinstaller
fi

# Clean previous builds
rm -rf build dist

# Build the executable using python -m PyInstaller (more reliable)
python -m PyInstaller astrovoid.spec

if [ $? -ne 0 ]; then
    echo
    echo "Build failed!"
    exit 1
fi

echo
echo "Build complete! Executable is in the dist folder."
echo

