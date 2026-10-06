from types import SimpleNamespace
from game_handlers.combat_targets import nearest_friendly


def test_nearest_living_ally_and_player_tiebreak():
    enemy = SimpleNamespace(x=0,y=0)
    player = SimpleNamespace(x=10,y=0,active=True)
    hunter = SimpleNamespace(x=5,y=0,active=True)
    assert nearest_friendly(enemy,player,hunter) is hunter
    hunter.x=10
    assert nearest_friendly(enemy,player,hunter) is player
    hunter.active=False
    assert nearest_friendly(enemy,player,hunter) is player
    player.active=False
    assert nearest_friendly(enemy,player,hunter) is None


import pytest
from unittest.mock import Mock
from entities.command_recorder import CommandRecorder
from entities.enemy import Enemy
from entities.replay_enemy_ship import ReplayEnemyShip
from entities.flocker_enemy_ship import FlockerEnemyShip
from entities.split_boss import SplitBoss
from entities.mother_boss import MotherBoss
from entities.baby import Baby
from entities.ship import Ship
from entities.hunter_ship import HunterShip
from game_handlers.enemy_updater import EnemyUpdater


@pytest.mark.parametrize('kind,method', [
    (Enemy,'update_enemies'), (ReplayEnemyShip,'update_replay_enemies'),
    (FlockerEnemyShip,'update_flockers'), (SplitBoss,'update_split_bosses'),
    (MotherBoss,'update_mother_bosses'), (Baby,'update_babies')])
def test_enemy_update_and_aim_use_nearest_hunter(kind,method):
    if kind is Enemy:
        enemy = Enemy((300,300),'patrol',1)
    elif kind is FlockerEnemyShip:
        enemy = kind((300,300))
    else:
        enemy = kind((300,300),CommandRecorder())
    enemy.update = Mock()
    enemy.get_fired_projectile = Mock(return_value=None)
    enemy.check_wall_collision = Mock(return_value=False)
    enemy.lay_egg = Mock()
    player = Ship((900,800))
    player.shield_active = True
    hunter = HunterShip((320,300))
    kwargs = {'hunter':hunter}
    if kind is MotherBoss:
        kwargs['eggs'] = []
    getattr(EnemyUpdater(),method)([enemy],1,player.get_pos(),Mock(walls=[],spatial_grid=None),
                                  player,Mock(),[],**kwargs)
    assert enemy.update.call_args.args[1] == hunter.get_pos()
    assert enemy.get_fired_projectile.call_args.args[0] == hunter.get_pos()
