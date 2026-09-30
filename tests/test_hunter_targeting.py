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
