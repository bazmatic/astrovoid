# Inchworm

Play the four-worm arena with `START_LEVEL=33 ./run.sh`. Ammo is unlimited and the
exit is open. Approach a head to provoke rearing and feeding; shoot or shove a
worm to break its grip. Authored inchworms spawn against nearby walls.

## Physical body

The worm has six rigid capsule links and five independently actuated bend joints,
solved by Pymunk (already used for gates). Each link has mass and rotational
inertia. Hinges preserve its length, joint limits prevent impossible folds, and
nonadjacent links collide with each other. Every link collides with nearby walls
and gate segments. The visible anatomy and projectile hit shape use those same
capsules, including when the head rears outside the old centre hitbox.

Each muscle requests a signed rest angle, up to 1.4 radians either way. Activation
changes gradually. Damped, torque-limited angular springs apply equal and opposite
torques to the neighbouring links. There is no direct position, heading, or
velocity command. Detached muscle activity can change shape and orientation but
cannot create linear momentum. The arena has no gravity; a detached worm coasts
with light drag. Death releases the feet and leaves a limp articulated body.

Front and rear legs have separate grip requests. A foot can only attach to an
active, stationary surface within its actual reach. Its contact fixes the
position along that surface; bounded leg forces support a resting height and
align the end link with the surface. Grip constraints have finite force and
slip when overloaded. Destroyed walls release their grips. Moving gates are
collision surfaces, not anchors. Shots apply point impulses, and explosions
transfer bulk momentum.

The front legs can grasp a nearby adversary. A breakable joint transfers equal
and opposite impulses between the head and prey. Neither is frozen or teleported.
Jaw contact must persist for a full bite interval before dealing damage. Shields,
intervening walls, escape, death, releasing the front grip, and incoming hits end
the hold. Player bites use the existing collision penalty; creature bites use
hit points or the energy system, including immunity.

## Controller interface

`physics/inchworm.py` owns the mechanics. `creatures/inchworm_control.py` contains
the temporary reflex controller. The trait connects these to the encounter and
handles damage. The renderer reads plain pose data, never drives the simulation.

Set `creature.worm_command` to an `InchwormCommand` before its next encounter step:

```python
from physics.inchworm import InchwormCommand

creature.worm_command = InchwormCommand(
    muscles=(-0.8, 0.4, 0.8, 0.4, -0.8),  # rear joint through neck
    rear_grip=False,
    front_grip=True,
    bite=False,
)
```

There are five continuous motor values in [-1, 1] and three binary requests.
Finite values are clipped; wrong-length or nonfinite muscle arrays are rejected.
An all-zero command is a real override. Setting `worm_command = None` restores the
reflex controller. Both controllers use the same actuator limits and contacts.
The reflex gait waits for grip handovers, curls against the planted front,
then extends against the planted rear. It can back away from a ledge. Reaching
uses bounded inverse kinematics to choose muscle setpoints; the solver supplies
all movement and can resist an unreachable pose.

Turning has a planted-rear curl, front-foot handover, and an unfolding phase facing
the other way. Free links automatically roll belly-toward-surface at a bounded
rate. A reversed head cannot plant until its legs face the surface, and its eyes
remain on its dorsal crown. This roll is a torsional posture approximation in the
planar solver; it adds no planar impulse and is not an extra neural motor.

`creature.worm_observation` exposes the physics module's plain-data `observe()`:

- `joint_angles`: five relative angles divided by 1.4 radians.
- `joint_rates`: five relative angular velocities, in radians per frame.
- `activation`: five current muscle setpoints, including actuator lag.
- `roll_sin`, `roll_cos`: the six automatically rolled link postures.
- `velocity`: forward/lateral centre velocity, divided by link length.
- `angular_velocity`: mean link rotation rate in radians per frame.
- `grips`: rear/front actual attachment flags, including a front prey grasp.
- `grip_loads`: rear/front constraint load as a fraction of holding capacity.
- `contacts`: six link-to-environment contact flags.
- `grabbing`: whether the front grip holds prey.
- `effort`: mean absolute muscle torque as a fraction of actuator capacity.

The neural adapter combines this proprioception with local surface rays, visible
target sensing, and the preceding motor command. The versioned recurrent controller
and staged training environment live in `learning/adapters/inchworm.py` and `inchworm_scenario.py`;
the trained brain is `assets/neural/inchworm.npz`.
Without installed weights, the reflex controller remains the playtest default.

`inchworms` catalogue parameters are `strideFrames` (160 by default, excluding
handover waits) and `biteFrames` (60). Both must be positive and finite. Physics
uses game-frame units and bounded substeps, further shortened during fast impacts.
Solver objects and live prey references are excluded from death-portrait copies.

## Scope and validation

The worm's solver mirrors nearby environment surfaces and its current adversary.
Other enemies still use the game's existing collision systems. Gates also retain
the game's mover/obstacle coupling; this is not a shared articulated-world solver.
The reflex controller does not plan routes around complex cave corners. Automatic
procedural population counts are unchanged; level 33 uses authored placements.

Tests exercise free-flight momentum conservation, actuator lag, repeated physical
strides, finite grip strength, destroyed surfaces, high-speed wall impacts, time
subdivision, reciprocal grabs, rearing, feeding, segmented projectile hits,
controller override, death/copy cleanup, three screen sizes, and the real game
loop on level 33.
