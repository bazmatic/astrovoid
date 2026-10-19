"""Gates in play: pushed for free, pushing back, jammed by anchored enemies, and stopping shots."""
import math

import level_config
from tests.test_exit_policies_game import game, level_file, start  # noqa: F401  (the game fixture)


def gate_level(gates, enemy=None):
    """A loader for a small open level with the given gates and no walls but the border."""
    base = level_file()(0)
    placed = [{'type': enemy, 'cell': [9, 3]}] if enemy else []
    base['layout'] = {'start': [2, 2], 'exit': [10, 10], 'walls': [], 'enemies': placed, 'gates': gates}
    return lambda level: base


FREE = {'cell': [6, 6], 'angle': 0}
MOTOR = {'cell': [6, 6], 'angle': 0, 'motor': 'cw'}


def begin(game, monkeypatch, gates, enemy=None):
    monkeypatch.setattr(level_config, 'load_level_config', gate_level(gates, enemy))
    start(game, 3)
    return game.obstacles.gates[0]


def test_a_level_without_gates_has_no_world(game, monkeypatch):
    monkeypatch.setattr(level_config, 'load_level_config', level_file())
    start(game, 3)
    assert game.obstacles is None
    assert game.maze.gate_segments == []


def test_thrusting_into_a_gate_turns_it_for_free(game, monkeypatch):
    gate = begin(game, monkeypatch, [FREE])
    start_angle = gate.angle
    game.player_has_moved = True
    px, py = gate.pin
    game.ship.x, game.ship.y = px + gate.half_length * 0.8, py - game.ship.radius - gate.thickness / 2 - 4
    game.ship.vx, game.ship.vy = 0.0, 3.0
    for _ in range(60):
        game.ship.vy = max(game.ship.vy, 3.0)
        game.update(1.0)
    assert abs(gate.angle - start_angle) > 0.05
    assert game.scoring.wall_collisions == 0
    assert game.scoring.hits_taken() == 0


def test_a_gate_shoves_an_enemy(game, monkeypatch):
    gate = begin(game, monkeypatch, [MOTOR], 'patrol')
    game.player_has_moved = True
    enemy = game.enemies[0]
    px, py = gate.pin
    enemy.x, enemy.y = px + gate.half_length * 0.7, py + enemy.radius + gate.thickness / 2
    enemy.vx = enemy.vy = 0.0
    before = (enemy.x, enemy.y)
    for _ in range(30):
        game.update(1.0)
    assert math.hypot(enemy.x - before[0], enemy.y - before[1]) > 1.0


def test_an_anemone_jams_a_motor_gate(game, monkeypatch):
    gate = begin(game, monkeypatch, [MOTOR], 'anemone')
    game.player_has_moved = True
    anemone = game.anemones[0]
    px, py = gate.pin
    anemone.x, anemone.y = px + gate.half_length * 0.6, py + anemone.radius + gate.thickness / 2
    anemone.anchor = (anemone.x, anemone.y)
    before = (anemone.x, anemone.y)
    for _ in range(180):
        game.update(1.0)
    assert math.hypot(anemone.x - before[0], anemone.y - before[1]) < 1.0
    # Unjammed, 3 seconds at the motor rate would turn it well over 3 radians
    assert abs(gate.angle) < 1.5


def test_a_player_shot_stops_at_a_gate_and_damages_nothing(game, monkeypatch):
    from entities.projectile import Projectile
    gate = begin(game, monkeypatch, [FREE])
    hit_points = [wall.hit_points for wall in game.maze.walls]
    px, py = gate.pin
    shot = Projectile((px + gate.half_length * 0.5, py - 40.0), 90.0, source='player')
    game.projectiles.append(shot)
    for _ in range(30):
        game.update(1.0)
    assert not shot.active
    assert shot not in game.projectiles
    assert gate.angular_velocity != 0.0 or gate.angle != 0.0
    assert [wall.hit_points for wall in game.maze.walls] == hit_points


def test_restarting_puts_the_gates_back(game, monkeypatch):
    gate = begin(game, monkeypatch, [{'cell': [6, 6], 'angle': 45}])
    bodies = len(game.obstacles.space.bodies)
    gate.body.angle += 1.0
    start(game, 3)
    assert abs(math.degrees(game.obstacles.gates[0].angle) - 45) < 1e-6
    assert len(game.obstacles.space.bodies) == bodies
