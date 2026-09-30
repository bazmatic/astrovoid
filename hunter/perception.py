"""Local sensor snapshots and bounded memory; only called on the game thread."""
import json
import math
import weakref
from dataclasses import asdict
import config
from hunter.model import HunterSettings, PilotObservation
from hunter.visibility import local_segments, visible_point, visible_wall_portions, visible_cell_edges


def _replace_intervals(old, observed):
    """Replace only observed portions, retaining stale knowledge elsewhere."""
    result = list(old)
    for lo, hi, blocked in observed:
        keep = []
        for a,b,value in result:
            if b <= lo or a >= hi:
                keep.append([a,b,value])
            else:
                if a < lo:
                    keep.append([a,lo,value])
                if b > hi:
                    keep.append([hi,b,value])
        result = keep + [[lo,hi,blocked]]
    merged = []
    for a,b,value in sorted(result):
        if merged and merged[-1][2] == value and abs(merged[-1][1]-a) < 1e-7:
            merged[-1][1] = b
        else:
            merged.append([a,b,value])
    return merged


class HunterPerception:
    def __init__(self, settings=HunterSettings()):
        self.settings = settings
        self.reset()

    def reset(self):
        self._ids = weakref.WeakKeyDictionary()
        self._next_id = 0
        self.contacts = {}
        self.cells = {}
        self._previous_cell = None

    def _id(self, entity):
        if entity not in self._ids:
            self._next_id += 1
            self._ids[entity] = self._next_id
        return self._ids[entity]

    def _contact(self, entity, origin, allegiance):
        dx,dy = entity.x-origin[0], entity.y-origin[1]
        return {'id': self._id(entity), 'type': getattr(entity,'type',type(entity).__name__),
                'allegiance': allegiance, 'position': [entity.x,entity.y],
                'relative_position': [dx,dy], 'velocity': [entity.vx,entity.vy],
                'heading': getattr(entity,'angle',None), 'radius': entity.radius,
                'distance': math.hypot(dx,dy), 'bearing': math.degrees(math.atan2(dy,dx)) % 360}

    def observe(self, hunter, maze, player, enemies, projectiles, previous_action, now, generation):
        origin = hunter.get_pos()
        radius = self.settings.sensor_cells * maze.cell_size_x
        walls = local_segments(origin, [(w.start,w.end) for w in maze.walls if w.active], radius)
        contacts = []
        visible_ids = set()
        for entity in list(enemies) + ([player] if player is not None else []):
            if not visible_point(origin, entity.get_pos(), walls, radius):
                continue
            if not entity.active:
                known_id = self._ids.get(entity)
                if known_id is not None:
                    self.contacts.pop(known_id,None)
                continue
            friendly = entity is player
            contact = self._contact(entity, origin, 'friendly' if friendly else 'enemy')
            contacts.append(contact)
            if not friendly:
                visible_ids.add(contact['id'])
                self.contacts[contact['id']] = (contact,now)
        for key,(contact,seen_at) in list(self.contacts.items()):
            if (now-seen_at >= self.settings.contact_ttl or
                (key not in visible_ids and visible_point(origin, contact['position'], walls, radius))):
                del self.contacts[key]
        oldest = sorted(self.contacts, key=lambda k:(self.contacts[k][1],k))
        for key in oldest[:max(0,len(oldest)-self.settings.max_memory_contacts)]:
            del self.contacts[key]
        contacts.sort(key=lambda c:(c['distance'],c['id']))
        bullets = [self._contact(p,origin,'enemy' if p.is_enemy else 'friendly')
                   for p in projectiles if p.active and visible_point(origin,p.get_pos(),walls,radius)]
        bullets.sort(key=lambda c:(c['distance'],c['id']))
        visible_walls = visible_wall_portions(origin,walls,radius)
        # Frontmost wall portions cast the same shadows as occluded geometry.
        remembered_cells = self._observe_map(origin,maze,visible_walls,radius,now)
        state = {
            'self': {'position': list(origin), 'velocity': [hunter.vx,hunter.vy],
                     'heading': hunter.angle, 'health': hunter.health, 'radius': hunter.radius,
                     'cooldown_seconds': hunter.fire_remaining},
            'cell_size': maze.cell_size_x,
            'sensor_range': radius,
            'previous_action': asdict(previous_action),
            'snapshot_at': now,
            'visible_contacts': contacts[:self.settings.max_contacts],
            'visible_projectiles': bullets[:self.settings.max_projectiles],
            'visible_walls': visible_walls,
            'remembered_contacts': self._remembered_contacts(origin,now),
            'remembered_cells': remembered_cells,
            'physics': {'fps':config.FPS,'speed_limit':hunter.max_speed,
                        'rotation_per_frame':hunter.current_rotation_speed,
                        'thrust_per_frame':config.SHIP_THRUST_FORCE,
                        'friction_per_frame':config.SHIP_FRICTION,
                        'projectile_speed':config.PROJECTILE_SPEED},
            'action_horizon_seconds': self.settings.request_interval,
        }
        return PilotObservation(generation,now,json.dumps(state,separators=(',',':'),allow_nan=False))

    def _remembered_contacts(self, origin, now):
        result = []
        for contact, seen_at in self.contacts.values():
            dx,dy = contact['position'][0]-origin[0],contact['position'][1]-origin[1]
            result.append(dict(contact, age=now-seen_at, relative_position=[dx,dy],
                               distance=math.hypot(dx,dy),
                               bearing=math.degrees(math.atan2(dy,dx)) % 360))
        return result

    def _observe_map(self, origin, maze, walls, radius, now):
        sx,sy,ox,oy = maze.cell_size_x,maze.cell_size_y,maze.offset_x,maze.offset_y
        current = (int((origin[0]-ox)//sx),int((origin[1]-oy)//sy))
        min_col = max(0,int((origin[0]-radius-ox)//sx))
        max_col = min(maze.grid_width-1,int((origin[0]+radius-ox)//sx))
        min_row = max(0,int((origin[1]-radius-oy)//sy))
        max_row = min(maze.grid_height-1,int((origin[1]+radius-oy)//sy))
        edge_cache = {}
        for row in range(min_row,max_row+1):
            for col in range(min_col,max_col+1):
                bounds = (ox+col*sx,oy+row*sy,ox+(col+1)*sx,oy+(row+1)*sy)
                edges = visible_cell_edges(origin,bounds,walls,radius,edge_cache)
                if not any(edges.values()) and (col,row) != current:
                    continue
                cell = self.cells.setdefault((col,row), {'edges':{},'visits':0,'last_visit':None})
                for name,parts in edges.items():
                    if parts:
                        cell['edges'][name] = _replace_intervals(cell['edges'].get(name,[]),parts)
                if (col,row) == current:
                    if current != self._previous_cell:
                        cell['visits'] += 1
                    cell['last_visit'] = now
        self._previous_cell = current
        ordered = sorted(self.cells, key=lambda c:((ox+(c[0]+.5)*sx-origin[0])**2 +
                                                  (oy+(c[1]+.5)*sy-origin[1])**2,c))
        result = []
        directions = {'left':(-1,0),'right':(1,0),'top':(0,-1),'bottom':(0,1)}
        for coord in ordered[:self.settings.max_sent_cells]:
            cell = self.cells[coord]
            exits = []
            for edge,parts in cell['edges'].items():
                dx,dy = directions[edge]
                neighbor = (coord[0]+dx,coord[1]+dy)
                if (0 <= neighbor[0] < maze.grid_width and 0 <= neighbor[1] < maze.grid_height
                        and not self.cells.get(neighbor,{}).get('visits',0)):
                    if any(not blocked for lo,hi,blocked in parts):
                        exits.append(edge)
            result.append({'cell':list(coord), 'center':[ox+(coord[0]+.5)*sx,oy+(coord[1]+.5)*sy],
                           'edges':cell['edges'], 'visits':cell['visits'],
                           'last_visit_age':None if cell['last_visit'] is None else now-cell['last_visit'],
                           'unexplored_exits':exits})
        return result
