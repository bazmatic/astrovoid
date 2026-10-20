"""The Roster: every enemy on the level, of every kind, in one place.

Enemies are kept in the order they were added. Each one names its kind in `type` (see enemy_kinds), and that is how
the roster is asked for some of them. It can be handed to whatever spawns enemies (a Mother laying eggs, an egg
hatching, a flighthouse launching flockers), which add to it as they would to a list.
"""
from typing import Dict, Iterable, List, Tuple

import enemy_kinds


class EnemyRoster:
    """Every enemy on the level, alive, dying or dead, until the level is cleared."""

    def __init__(self):
        self._enemies: List = []

    def add(self, enemy) -> None:
        """Put an enemy on the level."""
        self._enemies.append(enemy)

    # Spawning enemies add to the roster as they would to a list
    append = add

    def extend(self, enemies: Iterable) -> None:
        for enemy in enemies:
            self.add(enemy)

    def clear(self) -> None:
        """Take every enemy off the level."""
        self._enemies.clear()

    def of_kind(self, *kinds: str) -> List:
        """The enemies of these kinds, alive or not, in the order they were added. A new list: adding to the roster
        later does not change it."""
        return [enemy for enemy in self._enemies if enemy.type in kinds]

    def all(self) -> List:
        """Every enemy, alive or not."""
        return list(self._enemies)

    def alive(self) -> List:
        """Every enemy still alive."""
        return [enemy for enemy in self._enemies if enemy.active]

    def positions(self) -> List[Tuple[float, float]]:
        """Where every enemy is, alive or not."""
        return [enemy.get_pos() for enemy in self._enemies]

    def counts(self) -> Dict[str, int]:
        """How many enemies of each kind are alive; kinds with none alive are left out."""
        counts: Dict[str, int] = {}
        for enemy in self.alive():
            counts[enemy.type] = counts.get(enemy.type, 0) + 1
        return counts

    def update_dying(self, dt: float) -> None:
        """Advance the death animation of every enemy that is dying."""
        for enemy in self._enemies:
            if enemy.is_dying:
                enemy.update_death(dt)

    def draw(self, screen) -> None:
        """Draw every live enemy, a kind on a higher layer over one on a lower, then the death animations."""
        for enemy in sorted(self.alive(), key=lambda enemy: enemy_kinds.kind(enemy.type).layer):
            enemy.draw(screen)
        for enemy in self._enemies:
            if enemy.is_dying:
                enemy.draw_death(screen)
