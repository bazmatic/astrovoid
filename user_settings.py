"""Player settings chosen on the Settings screen, kept on disk across sessions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import sounds


DEFAULT_SETTINGS_PATH = Path(__file__).resolve().parent / "player_settings.json"


class UserSettings:
    """Loads and saves the player's settings, and puts each one into effect."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or DEFAULT_SETTINGS_PATH
        self.sound = True
        self._load()
        sounds.set_muted(not self.sound)

    def _load(self) -> None:
        """Read saved settings; anything missing or unreadable keeps its default."""
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text())
        except (ValueError, OSError):
            return
        if isinstance(raw, dict) and isinstance(raw.get("sound"), bool):
            self.sound = raw["sound"]

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"sound": self.sound}, indent=2))
        except OSError:
            pass

    def set_sound(self, on: bool) -> None:
        """Turn all game sound on or off."""
        self.sound = on
        sounds.set_muted(not on)
        self._save()
