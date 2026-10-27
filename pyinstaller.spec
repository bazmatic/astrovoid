# -*- mode: python -*-
"""PyInstaller spec for bundling Squiddler."""

from pathlib import Path
import ast
import os

from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT
from PyInstaller.building.osx import BUNDLE

PROJECT_ROOT = Path.cwd()
BLOCK_CIPHER = None
BUILD_MODE = os.environ.get("ASTROVOID_PYINSTALLER_MODE", "onedir").lower()
ONEFILE_BUILD = BUILD_MODE == "onefile"

# game.py is loaded from bundled data to avoid the game package name collision.
# Analysis cannot follow that dynamic load, so include its imports explicitly.
GAME_IMPORTS = set()
for node in ast.walk(ast.parse((PROJECT_ROOT / "game.py").read_text())):
    if isinstance(node, ast.Import):
        GAME_IMPORTS.update(alias.name for alias in node.names)
    elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
        GAME_IMPORTS.add(node.module)

def collect_tree(source: Path, target: str) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for root, _, filenames in os.walk(source):
        root_path = Path(root)
        for filename in filenames:
            file_path = root_path / filename
            relative = file_path.relative_to(source)
            destination = Path(target) / relative.parent
            items.append((str(file_path), str(destination)))
    return items


DATA_FILES = [
    (str(PROJECT_ROOT / "config" / "settings.json"), "config"),
    (str(PROJECT_ROOT / "config" / "enemies.json"), "config"),
    # main.py loads this file explicitly to avoid the game package name clash.
    (str(PROJECT_ROOT / "game.py"), "."),
]

for name in ("assets", "sounds", "levels"):
    DATA_FILES.extend(collect_tree(PROJECT_ROOT / name, name))

A = Analysis(
    [str(PROJECT_ROOT / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=DATA_FILES,
    hiddenimports=sorted(GAME_IMPORTS) + [
        "entities.hunter_ship_body", "hunter.controller", "hunter.perception",
        "hunter.spawn", "hunter.worker",
        "hunter.rules_pilot", "pymunk",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=BLOCK_CIPHER,
    noarchive=False,
)

PYZ_ARCHIVE = PYZ(A.pure, A.zipped_data, cipher=BLOCK_CIPHER)

# macOS bundles use the windowed bootloader; BUNDLE below creates the .app structure.
import sys
IS_MACOS = sys.platform == 'darwin'
CONSOLE_MODE = not (IS_MACOS and not ONEFILE_BUILD)

EXECUTABLE = EXE(
    PYZ_ARCHIVE,
    A.scripts,
    A.binaries if ONEFILE_BUILD else [],
    A.datas if ONEFILE_BUILD else [],
    exclude_binaries=not ONEFILE_BUILD,
    name="Squiddler",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=CONSOLE_MODE,
    windowed=not CONSOLE_MODE,
)

if not ONEFILE_BUILD:
    DISTRIBUTION = COLLECT(
        EXECUTABLE,
        A.binaries,
        A.zipfiles,
        A.datas,
        strip=False,
        upx=True,
        name="Squiddler",
    )
    if IS_MACOS:
        BUNDLE(
            DISTRIBUTION,
            name="Squiddler.app",
            bundle_identifier="com.bazmatic.squiddler",
            info_plist={"NSHighResolutionCapable": True},
        )
