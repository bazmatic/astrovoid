"""Living weed: plants grow from seeds on the rock, fruit pods that burst into drifting spores, and die of old age."""
import random

import config
from flora import Plant


def new_plant(seed):
    return Plant.new((0.0, 0.0), (0.0, -1.0), (1, 1), random.Random(seed), config.FLORA)


def test_a_seed_grows_fruits_withers_and_dies():
    plant = new_plant(1)
    stages = []
    while not plant.dead:
        plant.advance(1.0)
        if not plant.dead and (not stages or stages[-1] != plant.stage):
            stages.append(plant.stage)
    assert stages == ['seed', 'growing', 'fruiting', 'withering']


def test_every_fruiting_bursts_each_stalk_once():
    plant = new_plant(2)
    bursts = 0
    while not plant.dead:
        bursts += plant.advance(1.0)
    assert bursts == plant.fruitings * plant.stalks


def test_a_long_step_still_bursts_every_pod():
    plant = new_plant(3)
    bursts = 0
    while not plant.dead:
        bursts += plant.advance(500.0)
    assert bursts == plant.fruitings * plant.stalks
