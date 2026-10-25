"""Ordered swept contacts shared by every weapon projectile behaviour."""
import config
from weapons.geometry import segment_contact


def advance(shot, dt, maze, targets, hit_target, trigger_blast, obstacles=None):
    if not shot.active:
        return
    targets = tuple(t for t in targets if t.active)
    walls = _surfaces(shot,dt,maze,obstacles,targets)
    generation = getattr(maze,'wall_generation',0)
    segments = [(a,b) for a,b,_,_ in walls]
    shot.prepare(dt,targets,segments)
    remaining = min(dt,shot.lifetime)
    shot.previous = shot.get_pos()
    # Bound pathological zero-time corner contacts; remaining movement is discarded.
    budget = len(targets)+len(walls)+len(getattr(maze,'blocks',{}))+12
    for _ in range(budget):
        if remaining <= 1e-9 or not shot.active:
            break
        if getattr(maze,'wall_generation',0) != generation:
            # Removing rock exposes previously hidden faces, including adjoining blocks.
            walls = _surfaces(shot,remaining,maze,obstacles,targets)
            generation = getattr(maze,'wall_generation',0)
            segments = [(a,b) for a,b,_,_ in walls]
        start,delta = shot.get_pos(),(shot.vx*remaining,shot.vy*remaining)
        contacts = []
        for index,(a,b,thickness,wall) in enumerate(walls):
            if wall is not None and hasattr(wall,'active') and not wall.active:
                continue
            contact = segment_contact(start,delta,a,b,shot.radius+thickness)
            if contact is not None:
                contacts.append((contact[0],0,index,wall,contact[1]))
        for index,target in enumerate(targets):
            if not target.active or target in shot.hit_targets:
                continue
            t = shot.target_contact(start,delta,target,segments)
            if t is not None:
                contacts.append((t,1,index,target,None))
        if not contacts:
            shot.x += delta[0]
            shot.y += delta[1]
            break
        t,kind,_,obj,normal = min(contacts,key=lambda c:c[:3])
        shot.x += delta[0]*t
        shot.y += delta[1]*t
        remaining *= 1-t
        if kind == 0:
            shot.hit_surface(normal,obj,maze,obstacles)
        else:
            shot.hit_target(obj,hit_target,trigger_blast)
    shot.finish(dt,trigger_blast)
    if shot.x < -100 or shot.x > config.SCREEN_WIDTH+100 or shot.y < -100 or shot.y > config.SCREEN_HEIGHT+100:
        shot.active = False


def _surfaces(shot, dt, maze, obstacles, targets):
    grid = getattr(maze,'spatial_grid',None)
    nearby = grid.get_nearby_walls(shot.get_pos(),shot.query_radius(dt,targets)) if grid is not None else maze.walls
    walls = [(w.start,w.end,0,w) for w in nearby if w.active]
    if obstacles is not None:
        walls += [(a,b,g.thickness/2,g) for g in obstacles.gates for a,b in (g.ends(),)]
    return walls + list(shot.extra_surfaces())
