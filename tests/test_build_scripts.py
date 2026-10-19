"""The build scripts install the game's requirements before bundling it, and stop if pymunk is missing: PyInstaller
only warns about a missing module, and the built game would crash at launch."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize('script', ['build.sh', 'build.bat'])
def test_a_build_installs_the_requirements_and_needs_pymunk(script):
    text = (ROOT / script).read_text()
    bundling = text.index('PyInstaller pyinstaller.spec')
    assert -1 < text.find('pip install -r requirements.txt') < bundling
    assert -1 < text.find('import pymunk') < bundling
