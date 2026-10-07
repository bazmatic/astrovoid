"""Profile persistence for player progress tracking."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


DEFAULT_PROFILES_PATH = Path(__file__).resolve().parent / "profiles.json"


@dataclass(frozen=True)
class LevelBest:
    """Independent records for a cleared level."""

    score: int
    time: float
    stars: int


@dataclass(frozen=True)
class LevelResult:
    """How a clear compares with the records before that run."""

    first_clear: bool
    new_best_score: bool
    new_best_time: bool
    stars_gained: int
    previous_best: Optional[LevelBest]


@dataclass
class Profile:
    """Represents a player profile."""

    name: str
    level: int = 1
    total_score: int = 0
    bests: Dict[int, LevelBest] = field(default_factory=dict)


class ProfileManager:
    """Loads and saves profiles, tracks the active profile."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or DEFAULT_PROFILES_PATH
        self.profiles: List[Profile] = []
        self.active_profile_name: Optional[str] = None
        self._load_profiles()

    def _load_profiles(self) -> None:
        """Load profiles from disk, creating defaults if necessary."""
        data = {"profiles": [], "active_profile": None}

        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text())
                data.update(raw)
            except (ValueError, OSError):
                pass

        loaded_profiles: List[Profile] = []
        for entry in data.get("profiles", []):
            try:
                name = str(entry["name"])
                level = max(1, int(entry.get("level", 1)))
                total_score = int(entry.get("total_score", 0))
            except (KeyError, TypeError, ValueError):
                continue

            bests = {}
            raw_bests = entry.get("bests", {})
            if isinstance(raw_bests, dict):
                for key, value in raw_bests.items():
                    try:
                        best_level = int(key)
                        score = value['score']
                        elapsed = value['time']
                        stars = value['stars']
                        if (best_level < 1 or type(score) is not int or score < 0
                                or type(stars) is not int or not 0 <= stars <= 5
                                or type(elapsed) not in (int, float)
                                or not math.isfinite(elapsed) or elapsed < 0):
                            continue
                        bests[best_level] = LevelBest(score, round(elapsed, 1), stars)
                    except (KeyError, TypeError, ValueError, OverflowError):
                        continue
            loaded_profiles.append(Profile(name=name, level=level, total_score=total_score, bests=bests))

        self.profiles = loaded_profiles
        self.active_profile_name = data.get("active_profile")
        self._ensure_active_profile()

    def _ensure_active_profile(self) -> None:
        """Ensure there is always at least one profile and an active profile."""
        if not self.profiles:
            default = Profile(name="Player1")
            self.profiles.append(default)
            self.active_profile_name = default.name
            self._save_profiles()
            return

        if self.active_profile_name is None or not self.get_profile(self.active_profile_name):
            self.active_profile_name = self.profiles[0].name
            self._save_profiles()

    def _save_profiles(self) -> None:
        """Persist profile data to the configured path."""
        payload = {
            "profiles": [
                {
                    "name": profile.name,
                    "level": profile.level,
                    "total_score": profile.total_score,
                    "bests": {str(level): asdict(best) for level, best in profile.bests.items()}
                }
                for profile in self.profiles
            ],
            "active_profile": self.active_profile_name
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(payload, indent=2))
        except OSError:
            pass

    def get_profiles(self) -> List[Profile]:
        """Return all profiles."""
        return list(self.profiles)

    def get_profile(self, name: Optional[str]) -> Optional[Profile]:
        """Return a profile by name."""
        if not name:
            return None
        for profile in self.profiles:
            if profile.name == name:
                return profile
        return None

    def get_active_profile(self) -> Optional[Profile]:
        """Return the currently active profile."""
        return self.get_profile(self.active_profile_name)

    def set_active_profile(self, name: str) -> None:
        """Set the active profile by name."""
        if not self.get_profile(name):
            raise ValueError(f"Profile '{name}' not found.")
        self.active_profile_name = name
        self._save_profiles()

    def create_profile(self, name: str) -> Profile:
        """Add a new profile and make it active."""
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("Profile name cannot be empty.")
        if self.get_profile(cleaned):
            raise ValueError(f"A profile named '{cleaned}' already exists.")

        profile = Profile(name=cleaned)
        self.profiles.append(profile)
        self.active_profile_name = profile.name
        self._save_profiles()
        return profile

    def record_level_result(self, level: int, score: int, time_seconds: float, stars: int) -> LevelResult:
        """Record a successful clear, comparing the same precision shown on screen."""
        profile = self.get_active_profile()
        score, elapsed = int(score), round(time_seconds, 1)
        previous = profile.bests.get(level)
        result = LevelResult(
            first_clear=previous is None,
            new_best_score=previous is None or score > previous.score,
            new_best_time=previous is None or elapsed < previous.time,
            stars_gained=max(0, stars - (previous.stars if previous else 0)),
            previous_best=previous,
        )
        profile.bests[level] = LevelBest(
            score if result.new_best_score else previous.score,
            elapsed if result.new_best_time else previous.time,
            max(stars, previous.stars if previous else 0),
        )
        self._save_profiles()
        return result

    def update_active_profile_progress(self, current_level: int, total_score: int) -> None:
        """Record progress after a successful level completion."""
        profile = self.get_active_profile()
        if not profile:
            return

        next_level = max(profile.level, current_level + 1)
        new_score = max(profile.total_score, total_score)
        profile.level = next_level
        profile.total_score = new_score
        self._save_profiles()

    def get_active_level(self) -> int:
        """Return the next level to play for the active profile."""
        profile = self.get_active_profile()
        return max(1, profile.level) if profile else 1

    def get_active_total_score(self) -> int:
        """Return the total score recorded for the active profile."""
        profile = self.get_active_profile()
        return profile.total_score if profile else 0

