"""All text uses the bundled typeface."""
import pathlib
import re

import pygame
from rendering import fonts


def test_bundled_font_differs_from_the_builtin_one():
    pygame.font.init()
    ours = fonts.get_font(36).render("SQUIDDLER 0123", True, (255, 255, 255))
    builtin = pygame.font.Font(None, 36).render("SQUIDDLER 0123", True, (255, 255, 255))
    assert pygame.image.tostring(ours, "RGBA") != pygame.image.tostring(builtin, "RGBA")
    # Much the same visual size, so existing layouts still fit
    assert abs(ours.get_width() - builtin.get_width()) < builtin.get_width() * 0.2


def test_fonts_are_cached():
    assert fonts.get_font(24) is fonts.get_font(24)
    assert fonts.get_font(24, bold=True) is not fonts.get_font(24, bold=False)


def test_missing_font_file_falls_back(monkeypatch):
    monkeypatch.setattr(fonts, 'BOLD_PATH', "assets/fonts/missing.ttf")
    monkeypatch.setattr(fonts, '_fonts', {})
    assert fonts.get_font(40).render("ok", True, (255, 255, 255)).get_width() > 0


def test_no_code_builds_the_builtin_font_directly():
    root = pathlib.Path(__file__).parent.parent
    offenders = []
    for folder in ("rendering", "entities", "states", "game_handlers"):
        for path in (root / folder).glob("*.py"):
            if path.name != "fonts.py" and re.search(r"font\.Font\(None", path.read_text()):
                offenders.append(path.name)
    if re.search(r"font\.Font\(None", (root / "game.py").read_text()):
        offenders.append("game.py")
    assert offenders == []


def test_fonts_survive_pygame_restarting():
    stale = fonts.get_font(24)
    pygame.quit()
    pygame.init()
    fresh = fonts.get_font(24)
    assert fresh is not stale
    assert fresh.render("ok", True, (255, 255, 255)).get_width() > 0
