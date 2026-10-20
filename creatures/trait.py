"""A Trait: one piece of a Creature's behaviour, configured from the catalogue.

A trait is stateless: what it keeps for one creature lives on that creature. Every hook does nothing by default, so a
trait overrides only the ones it needs.
"""
from typing import Mapping, Tuple


class Trait:
    NAME: str = ''                   # its name in config/enemies.json
    REQUIRES: Tuple[str, ...] = ()   # traits a creature must also have for this one to work
    CROWD: bool = False              # has on_crowd, run once a frame for all live creatures of the kind

    @classmethod
    def from_params(cls, params: Mapping) -> 'Trait':
        """The trait with these catalogue parameters. A parameter it does not take raises ValueError."""
        try:
            return cls(**params)
        except TypeError as error:
            raise ValueError(f'trait {cls.NAME!r}: bad parameters {dict(params)}: {error}') from None

    def on_spawn(self, c, enc) -> None:
        """Once, when the creature joins the encounter: set up its state."""

    def on_frame(self, c, enc, dt: float) -> None:
        """Every frame while the creature lives."""

    def on_shot(self, c, shot, enc) -> None:
        """A friendly shot struck the creature."""

    def on_death(self, c, enc) -> None:
        """The creature died."""

    def on_event(self, c, name: str, enc) -> None:
        """Another trait emitted an event on the creature."""

    def on_crowd(self, creatures, enc, dt: float) -> None:
        """Once a frame, with every live creature of a kind that has this trait (CROWD traits only)."""
