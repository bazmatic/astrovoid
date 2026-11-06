"""Living weed: plants on the cave rock, and the spores they scatter.

A Flora is every plant and spore in one cave. Plants grow on soil: the faces of breakable rock (outer rock counts;
strong metal walls do not). A plant goes when its rock does.

A plant starts as a seed on the rock, grows into a tuft of blades, then fruits: it puts up stalks whose pods swell and
burst, several times over. Then it withers and is gone. Its stages are fixed when it is made, as the ages at which
each one ends, so a long step crosses them as surely as many short ones.
"""
import bisect
import itertools
import math
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

import config
from utils import circle_line_collision

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


class Flora:
    """Every plant and spore in one cave, stepped and drawn with it."""
    ROOT_REACH = 3.0  # px: a plant this far from its block's rock has lost it
    PROBE = 4.0  # px out from the rock, which must be open water for a plant to grow there

    def __init__(self, maze, seed: int, settings=None):
        self.maze = maze
        self.settings = settings or config.FLORA
        self.rng = random.Random(seed)
        self.plants: List[Plant] = []
        self.spores: List = []
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
        """Age every plant by dt frames; the dead, and any whose rock has gone, are gone."""
        for plant in self.plants:
            plant.advance(dt)
        lost_rock = self.maze.wall_generation != self._wall_generation
        self._wall_generation = self.maze.wall_generation
        self.plants = [plant for plant in self.plants
                       if not plant.dead and (not lost_rock or self._on_rock(plant))]

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
