"""The Rules hunter: the Rules pilot's hunter ship, flown as an enemy that hunts only its protagonist."""
import time

from entities.enemy_hunter import ENEMY_HUNTER_HIT_POINTS, EnemyHunter
from hunter.flight import WorkerPilot
from hunter.settings_for import hunter_settings_for

RULES_HUNTER_HIT_POINTS = ENEMY_HUNTER_HIT_POINTS


class RulesHunter(EnemyHunter):
    type = 'rules_hunter'  # the enemy kind a level file names
    # The enemy colour: red, where the allied hunter is green and the Neural hunter magenta.
    COLOR = (255, 90, 90)
    FILL = (110, 25, 25)
    NOSE_COLOR = (255, 215, 200)
    COCKPIT_COLOR = (60, 10, 10)
    ENGINE_COLOR = (170, 60, 20)
    ENGINE_LIT_COLOR = (255, 150, 80)

    def __init__(self, start_pos, worker, surroundings, clock=time.monotonic):
        super().__init__(start_pos, hunter_settings_for('rules'), WorkerPilot(worker, clock), surroundings, worker)
