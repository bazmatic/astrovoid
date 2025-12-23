# -*- mode: python -*-
"""PyInstaller spec for bundling ASTRO VOID."""

from pathlib import Path
import os

from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

PROJECT_ROOT = Path.cwd()
BLOCK_CIPHER = None
BUILD_MODE = os.environ.get("ASTROVOID_PYINSTALLER_MODE", "onedir").lower()
ONEFILE_BUILD = BUILD_MODE == "onefile"

def collect_tree(source: Path, target: str) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for root, _, filenames in os.walk(source):
        root_path = Path(root)
        for filename in filenames:
            file_path = root_path / filename
            relative = file_path.relative_to(source)
            destination = Path(target) / relative
            items.append((str(file_path), str(destination)))
    return items


DATA_FILES = [
    (str(PROJECT_ROOT / "config" / "settings.json"), "config"),
]

for name in ("assets", "sounds", "levels"):
    DATA_FILES.extend(collect_tree(PROJECT_ROOT / name, name))

A = Analysis(
    [str(PROJECT_ROOT / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=DATA_FILES,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=BLOCK_CIPHER,
    noarchive=False,
)

PYZ_ARCHIVE = PYZ(A.pure, A.zipped_data, cipher=BLOCK_CIPHER)

# Use windowed mode on macOS to create proper app bundle
import sys
IS_MACOS = sys.platform == 'darwin'
CONSOLE_MODE = not (IS_MACOS and not ONEFILE_BUILD)

EXECUTABLE = EXE(
    PYZ_ARCHIVE,
    A.scripts,
    [],
    exclude_binaries=not ONEFILE_BUILD,
    name="AstroVoid",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=CONSOLE_MODE,
    windowed=not CONSOLE_MODE,
)

if not ONEFILE_BUILD:
    COLLECT(
        EXECUTABLE,
        A.binaries,
        A.zipfiles,
        A.datas,
        strip=False,
        upx=True,
        name="AstroVoid",
    )
