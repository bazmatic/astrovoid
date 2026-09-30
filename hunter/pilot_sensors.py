"""Translate sensed geometry into body-relative readings, without choosing controls."""
import math
from hunter.visibility import visible_point


def direction(bearing, heading):
    error = (bearing-heading+180) % 360-180
    if abs(error) <= 20:
        return 'ahead'
    if abs(error) >= 160:
        return 'behind'
    return 'left' if error < 0 else 'right'


def pilot_state(state):
    ship = state.get('self', {})
    origin = ship.get('position', [0,0])
    heading = ship.get('heading', 0)
    radius = ship.get('radius', 10)
    cell_size = state.get('cell_size', 100)
    sensor_range = state.get('sensor_range', cell_size*4)
    walls = state.get('visible_walls', [])

    def contact(c):
        return {'id':c['id'], 'allegiance':c['allegiance'],
                'direction':direction(c['bearing'],heading),
                'range':'near' if c['distance'] < cell_size else 'far',
                'age_seconds':round(c.get('age',0),1)}

    # Three rays per sector measure a small corridor, accounting for ship size.
    # Only locally observed walls are available here; no hidden world queries.
    space = {}
    for name,offset in [('ahead',0),('ahead_left',-45),('left',-90),
                        ('behind_left',-135),('behind',180),('behind_right',135),
                        ('right',90),('ahead_right',45)]:
        clearance = sensor_range
        for spread in (-10,0,10):
            angle = math.radians(heading+offset+spread)
            dx,dy = math.cos(angle),math.sin(angle)
            for a,b in walls:
                ex,ey = b[0]-a[0],b[1]-a[1]
                denom = dx*ey-dy*ex
                if abs(denom) < 1e-9:
                    continue
                ax,ay = a[0]-origin[0],a[1]-origin[1]
                t,u = (ax*ey-ay*ex)/denom,(ax*dy-ay*dx)/denom
                if t >= 0 and 0 <= u <= 1:
                    clearance = min(clearance,t)
        clearance = max(0,clearance-radius)
        space[name] = {'clearance': 'blocked' if clearance < radius*2 else
                       'close' if clearance < cell_size*.75 else 'clear',
                       'distance_cells':round(clearance/cell_size,1)}

    exploration = []
    for cell in state.get('remembered_cells', []):
        dx,dy = cell['center'][0]-origin[0],cell['center'][1]-origin[1]
        distance = math.hypot(dx,dy)
        if distance < cell_size*.35 or not visible_point(origin,cell['center'],walls,sensor_range):
            continue
        exploration.append({'direction':direction(math.degrees(math.atan2(dy,dx)),heading),
                            'visited':bool(cell['visits']),
                            'distance_cells':round(distance/cell_size,1)})
    speed = math.hypot(*ship.get('velocity',[0,0]))
    speed_limit = state.get('physics',{}).get('speed_limit',8)
    visible = state.get('visible_contacts',[])
    visible_ids = {c['id'] for c in visible}
    return {'speed':'fast' if speed > speed_limit*.4 else 'slow',
            'health':ship.get('health',3), 'space':space,
            'visible_contacts':[contact(c) for c in visible],
            'remembered_contacts':[contact(c) for c in state.get('remembered_contacts',[])
                                   if c['id'] not in visible_ids],
            'hostile_projectiles':[contact(c) for c in state.get('visible_projectiles',[])
                                   if c['allegiance']=='enemy'],
            'exploration':exploration[:12]}
