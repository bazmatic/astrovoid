"""Living weed: plants on the cave rock, and the spores they scatter.

A Flora is every plant and spore in one cave. Plants grow on soil: the faces of breakable rock (outer rock counts;
strong metal walls do not). A plant goes when its rock does.

A ripe pod bursts into spores, which drift through open water. One that touches soil takes root there as a seed,
unless a living plant is too near; one that touches anything else, or drifts too long, is gone. Crowding is what
keeps the numbers steady: in a cave most spores would find rock.

A plant starts as a seed on the rock, grows into a tuft of blades, then fruits: it puts up stalks whose pods swell and
burst, several times over. Then it withers and is gone. Its stages are fixed when it is made, as the ages at which
each one ends, so a long step crosses them as surely as many short ones.
"""
import bisect
import itertools
import math
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple, Union

import config
from utils import circle_line_collision, circle_line_collision_swept, get_closest_point_on_line, line_line_collision

Point = Tuple[float, float]
Color = Tuple[int, int, int]

COLORS = ((70, 170, 120), (95, 190, 110), (60, 150, 140))


@dataclass(eq=False)
class Plant:
    """One plant growing out of the rock."""
    base: Point                # where it meets the rock
    direction: Point           # unit vector pointing away from the rock
    cell: Tuple[int, int]      # the block whose rock it grows on
    age: float                 # frames
    fruitings: int
    stalks: int
    phase: float               # where in its sway it is
    color: Color
    seed_end: float
    grow_end: float
    bursts: Tuple[float, ...]  # the age at which each fruiting's pods burst
    pod_frames: float
    death: float

    @classmethod
    def new(cls, base: Point, direction: Point, cell: Tuple[int, int], rng: random.Random, settings,
            age: float = 0.0) -> 'Plant':
        """A plant of this age, its stages rolled from the settings."""
        def last(frames: float) -> float:
            return frames * rng.uniform(1.0 - settings.lifeJitter, 1.0 + settings.lifeJitter)

        seed_end = last(settings.seedFrames)
        grow_end = seed_end + last(settings.growFrames)
        pod_frames = last(settings.podFrames)
        fruitings = rng.randint(settings.fruitingsMin, settings.fruitingsMax)
        bursts, ripe = [], grow_end
        for fruiting in range(fruitings):
            if fruiting:
                ripe += last(settings.restFrames)
            ripe += pod_frames
            bursts.append(ripe)
        return cls(base=base, direction=direction, cell=cell, age=age, fruitings=fruitings,
                   stalks=rng.randint(settings.stalksMin, settings.stalksMax), phase=rng.uniform(0.0, math.tau),
                   color=rng.choice(COLORS), seed_end=seed_end, grow_end=grow_end, bursts=tuple(bursts),
                   pod_frames=pod_frames, death=ripe + last(settings.witherFrames))

    @property
    def stage(self) -> str:
        if self.age < self.seed_end:
            return 'seed'
        if self.age < self.grow_end:
            return 'growing'
        if self.age < self.bursts[-1]:
            return 'fruiting'
        return 'withering'

    @property
    def growth(self) -> float:
        """0 as it starts growing, 1 once grown."""
        return max(0.0, min(1.0, (self.age - self.seed_end) / (self.grow_end - self.seed_end)))

    @property
    def pod_ripeness(self) -> float:
        """0 as a pod starts to swell, nearly 1 as it bursts; 0 while no pod is swelling."""
        for burst in self.bursts:
            if burst - self.pod_frames <= self.age < burst:
                return (self.age - (burst - self.pod_frames)) / self.pod_frames
        return 0.0

    @property
    def withered(self) -> float:
        """0 as it starts to wither, 1 at its death."""
        return max(0.0, min(1.0, (self.age - self.bursts[-1]) / (self.death - self.bursts[-1])))

    @property
    def dead(self) -> bool:
        return self.age >= self.death

    def advance(self, dt: float) -> int:
        """Age it by dt frames. Returns how many pods burst meanwhile."""
        before, self.age = self.age, self.age + dt
        return self.stalks * sum(1 for burst in self.bursts if before < burst <= self.age)


@dataclass(eq=False)
class Spore:
    """A spore drifting through open water."""
    x: float
    y: float
    vx: float
    vy: float
    age: float   # frames
    life: float  # frames it drifts before it fades
    clear: float = 0.0  # px it can still drift before it could touch rock


class Flora:
    """Every plant and spore in one cave, stepped and drawn with it."""
    STALK = 12.0  # px from the rock to a pod
    SCATTER = math.radians(60)  # spores leave a pod up to this far either side of straight out
    CLEAR_REACH = 24.0  # px: how far a spore looks for rock, so it need not look again until it has moved this far
    ROOT_REACH = 3.0  # px: a plant this far from its block's rock has lost it
    PROBE = 4.0  # px out from the rock, which must be open water for a plant to grow there

    def __init__(self, maze, seed: int, settings=None):
        self.maze = maze
        self.settings = settings or config.FLORA
        self.rng = random.Random(seed)
        self.plants: List[Plant] = []
        self.spores: List[Spore] = []
        self._wall_generation = maze.wall_generation

    @classmethod
    def seeded(cls, maze, seed: int, settings=None) -> 'Flora':
        """A flora for a new cave: plants spread over its soil at every age, none beside the ship's start."""
        flora = cls(maze, seed, settings)
        soil = [wall for wall in maze.walls if flora._is_soil(wall)]
        lengths = list(itertools.accumulate(math.dist(wall.start, wall.end) for wall in soil))
        if not soil or lengths[-1] <= 0:
            return flora
        wanted = round(lengths[-1] / 1000 * flora.settings.startDensity)
        rng = flora.rng
        for _ in range(wanted * 10):
            if len(flora.plants) >= wanted:
                break
            wall = soil[min(len(soil) - 1, bisect.bisect(lengths, rng.uniform(0, lengths[-1])))]
            t = rng.uniform(0.1, 0.9)
            point = (wall.start[0] + (wall.end[0] - wall.start[0]) * t, wall.start[1] + (wall.end[1] - wall.start[1]) * t)
            direction = flora._open_side(wall, point)
            if (direction is None or math.dist(point, maze.start_pos) < flora.settings.startClear
                    or not flora.has_room(point)):
                continue
            plant = Plant.new(point, direction, wall.cell, rng, flora.settings)
            plant.age = rng.uniform(0, plant.death)
            flora.plants.append(plant)
        return flora

    def has_room(self, point) -> bool:
        """Whether a new plant may take root here: none living too near, and the cave not full."""
        spacing = self.settings.plantSpacing
        return (len(self.plants) < self.settings.maxPlants
                and all(math.dist(point, plant.base) >= spacing for plant in self.plants))

    def step(self, dt: float) -> None:
        """Age every plant by dt frames and burst its ripe pods; drift every spore, rooting those that reach soil. The
        dead, and any plant whose rock has gone, are gone."""
        for plant in self.plants:
            for _ in range(plant.advance(dt)):
                self._burst(plant)
        lost_rock = self.maze.wall_generation != self._wall_generation
        self._wall_generation = self.maze.wall_generation
        self.plants = [plant for plant in self.plants
                       if not plant.dead and (not lost_rock or self._on_rock(plant))]
        self.spores = [spore for spore in self.spores if self._drift(spore, dt)]

    def spores_near(self, pos, radius: float) -> List[Spore]:
        return [spore for spore in self.spores if math.dist(pos, (spore.x, spore.y)) <= radius]

    def plants_near(self, pos, radius: float) -> List[Plant]:
        return [plant for plant in self.plants if math.dist(pos, plant.base) <= radius]

    def remove(self, thing: Union[Plant, Spore]) -> None:
        """Take a plant or a spore out of the cave (eaten, say)."""
        crowd = self.plants if isinstance(thing, Plant) else self.spores
        if thing in crowd:
            crowd.remove(thing)

    def _burst(self, plant: Plant) -> None:
        """One pod bursts: its spores fly out from the stalk's tip, away from the rock."""
        settings, rng = self.settings, self.rng
        reach = self.STALK if self.maze.is_open(self._out(plant, self.STALK), settings.sporeRadius) else self.PROBE
        x, y = self._out(plant, reach)
        heading = math.atan2(plant.direction[1], plant.direction[0])
        for _ in range(rng.randint(settings.sporesMin, settings.sporesMax)):
            if len(self.spores) >= settings.maxSpores:
                return
            angle = heading + rng.uniform(-self.SCATTER, self.SCATTER)
            speed = settings.sporeSpeed * rng.uniform(0.7, 1.3)
            self.spores.append(Spore(x=x, y=y, vx=math.cos(angle) * speed, vy=math.sin(angle) * speed, age=0.0,
                                     life=settings.sporeFrames * rng.uniform(0.75, 1.0)))

    def _drift(self, spore: Spore, dt: float) -> bool:
        """Move a spore on by dt frames. Returns whether it is still drifting."""
        settings, maze = self.settings, self.maze
        spore.age += dt
        if spore.age >= spore.life:
            return False
        wander = settings.sporeWander * dt
        drag = settings.sporeDrag ** dt
        spore.vx = (spore.vx + self.rng.uniform(-wander, wander)) * drag
        spore.vy = (spore.vy + self.rng.uniform(-wander, wander)) * drag
        start = (spore.x, spore.y)
        end = (spore.x + spore.vx * dt, spore.y + spore.vy * dt)
        radius = settings.sporeRadius
        # Rock only changes by going, so a spore far from it need not look again until it has drifted that far
        spore.clear -= math.dist(start, end)
        if spore.clear <= 0.0:
            touched, when, centre = None, 2.0, None
            for wall in maze.spatial_grid.get_walls_along_path(start, end, radius):
                if wall.active:
                    hit, time, at = circle_line_collision_swept(start, end, radius, wall.start, wall.end)
                    if hit and time < when:
                        touched, when, centre = wall, time, at
            if touched is not None:
                self._land(touched, centre)
                return False
            spore.clear = self._clearance(end)
        if any(line_line_collision(start, end, a, b) for a, b in getattr(maze, 'gate_segments', ())):
            return False
        spore.x, spore.y = end
        return (maze.offset_x <= spore.x <= maze.offset_x + maze.grid_width * maze.cell_size_x
                and maze.offset_y <= spore.y <= maze.offset_y + maze.grid_height * maze.cell_size_y)

    def _land(self, wall, centre) -> None:
        """A spore at `centre` touched a wall: on soil with room, it takes root as a seed."""
        if not self._is_soil(wall):
            return
        point = get_closest_point_on_line(centre, wall.start, wall.end)
        if not self.has_room(point):
            return
        away = math.dist(point, centre)
        direction = ((centre[0] - point[0]) / away, (centre[1] - point[1]) / away) if away > 1e-6 else None
        direction = direction or self._open_side(wall, point)
        if direction is not None:
            self.plants.append(Plant.new(point, direction, wall.cell, self.rng, self.settings))

    def _clearance(self, point) -> float:
        """How far a spore at this point can drift, up to CLEAR_REACH, before it could touch rock."""
        nearest = self.CLEAR_REACH
        for wall in self.maze.spatial_grid.get_nearby_walls(point, self.CLEAR_REACH):
            if wall.active:
                nearest = min(nearest, math.dist(point, get_closest_point_on_line(point, wall.start, wall.end)))
        return nearest - self.settings.sporeRadius

    @staticmethod
    def _out(plant: Plant, reach: float) -> Point:
        return (plant.base[0] + plant.direction[0] * reach, plant.base[1] + plant.direction[1] * reach)

    def _is_soil(self, wall) -> bool:
        return (wall.active and wall.cell is not None and wall.cell in self.maze.blocks
                and wall.cell not in self.maze.strong_cells)

    def _on_rock(self, plant: Plant) -> bool:
        return plant.cell in self.maze.blocks and any(
            wall.active and wall.cell == plant.cell and circle_line_collision(plant.base, self.ROOT_REACH, wall.start, wall.end)
            for wall in self.maze.spatial_grid.get_nearby_walls(plant.base, self.ROOT_REACH))

    def _open_side(self, wall, point) -> Optional[Point]:
        """The unit vector from a point on a wall out into open water, or None if neither side is open."""
        length = math.dist(wall.start, wall.end)
        if length <= 0:
            return None
        normal = (-(wall.end[1] - wall.start[1]) / length, (wall.end[0] - wall.start[0]) / length)
        for side in (1.0, -1.0):
            direction = (normal[0] * side, normal[1] * side)
            if self.maze.is_open((point[0] + direction[0] * self.PROBE, point[1] + direction[1] * self.PROBE), 1):
                return direction
        return None
