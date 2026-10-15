"""Generated levels and laid-out levels make their enemies through one factory."""
from entities.command_recorder import CommandRecorder
from game_handlers import spawn_manager
from game_handlers.entity_manager import EntityManager
from game_handlers.spawn_manager import SpawnManager
from level_rules import EnemyCounts


def test_a_generated_level_makes_every_enemy_through_make_enemy(monkeypatch):
    made = []
    real = spawn_manager.make_enemy

    def counting(kind, *args):
        made.append(kind)
        return real(kind, *args)
    monkeypatch.setattr(spawn_manager, 'make_enemy', counting)
    counts = EnemyCounts(total=3, static=1, patrol=1, aggressive=1, replay=1, flocker=2, flighthouse=1, egg=1,
                         anemone=1)
    positions = [(300.0 + 200.0 * col, 200.0 + 200.0 * row) for col in range(6) for row in range(4)]
    manager = SpawnManager(EntityManager())
    manager.spawn_all_enemies(5, positions, CommandRecorder(), counts, 1, 1)
    assert sorted(made) == sorted(['static', 'patrol', 'aggressive', 'replay', 'flocker', 'flocker', 'flighthouse',
                                   'egg', 'anemone', 'split_boss', 'mother_boss'])
    assert len(list(manager.entity_manager.get_all_enemies())) == len(made)
