import math
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
    assert state['space']['ahead']['clearance_metres'] == pytest.approx(30-ship.radius)
    assert 'exploration' not in state


def test_metres_speed_heading_and_rotation_use_physics_units():
    ship = HunterShip((150,150))
    ship.vx,ship.vy,ship.angle = 3,4,315
    obs = HunterPerception().observe(ship,maze(),None,[Enemy((250,150),'patrol',1)],[],NEUTRAL,0,1)
    raw = json.loads(obs.state_json)
    state = pilot_state(raw)
    assert state['speed_metres_per_second'] == 5*raw['physics']['fps']
    assert state['heading_degrees'] == 315
    assert state['velocity_heading_degrees'] == pytest.approx(53.130102354)
    fps = raw['physics']['fps']
    motion = state['motion']
    assert motion['velocity_metres_per_second'] == {'x':3*fps,'y':4*fps}
    assert motion['direction'] == 'right'
    assert motion['forward_speed_metres_per_second'] == pytest.approx(-math.sqrt(.5)*fps)
    assert motion['rightward_speed_metres_per_second'] == pytest.approx(7*math.sqrt(.5)*fps)
    assert state['rotation_speed_degrees_per_second'] == ship.current_rotation_speed*raw['physics']['fps']
    assert state['visible_contacts'][0]['distance_metres'] == 100
    assert state['visible_contacts'][0]['heading_degrees'] == 0
    assert 'range' not in state['visible_contacts'][0]


def test_history_is_last_three_nonrecursive_states_and_resets_with_generation():
    perception,ship = HunterPerception(),HunterShip((150,150))
    for now in range(5):
        ship.angle = now*10
        obs = perception.observe(ship,maze(),None,[],[],NEUTRAL,now,1)
    history = json.loads(obs.state_json)['previous_states']
    assert [s['snapshot_at_seconds'] for s in history] == [1,2,3]
    assert [s['heading_degrees'] for s in history] == [10,20,30]
    assert all('previous_states' not in s for s in history)
    obs = perception.observe(ship,maze(),None,[],[],NEUTRAL,5,2)
    assert json.loads(obs.state_json)['previous_states'] == []
    perception.reset()
    obs = perception.observe(ship,maze(),None,[],[],NEUTRAL,6,2)
    assert json.loads(obs.state_json)['previous_states'] == []


def test_motion_reports_seconds_until_wall_impact_when_coasting():
    ship,world = HunterShip((150,150)),maze()
    world.walls = [WallSegment((250,0),(250,900),3)]
    ship.vx,ship.angle = 2,90

    def motion():
        obs = HunterPerception().observe(ship,world,None,[],[],NEUTRAL,0,1)
        raw = json.loads(obs.state_json)
        return pilot_state(raw)['motion'],raw['physics']

    moving,physics = motion()
    assert moving['wall_clearance_metres'] == pytest.approx(100-ship.radius)
    # Fly the same course with the engine off and count frames to contact.
    coaster,frames = HunterShip((150,150)),0
    coaster.vx = 2
    while coaster.x+coaster.radius < 250:
        coaster.step(1,NEUTRAL)
        frames += 1
    assert moving['seconds_to_wall_impact'] == pytest.approx(frames/physics['fps'],abs=1/physics['fps'])
    assert moving['seconds_to_wall_impact'] > (100-ship.radius)/(2*physics['fps'])

    # A wall beside the centre line still catches the edge of the hull.
    world.walls = [WallSegment((250,150+ship.radius/2),(250,900),3)]
    assert motion()[0]['seconds_to_wall_impact'] is not None
    world.walls = [WallSegment((250,150+ship.radius*2),(250,900),3)]
    assert motion()[0]['seconds_to_wall_impact'] is None

    world.walls = [WallSegment((250,0),(250,900),3)]
    ship.vx = .01  # Drag stops the ship long before the wall.
    slow = motion()[0]
    assert slow['wall_clearance_metres'] == pytest.approx(100-ship.radius)
    assert slow['seconds_to_wall_impact'] is None
    ship.vx = -2
    assert motion()[0]['seconds_to_wall_impact'] is None
    ship.vx = 0
    stationary = motion()[0]
    assert stationary['wall_clearance_metres'] is None
    assert stationary['seconds_to_wall_impact'] is None


def test_turning_state_and_bearings_projected_to_next_decision():
    from dataclasses import replace
    ship = HunterShip((150,150))
    ship.angle = 300
    enemy = Enemy((250,150),'patrol',1)

    def state(action):
        obs = HunterPerception().observe(ship,maze(),None,[enemy],[],action,0,1)
        raw = json.loads(obs.state_json)
        return pilot_state(raw),raw

    idle,raw = state(NEUTRAL)
    step = (ship.current_rotation_speed*raw['physics']['fps']
            *max(ship.settings.request_interval,ship.settings.decision_delay))
    assert idle['turning'] == {'direction':'none','degrees_per_decision':pytest.approx(step)}
    contact = idle['visible_contacts'][0]
    assert contact['degrees_off_nose'] == contact['degrees_off_nose_at_next_decision'] == 60

    right = state(replace(NEUTRAL,turn=1))[0]
    assert right['turning']['direction'] == 'right'
    contact = right['visible_contacts'][0]
    assert contact['degrees_off_nose'] == 60
    assert contact['degrees_off_nose_at_next_decision'] == pytest.approx(60-step)

    left = state(replace(NEUTRAL,turn=-1))[0]
    assert left['turning']['direction'] == 'left'
    assert left['visible_contacts'][0]['degrees_off_nose_at_next_decision'] == pytest.approx(60+step)


def test_aim_leads_a_crossing_enemy_and_reports_whether_the_nose_is_on_target():
    import config
    from entities.ship import Ship
    ship = HunterShip((150,150))
    enemy = Enemy((350,150),'patrol',1)

    def contacts(player=None):
        obs = HunterPerception().observe(ship,maze(),player,[enemy],[],NEUTRAL,0,1)
        raw = json.loads(obs.state_json)
        return pilot_state(raw)['visible_contacts'],raw['physics']['fps']

    (still,),fps = contacts()
    assert still['aim']['lead_degrees_off_nose'] == 0
    assert still['aim']['on_target'] and still['aim']['miss_distance_metres'] == 0
    assert still['aim']['seconds_to_hit'] == pytest.approx(200/config.PROJECTILE_SPEED/fps,abs=.01)

    enemy.vy = 2
    (crossing,),_ = contacts()
    aim = crossing['aim']
    assert crossing['degrees_off_nose'] == 0 and aim['lead_degrees_off_nose'] > 5
    assert not aim['on_target'] and aim['miss_distance_metres'] > 0
    # A shot along the lead bearing meets the enemy when it arrives.
    frames = aim['seconds_to_hit']*fps
    lead = math.radians(aim['lead_degrees_off_nose'])
    shot = (150+math.cos(lead)*config.PROJECTILE_SPEED*frames,
            150+math.sin(lead)*config.PROJECTILE_SPEED*frames)
    assert math.hypot(shot[0]-350,shot[1]-(150+2*frames)) < enemy.radius
    ship.angle = aim['lead_degrees_off_nose']
    assert contacts()[0][0]['aim']['on_target']

    ship.angle,enemy.vy = 0,0
    enemy.vx = config.PROJECTILE_SPEED*2  # Outrunning the shot: no solution.
    assert contacts()[0][0]['aim'] is None
    enemy.vx = 0
    friendly = [c for c in contacts(Ship((150,250)))[0] if c['allegiance'] == 'friendly']
    assert friendly and 'aim' not in friendly[0]


def test_brake_solution_compares_speed_with_what_can_be_stopped_before_the_wall():
    ship,world = HunterShip((150,150)),maze()
    world.walls = [WallSegment((350,0),(350,900),3)]

    def brake():
        obs = HunterPerception().observe(ship,world,None,[],[],NEUTRAL,0,1)
        return pilot_state(json.loads(obs.state_json))['motion']['brake']

    parked = brake()
    assert parked['speed_state'] == 'slow' and parked['thrust_effect'] is None
    assert parked['retrograde_degrees_off_nose_at_next_decision'] is None

    ship.vx = 3  # Nose along the course: a stop needs a half turn first.
    fast = brake()
    assert fast['speed_state'] == 'too_fast' and fast['thrust_effect'] == 'speeds_up'
    assert abs(fast['retrograde_degrees_off_nose']) == 180
    assert fast['stopping_distance_metres'] > 200-ship.radius

    ship.angle = 180  # Already in the braking attitude: more speed can be shed in time.
    braking = brake()
    assert braking['thrust_effect'] == 'slows' and braking['retrograde_degrees_off_nose'] == 0
    assert braking['safe_speed_metres_per_second'] > fast['safe_speed_metres_per_second']
    assert braking['stopping_distance_metres'] < fast['stopping_distance_metres']

    ship.angle = 90
    assert brake()['thrust_effect'] == 'sideways'
    ship.angle,ship.vx = 0,.2
    assert brake()['speed_state'] == 'slow'
    # The reported safe speed is the boundary of too_fast.
    ship.vx = 1
    limit = brake()['safe_speed_metres_per_second']/60
    ship.vx = limit*.75
    assert brake()['speed_state'] == 'cruising'


def test_follow_player_routes_around_walls_to_the_player():
    from entities.ship import Ship
    ship,world,player = HunterShip((150,150)),maze(),Ship((350,150))
    enemy = Enemy((150,450),'patrol',1)

    def follow():
        obs = HunterPerception().observe(ship,world,player,[enemy],[],NEUTRAL,0,1)
        return pilot_state(json.loads(obs.state_json))['follow_player']

    assert follow() is not None  # Offered even while enemies remain, for when none is in sight.
    enemy.active = False
    direct = follow()
    assert direct['player_visible'] and direct['degrees_off_nose'] == 0
    assert direct['waypoint_distance_metres'] == direct['route_distance_metres'] == 200
    assert not direct['alongside']

    # A wall between them, open only below: the route detours and the waypoint is
    # a cell centre in plain sight, not the hidden player.
    world.walls = [WallSegment((200,0),(200,200),3),WallSegment((300,0),(300,200),3)]
    detour = follow()
    assert not detour['player_visible']
    assert detour['route_distance_metres'] > 200
    assert detour['direction'] == 'right' and 0 < detour['degrees_off_nose'] <= 90

    world.walls = []
    player.x = 200
    assert follow()['alongside']
    player.active = False
    assert follow() is None
