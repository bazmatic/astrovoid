"""Decides when an unattended autoplay level is over and which level comes next."""
import time


class AutoplayDirector:
    def __init__(self, first_level, last_level, time_limit, clock=time.monotonic, no_kill_seconds=0):
        if last_level < first_level:
            raise ValueError('autoplay lastLevel is before firstLevel')
        self.first_level, self.last_level = first_level, last_level
        self.time_limit, self.clock, self.no_kill_seconds = time_limit, clock, no_kill_seconds
        self.level = first_level
        self._started_at = clock()
        self._enemies_at_start = 0
        self._hunter_present = False
        self._enemies_seen = 0
        self._last_kill = self._started_at

    def start_level(self, enemy_count, hunter_present=True):
        self._started_at = self._last_kill = self.clock()
        self._enemies_at_start = self._enemies_seen = enemy_count
        self._hunter_present = hunter_present

    def end_reason(self, enemies_left, hunter_alive):
        """Why the level is over ('hunter_dead', 'cleared', 'no_kill' or 'time'), or None.

        A kill is the live enemy count falling. The player is parked, so that is the hunter's.
        """
        if self._hunter_present and not hunter_alive:
            return 'hunter_dead'
        if self._enemies_at_start and not enemies_left:
            return 'cleared'
        now = self.clock()
        if enemies_left < self._enemies_seen:
            self._last_kill = now
        self._enemies_seen = enemies_left
        if self.no_kill_seconds and now - self._last_kill > self.no_kill_seconds:
            return 'no_kill'
        if now - self._started_at >= self.time_limit:
            return 'time'
        return None

    def advance(self):
        """The next level, wrapping from the last back to the first."""
        self.level = self.first_level if self.level >= self.last_level else self.level + 1
        return self.level
