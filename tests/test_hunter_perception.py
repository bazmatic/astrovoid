import pytest
import json
from types import SimpleNamespace
from dataclasses import replace
from entities.hunter_ship import HunterShip
from entities.enemy import Enemy
from maze.wall_segment import WallSegment
from hunter.model import NEUTRAL, HunterSettings
from hunter.perception import HunterPerception


def maze():
    return SimpleNamespace(cell_size_x=100, cell_size_y=100, offset_x=0, offset_y=0,
                           grid_width=10, grid_height=10, walls=[])


def read(perception, hunter, world, enemies, now):
    return json.loads(perception.observe(hunter, world, None, enemies, [], NEUTRAL, now, 1).state_json)


def test_hidden_motion_does_not_rewrite_sighting():
    p, h, m = HunterPerception(), HunterShip((150,150)), maze()
    e = Enemy((250,150),'patrol',1)
    first = read(p,h,m,[e],0)
    assert len(first['visible_contacts']) == 1
    m.walls = [WallSegment((200,0),(200,900),3)]
    e.x = 300
    state = read(p,h,m,[e],1)
    assert not state['visible_contacts']
    assert state['remembered_contacts'][0]['position'] == [250,150]
    assert state['remembered_contacts'][0]['age'] == 1
    assert not read(p,h,m,[e],11)['remembered_contacts']


def test_contact_caps_do_not_erase_visible_memory_and_snapshot_is_detached():
    settings = replace(HunterSettings(), max_contacts=1, max_memory_contacts=2)
    p, h, m = HunterPerception(settings), HunterShip((150,150)), maze()
    enemies = [Enemy((200+i*10,150),'patrol',1) for i in range(3)]
    snap = p.observe(h,m,None,enemies,[],NEUTRAL,0,1)
    for e in enemies:
        e.x = 300
    state = json.loads(snap.state_json)
    assert state['visible_contacts'][0]['position'] == [200,150]
    assert len(state['remembered_contacts']) == 2
    assert len(read(p,h,m,enemies,1)['remembered_contacts']) == 2
    p.reset()
    assert not read(p,h,m,[],2)['remembered_contacts']


def test_visible_empty_position_removes_sighting():
    p,h,m = HunterPerception(), HunterShip((150,150)), maze()
    read(p,h,m,[Enemy((250,150),'patrol',1)],0)
    assert not read(p,h,m,[],1)['remembered_contacts']


def test_observed_death_removes_old_hidden_sighting():
    p,h,m = HunterPerception(),HunterShip((150,150)),maze()
    enemy = Enemy((250,150),'patrol',1)
    read(p,h,m,[enemy],0)
    m.walls = [WallSegment((200,0),(200,900),3)]
    enemy.x=160
    enemy.active=False
    assert not read(p,h,m,[enemy],1)['remembered_contacts']


def test_route_follows_an_opening_blasted_through_a_wall_cell():
    from entities.ship import Ship
    world = maze()
    # Column 2 is solid wall in the generated grid, built as per-cell edges.
    world.grid = [[1 if x == 2 else 0 for x in range(10)] for _ in range(10)]
    edges = {}
    for y in range(10):
        left = WallSegment((200,y*100),(200,y*100+100),3)
        right = WallSegment((300,y*100),(300,y*100+100),3)
        edges[y] = (left,right)
        world.walls += [left,right,WallSegment((200,y*100),(300,y*100),3),
                        WallSegment((200,y*100+100),(300,y*100+100),3)]
    p,h,player = HunterPerception(),HunterShip((150,150)),Ship((350,150))

    def route():
        obs = p.observe(h,world,player,[],[],NEUTRAL,0,1)
        return json.loads(obs.state_json)['follow_player']['route_distance']

    assert route() is None
    for wall in edges[1]:
        wall.active = False
    # The grid still marks the cell as wall; the destroyed edges open it.
    assert route() == 200


def test_sight_range_is_the_same_distance_whatever_the_cell_size():
    """Sight is a share of the maze's width, so a denser maze does not shorten it."""
    settings = HunterSettings()
    coarse, dense = maze(), maze()
    dense.grid_width = dense.grid_height = 30
    dense.cell_size_x = dense.cell_size_y = 1000 / 30
    assert settings.sensor_range(coarse) == pytest.approx(settings.sensor_range(dense)) == pytest.approx(400)

    def sees(world, distance):
        state = read(HunterPerception(), HunterShip((150, 150)), world, [Enemy((150 + distance, 150), 'patrol', 1)], 0)
        return len(state['visible_contacts']) == 1

    for world in (coarse, dense):
        assert sees(world, 390)
        assert not sees(world, 410)
