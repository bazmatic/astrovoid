"""The cave field: a smooth rock/open field over the maze cells that later becomes curved walls."""
import config


def test_cave_settings_load_from_settings_json():
    assert config.CAVE.enabled is True
    assert config.CAVE.blurCells == 0.34
    assert config.CAVE.noiseScalesCells == (0.85, 0.35)
    assert config.CAVE.clearanceRadius == 16.0
