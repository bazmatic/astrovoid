"""Local sensor snapshots and bounded memory; only called on the game thread."""
import json
import math
import weakref
from collections import deque
from types import FunctionType
from hunter.pilot_sensors import pilot_state
from dataclasses import asdict
import config
from hunter.model import HunterSettings, PilotObservation
from hunter.maze_route import MazeRoutes
from hunter.visibility import local_segments, visible_point, visible_wall_portions


class HunterPerception:
    def __init__(self, settings=HunterSettings()):
        self.settings = settings
        self.reset()

    def reset(self):
        self._ids = weakref.WeakKeyDictionary()
        self._next_id = 0
        self.contacts = {}
        self._history = deque(maxlen=3)
        self._history_generation = None
        self._routes = MazeRoutes()

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

    def perceive(self, hunter, surroundings, previous_action, now, generation):
        """The observation of `surroundings` (see hunter.surroundings) as they are now."""
        return self.observe(hunter, surroundings.maze, surroundings.friend(), surroundings.enemies(),
                            surroundings.threats(), previous_action, now, generation,
                            powerups=surroundings.pickups())

    def observe(self, hunter, maze, player, enemies, projectiles, previous_action, now, generation,
                powerups=()):
        origin = hunter.get_pos()
        radius = self.settings.sensor_range(maze)
        # The maze's walls as merged for sight (curved rock has many short ones), and the gates as they stand
        rock = maze.sight_segments() if isinstance(getattr(type(maze), 'sight_segments', None), FunctionType) else [
            (w.start,w.end) for w in maze.walls if w.active]
        sight = list(rock) + [(w.start,w.end) for w in getattr(maze, 'gate_segments', ()) if w.active]
        walls = local_segments(origin, sight, radius)
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
        # Powerups are sensed like anything else: only those in plain sight, nearest first.
        crystals = [self._contact(p,origin,'powerup') for p in powerups
                    if p.active and visible_point(origin,p.get_pos(),walls,radius)]
        crystals.sort(key=lambda c:(c['distance'],c['id']))
        visible_walls = visible_wall_portions(origin,walls,radius)
        state = {
            'self': {'position': list(origin), 'velocity': [hunter.vx,hunter.vy],
                     'heading': hunter.angle, 'health': hunter.health, 'radius': hunter.radius,
                     'cooldown_seconds': hunter.fire_remaining,
                     'thrust_frames': getattr(hunter,'thrust_frames',0)},
            'cell_size': maze.cell_size_x,
            'sensor_range': radius,
            'previous_action': asdict(previous_action),
            'snapshot_at': now,
            # Whether any enemy is still alive anywhere, seen or not (an ally is told the level is not clear).
            'enemies_present': any(getattr(enemy, 'active', True) for enemy in enemies),
            'visible_contacts': contacts[:self.settings.max_contacts],
            'visible_projectiles': bullets[:self.settings.max_projectiles],
            'visible_powerups': crystals[:self.settings.max_contacts],
            'visible_walls': visible_walls,
            'remembered_contacts': self._remembered_contacts(origin,now),
            'physics': {'fps':config.FPS,'speed_limit':hunter.max_speed,
                        'rotation_per_frame':hunter.current_rotation_speed,
                        'thrust_per_frame':hunter.thrust_force,
                        'friction_per_frame':config.SHIP_FRICTION,
                        'projectile_speed':config.PROJECTILE_SPEED,
                        'projectile_lifetime':config.PROJECTILE_LIFETIME,
                        'projectile_radius':config.PROJECTILE_SIZE},
            # A choice made from this snapshot lands roughly one round trip later.
            'action_horizon_seconds': max(self.settings.request_interval,
                                          self.settings.decision_delay),
        }
        if player is not None and player.active:
            state['follow_player'] = self._route_to_player(origin,player,maze,walls,radius)
        if self._history_generation != generation:
            self._history.clear()
            self._history_generation = generation
        state['previous_states'] = list(self._history)
        self._history.append(pilot_state(state))
        return PilotObservation(generation,now,json.dumps(state,separators=(',',':'),allow_nan=False))

    def _route_to_player(self, origin, player, maze, walls, radius):
        """The player guides the hunter in: a cell route through the maze and its next waypoint."""
        target = tuple(player.get_pos())
        found = self._routes.route(maze, origin, [target])
        route = found[1] if found else []
        # Head for the furthest point of the route that is in plain sight.
        points = [target]+route
        waypoint = next((p for p in points if visible_point(origin,p,walls,radius)),
                        route[-1] if route else target)
        legs = [tuple(origin)]+route[::-1]+[target]
        dx,dy = waypoint[0]-origin[0],waypoint[1]-origin[1]
        return {'waypoint':list(waypoint), 'bearing':math.degrees(math.atan2(dy,dx)) % 360,
                'waypoint_distance':math.hypot(dx,dy),
                'route_distance':(sum(math.dist(a,b) for a,b in zip(legs,legs[1:]))
                                  if found else None),
                'player_distance':math.dist(origin,target),
                'player_visible':waypoint == target}

    def _remembered_contacts(self, origin, now):
        result = []
        for contact, seen_at in self.contacts.values():
            dx,dy = contact['position'][0]-origin[0],contact['position'][1]-origin[1]
            result.append(dict(contact, age=now-seen_at, relative_position=[dx,dy],
                               distance=math.hypot(dx,dy),
                               bearing=math.degrees(math.atan2(dy,dx)) % 360))
        return result
