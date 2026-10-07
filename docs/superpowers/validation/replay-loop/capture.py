import os
import time
import tempfile
from pathlib import Path
import pygame
import config
import level_config
from game import Game
from profiles import ProfileManager

pygame.init()
config.SCREEN_WIDTH, config.SCREEN_HEIGHT = 1352, 878
config.SPLASH_ENABLED = False
screen = pygame.display.set_mode((1352, 878))
pygame.display.set_caption('Squiddler — Replay loop preview')
print('Display driver:', pygame.display.get_driver(), flush=True)
assert pygame.display.get_driver() != 'dummy'
manager = ProfileManager(Path(tempfile.mkdtemp()) / 'profiles.json')
manager.update_active_profile_progress(16, 2048)
for level in range(1, 17):
    manager.record_level_result(level, 40 + level * 3, 55.2 - level, min(5, 2 + level % 4))
Game.__init__.__globals__['ProfileManager'] = lambda: manager
level_config.level_has_hunter = lambda level: False
os.environ.pop('START_LEVEL', None)
game = Game(screen)
output = Path('docs/superpowers/validation/replay-loop')

def capture(name):
    pygame.event.pump()
    game.draw()
    pygame.image.save(screen, str(output / (name + '.png')))

game.state = config.STATE_MENU
game.update(1)
capture('main-menu')
game.main_menu.menu_selected_index = game.main_menu.menu_options.index('LEVELS')
game.state_handler_registry.get_handler(game.state).handle_keyboard(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN), game)
capture('level-select')
game.level_select_menu.selected_level = 4
game.state_handler_registry.get_handler(game.state).handle_keyboard(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN), game)
capture('playing-restart-hint')
game.game_over_active = True
game.game_over_start_time = time.time() - 0.51
capture('power-out-restart-hint')
game.game_over_active = False
# Use a near-perfect run so the stricter 95-point cutoff still yields five stars.
game.scoring.level_start_time = time.time() - 1.5
game.complete_level()
# Freeze the animation at exact times, using the same update and draw path as play.
game.update(1.28 * 60)
capture('stars-mid-burst')
game.update(0.72 * 60)
capture('five-star-flash')
game.update(1.05 * 60)
capture('new-best')
game.level_succeeded = False
game.star_animation = None
capture('failed-retry-hint')
game.state = config.STATE_CONTROLS
capture('controls')
print('Saved:', output, flush=True)
game._close_hunter()
pygame.quit()
