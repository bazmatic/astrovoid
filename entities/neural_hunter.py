"""The Neural hunter: the neural pilot's hunter ship, flown as an enemy that hunts only its protagonist."""
import config
from entities.enemy_hunter import EnemyHunter
from hunter.flight import NeuralPilot
from hunter.settings_for import hunter_settings_for


class NeuralHunter(EnemyHunter):
    # Magenta: apart from the red Rules hunter and the green allied hunter.
    COLOR = (255, 90, 230)
    FILL = (100, 20, 95)
    NOSE_COLOR = (255, 210, 245)
    COCKPIT_COLOR = (55, 10, 50)
    ENGINE_COLOR = (170, 50, 140)
    ENGINE_LIT_COLOR = (255, 140, 230)

    def __init__(self, start_pos, policy, surroundings):
        """`policy` is the neural pilot's (see hunter.neural.loader.load_neural_policy); None: drawn, never flown."""
        pilot = None if policy is None else NeuralPilot(policy, config.SETTINGS.game.neuralDecisionFrames)
        super().__init__(start_pos, hunter_settings_for('neural'), pilot, surroundings)
