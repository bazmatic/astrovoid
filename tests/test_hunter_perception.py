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


def test_hidden_wall_destruction_does_not_update_memory_until_reobserved():
    p,h,m = HunterPerception(),HunterShip((150,150)),maze()
    wall = WallSegment((200,100),(200,200),3)
    m.walls = [wall]
    first = read(p,h,m,[],0)
    old = next(c for c in first['remembered_cells'] if c['cell']==[1,1])
    assert any(part[2] for part in old['edges']['right'])
    h.x=h.y=850
    wall.active=False
    hidden = read(p,h,m,[],1)
    same = next(c for c in hidden['remembered_cells'] if c['cell']==[1,1])
    assert same['edges']['right'] == old['edges']['right']
    h.x=h.y=150
    seen = read(p,h,m,[],2)
    changed = next(c for c in seen['remembered_cells'] if c['cell']==[1,1])
    assert not any(part[2] for part in changed['edges']['right'])
    assert changed['visits']==2


def test_observed_death_removes_old_hidden_sighting():
    p,h,m = HunterPerception(),HunterShip((150,150)),maze()
    enemy = Enemy((250,150),'patrol',1)
    read(p,h,m,[enemy],0)
    m.walls = [WallSegment((200,0),(200,900),3)]
    enemy.x=160
    enemy.active=False
    assert not read(p,h,m,[enemy],1)['remembered_contacts']
