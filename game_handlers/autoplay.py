"""Decides when an unattended autoplay level is over and which level comes next."""
import time


class AutoplayDirector:
    def __init__(self, first_level, last_level, time_limit, clock=time.monotonic, stuck_seconds=0):
        if last_level < first_level:
            raise ValueError('autoplay lastLevel is before firstLevel')
        self.first_level, self.last_level = first_level, last_level
        self.time_limit, self.clock, self.stuck_seconds = time_limit, clock, stuck_seconds
        self.level = first_level
        self._started_at = clock()
        self._enemies_at_start = 0
        self._hunter_present = False
        self._visited = set()
        self._last_progress = self._started_at

    def start_level(self, enemy_count, hunter_present=True):
        self._started_at = self._last_progress = self.clock()
        self._enemies_at_start = enemy_count
        self._hunter_present = hunter_present
        self._visited = set()

    def end_reason(self, enemies_left, hunter_alive, hunter_cell=None, enemy_near=False):
        """Why the level is over ('hunter_dead', 'cleared', 'stuck' or 'time'), or None.

        Stuck means no new maze cell reached for stuck_seconds, with no enemy near to
        fight. It is only judged when the caller reports the hunter's cell.
        """
        if self._hunter_present and not hunter_alive:
            return 'hunter_dead'
        if self._enemies_at_start and not enemies_left:
            return 'cleared'
        now = self.clock()
        if hunter_cell is not None:
            if hunter_cell not in self._visited or enemy_near:
                self._visited.add(hunter_cell)
                self._last_progress = now
            elif self.stuck_seconds and now - self._last_progress >= self.stuck_seconds:
                return 'stuck'
        if now - self._started_at >= self.time_limit:
            return 'time'
        return None

    def advance(self):
        """The next level, wrapping from the last back to the first."""
        self.level = self.first_level if self.level >= self.last_level else self.level + 1
        return self.level
