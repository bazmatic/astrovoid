"""Living weed: plants on the cave rock, and the spores they scatter.

A plant starts as a seed on the rock, grows into a tuft of blades, then fruits: it puts up stalks whose pods swell and
burst, several times over. Then it withers and is gone. Its stages are fixed when it is made, as the ages at which
each one ends, so a long step crosses them as surely as many short ones.
"""
import math
import random
from dataclasses import dataclass
from typing import Tuple

Point = Tuple[float, float]
Color = Tuple[int, int, int]

COLORS = ((70, 170, 120), (95, 190, 110), (60, 150, 140))


@dataclass
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
