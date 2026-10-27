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


def test_bundled_assets_keep_their_original_relative_paths():
    """PyInstaller data destinations are directories, not full output filenames."""
    import ast

    tree = ast.parse((ROOT / 'pyinstaller.spec').read_text())
    collect = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'collect_tree')
    namespace = {'Path': Path, 'os': __import__('os')}
    exec(compile(ast.Module(body=[collect], type_ignores=[]), 'pyinstaller.spec', 'exec'), namespace)
    entries = namespace['collect_tree'](ROOT / 'assets', 'assets')
    source = ROOT / 'assets/fonts/ChakraPetch-Bold.ttf'
    assert (str(source), 'assets/fonts') in entries
