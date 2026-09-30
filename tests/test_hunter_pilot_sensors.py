import json
import pytest
from entities.hunter_ship import HunterShip
from entities.enemy import Enemy
from hunter.perception import HunterPerception
from hunter.model import NEUTRAL
from hunter.pilot_sensors import pilot_state
from tests.test_hunter_perception import maze
from maze.wall_segment import WallSegment


@pytest.mark.parametrize('heading,direction', [(45,'left'),(0,'ahead'),(315,'right'),(180,'behind')])
def test_real_observation_reports_enemy_direction_relative_to_nose(heading,direction):
    ship = HunterShip((150,150))
    ship.angle = heading
    obs = HunterPerception().observe(ship,maze(),None,[Enemy((250,150),'patrol',1)],[],NEUTRAL,0,1)
    state = pilot_state(json.loads(obs.state_json))
    assert state['visible_contacts'][0]['direction'] == direction


def test_navigation_sensors_do_not_offer_cells_behind_a_wall():
    ship,world = HunterShip((150,150)),maze()
    world.walls = [WallSegment((180,0),(180,900),3)]
    obs = HunterPerception().observe(ship,world,None,[Enemy((250,150),'patrol',1)],[],NEUTRAL,0,1)
    state = pilot_state(json.loads(obs.state_json))
    assert state['visible_contacts'] == []
    assert state['space']['ahead']['clearance'] in ('blocked','close')
    assert all(c['direction'] != 'ahead' for c in state['exploration'])
