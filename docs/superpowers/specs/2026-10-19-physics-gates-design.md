# Physics obstacles: gates

Date: 2026-10-19. Status: design, agreed in conversation; awaiting review of this document.

## Purpose

The user wants physics-based obstacles in the levels, because they would be fun to play with. The moment they
pictured: the player is racing into an area with enemies on their tail, shoves a gate open, and the enemies beside
it get pushed away. Gates are the first members of a family of physics obstacles; later ones (the user agreed to a
family; heavy blocks, hinged doors, see-saws and a crusher are examples, not commitments) should be able to reuse
what this work builds.

Success: a level designer places gates in the level editor; in play, the ship and enemies push free gates around
and are swept aside by motor gates; gates are stopped by walls and each other; everything that sees walls sees
gates; nothing ever passes through a wall.

## Goals

- **A physics footing for obstacles**, using the **pymunk** 2D physics library (agreed). The maze walls go into the
  pymunk space as static segments; each obstacle is a pymunk body, held by a joint where needed. Future obstacle
  kinds should be a new shape and joint on the same footing, not a new physics system.
- **Free gate**: a plank on a pin through its middle.
  - Light (the user's word): it spins easily, and pushing it barely slows the ship. A light gate nudges enemies
    aside rather than flinging them far (the user accepted this).
  - When nobody touches it, it follows normal physics: once pushed it keeps turning, running down slowly. My call:
    at the same gentle rate the ship coasts to a stop (the ship's friction, 0.998 per frame).
  - Pushing a gate is free: no damage, no power cost, unlike hitting a maze wall (the user's rule).
- **Motor gate**: the same plank, turned steadily by a motor.
  - Strong enough to push ships and enemies aside (the user's rule).
  - If something is pinned between the plank and a maze wall, the gate stalls, pushing, until it slips free; it
    never crushes it or pushes it through the wall (agreed). The same holds against other obstacles.
  - A motor gate placed so a wall blocks its swing simply stays still; when the player shoots that wall block away
    it starts turning (the user's idea). So when a destructible wall block is destroyed, the physics space must lose
    that block's edges, and gain any newly exposed faces.
  - One motor speed for all motor gates, in `config/settings.json` (my call); each gate's direction (clockwise or
    anticlockwise) is set in the editor.
- **Both ways**: the ship and enemies move gates, and gates push the ship and enemies back. A swinging gate can
  bounce the ship and shove enemies.
- **Gates stop against maze walls and against each other.**
- **Anchored enemies** (anemones, flighthouses, which are pinned in place today) count as immovable, like walls: a
  gate stops against them, and a motor gate stalls on one (my call; it matches how they already treat the ship).
- Gate contact is not an enemy hit, so it never costs the "No hits" star, and player shots must never treat a gate
  as a destructible wall block (`maze.damage_wall`).
- **Bullets** (player's, the hunter's and enemies') stop at a gate and give it a small push: a bullet has a little
  momentum (the user's rule), so a stream of shots can nudge a free gate round, while a single shot barely moves it.
  How much is a setting. They do not damage gates. Whether a bullet nudges a motor gate is left to the builder; it
  should never noticeably slow one.
- **Everything that sees walls sees gates**: enemies that check walls, the Jev hunter's senses and route, and line of
  sight for enemies that use it (anemones, flighthouses) treat a gate's plank as being in the way, as it is now.
- **Level editor**: a gate is placed on a cell like an enemy. A key sets its starting angle; for a motor gate, a key
  sets its direction (my guess, accepted).
  - Placed gates are saved in the level's `layout` and come back exactly.

## The gate's size

The plank is two cells long in total, pinned at its middle (the user's choice): each tip reaches the centre of the
neighbouring cell, so the gate sweeps a circle of one cell's radius around its pin, which is the centre of the cell
it is placed in. It turns freely in an ordinary three-cell passage. Cells aren't square (`cell_size_x` and
`cell_size_y` differ); the builder picks how "one cell" is measured for the radius. Longer gates may come later. Its thickness is left to the builder; it should read
clearly as a plank and be thick enough that the ship can't slip through it.

## Non-goals (for now)

- Other members of the family (blocks, hinged doors, see-saws, crushers).
- The Neural hunter learning to use obstacles. It should at least see them as things in the way, the same as walls;
  learning tricks with them can come later (the user's note).
- Gates in generated (non-layout) levels. Gates come from hand-made layouts only (my call).
- Gates taking damage or being destroyed.

## Anti-goals

- A ship or enemy pushed through a maze wall or through a gate by the physics. This is the failure most likely to
  come from mixing pymunk with the game's own collision code.
- A physics step that makes the game stutter at 60 fps on a level with a handful of gates.
- Gates that jitter, creep or vibrate while at rest.

## How the game works today (from a code survey)

- Movement is per frame at 60 fps (`dt` ≈ 1.0, velocities in px per frame). The ship (`RotatingThrusterShip`) and
  most enemy ships use a swept circle-vs-wall-segment test with a reflect-and-restitution response; simpler enemies
  (`Enemy`) use a non-swept test. Walls are infinitely heavy. Circle-vs-circle contacts use r² masses
  (`utils/math_utils.apply_circle_collision_physics`). There is no rotation physics anywhere today.
- Maze walls are `WallSegment` line segments built from the grid's blocks (`Maze.rebuild_walls`), indexed in
  `maze.spatial_grid`. A `WallSegment` hashes by its endpoints, so a segment that moves must be removed from and
  re-added to the grid rather than mutated in place.
- Destructible blocks: `Maze.damage_wall` removes a block at 0 HP, deactivates its faces, adds the neighbours'
  newly exposed faces, and increments `maze.wall_generation`.
- The Jev hunter's route search caches by `(number of active walls, maze.wall_generation)`; a moving gate would not
  invalidate it on its own.
- Level layouts (`level_layout.Layout`, `parse_layout`, `to_json`) and the editor (`editor/model.py`,
  `rendering/level_editor.py`) hold one item per cell, with no orientation or extra settings yet.
- `game.update` order: maze, exit, input, ship update and wall collision, hunter and enemies (each with wall and
  ship contacts), projectiles, powerups, exit check.
- pymunk 7.3.1 is available for the game's Python 3.10. It is a new dependency (`requirements.txt`) and must also
  work in the PyInstaller builds.

## Left to the builder

- How the game's own movement and pymunk meet: for example, whether the ship and enemies are mirrored into the
  pymunk space as bodies whose velocities are synced each frame, or whether gate contacts are resolved by the game
  and handed to pymunk as impulses. Whatever is chosen must keep the anti-goals.
- How gates appear to wall-reading code (moving `WallSegment`s re-indexed each frame, or a separate query that wall
  readers also consult), and how the hunter's route cache treats gates.
- Gate mass, plank thickness, motor speed and motor force values (in settings), and the look of the plank and pin.
- Editor keys and labels, and the layout JSON shape for a gate (its cell, kind, angle and direction).
- Which existing tests change, and the new tests. Rendering is checked on the real display (1352×878).
