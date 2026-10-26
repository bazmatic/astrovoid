# Curved cave walls

Date: 2026-10-25. Status: approved design, updated 2026-10-26 for the user’s broader, smoother curves and acceptance of seeded passage narrowing.

## Purpose

The user wants the maze walls to look like smooth cave rock instead of rectangular blocks: curvy and
naturalistic. They picked the look from mockups: smooth, water-worn rock with gentle irregular bulges and dips,
curved "as much as possible", landing **between the C2 and C3 mockups** (see "The look" below for what those were).

The shape must be honest: the ship, enemies and projectiles bounce off the curve the player sees, "as much as is
practical, even if just an approximation" (the user's words). Collision must not secretly follow the old square
grid.

Success: every level, generated or hand-made, loads as curved cave rock; flying into a bulge bounces the ship off
that bulge's surface; seeded bulges may make traversal harder; report any truly unfinishable level rather than restoring a corridor-width clamp.

## Goals

- **Curved rock everywhere** except steel strong walls. Generated levels and hand-built `layout` levels both get
  curves, worked out from the wall cells when the maze is built. Level files and the level editor keep storing
  cells; nothing about authoring changes.
- **What you see is what you hit.** Collision, bouncing, projectile contact, line of sight, grenade proximity
  sensing, rooted-enemy sight lines and the hunter's distance rays all use the curved shape.
- **Deterministic per level.** The bulges come from the level's seed, so a level looks and plays the same every
  time; different levels look different. (My call; the user agreed with the playback.) Training that varies the
  seed between episodes gets varied rock for free.
- **Grenade holes look natural.** When a block is destroyed, the rock around the gap re-forms smoothly, so a fresh
  hole looks like a natural cave opening, not a square bite (the user's "perfect"). It need not look rougher than
  the surrounding rock. The existing wound marks (chips, cracks, bites) before a block breaks stay, drawn on the
  curved surface.
- **Steel strong walls stay square** and keep their metal-plate look, so they read as man-made (the user's rule).

## Anti-goals

- Gates keep their whole swing: rock stays out of each gate's swing circle.
- Wall cores and their links stay solid, so thin walls remain barriers rather than floating islands.
- Open-cell centres and small links stay open. These preserve the field's topology, not a creature-sized
  passage guarantee. Bulges may narrow passages and make traversal harder; the user withdrew the earlier
  anti-goal because the game fixes the seed. No corridor-clearance clamp or corridor-face pinning remains.
- Ship start, exit, beacon and placed creatures keep their discs clear as far as square walls allow.
- Steel stays square; generation is deterministic and rebuilds match fresh construction.
- Collision must not visibly disagree with the drawing: no bouncing off empty-looking space, no flying into rock.
- No noticeable frame-rate drop on the real fullscreen display (1352x878), including when grenades destroy blocks.

## Non-goals

- Keeping already-trained neural hunters flying well. The user accepted that they will need retraining on the new
  walls. Their 16 distance rays will read different values.
- Changing how levels are stored or edited, or adding curve controls to the editor.
- Changing gameplay rules for walls: hit points, which walls are destructible, blast damage, rail behaviour all
  stay as they are.

## The look

Latest direction (2026-10-26): curves should sweep on a larger scale, without small irregularities.
Current tuning uses `blurCells: 0.42`, `noiseAmplitude: 0.7`, one noise scale of `2.5` cells and weight `1.0`.
The fine noise octave is removed. Curved ridge widths meet at a common endpoint width and use gentler
wander so rendering does not add a chain of small lumps. The earlier mockups below are historical references;
the user still judges the final look from real-display screenshots.


The mockups (in `.superpowers/brainstorm/`, not committed) drew one sample wall grid by blurring the cell
occupancy and thresholding at 0.5, with value noise added for irregularity. 26 px cells, two noise octaves at
scales of 22 px and 9 px:

| Mockup | Blur | Noise amplitude |
|---|---|---|
| C2 | box blur radius 8, 3 passes | 0.42 |
| C3 | box blur radius 10, 3 passes | 0.55 |

The target sits between these. The mockup method is only a reference for the amount of curve and bulge, not a
required technique.

**The curve scales with the cell size** (the user's rule). Real cells range from about 35x26 px (grid 32) through
62x47 px (grid 18) to 112x84 px (level 1, grid 10). Every level should look like the chosen mockup relative to
its own layout, so big-celled levels get big sweeping curves. Express the tuning as fractions of a cell, not
pixels. (In the mockup, cells were 26 px: C2 blur 8 px is about 0.31 cell, C3 10 px about 0.38 cell; noise scales
22 px and 9 px are about 0.85 and 0.35 cell.) The tuning values live in `config/settings.json` under `maze` so they
can be adjusted after seeing it in the real game. (My call.)

Real cells are not square (`MazePositionCalculator` sizes x and y separately). Curves should still look like rock
rather than stretched blobs. The builder decides how.

Rendering keeps today's rock character (ridge highlights, barnacles, animated weed, block-fill darker rock,
cracks), reshaped to follow the curve.

Where curved rock meets a square steel wall, the rock meets the steel edge cleanly. (My call.) The outer
perimeter's inner face is curved rock like any other indestructible rock wall. (My call.)

## Constraints from the current code

- **Work happens on the `feature/curved-cave-walls` branch**, not on `main` (the user's rule).

These come from reading the code (not running it). Line numbers are approximate.

- **Walls are already straight segments.** `GridToWallsConverter` (`maze/converter.py`) turns each exposed cell face
  into a `WallSegment` (`maze/wall_segment.py`), tagged with its `cell`. Every collision, sight and ray consumer
  reads those segments through `utils/spatial_grid.py`. So the cheapest honest route is expressing the curve as
  many short `WallSegment`s, each tagged with the cell it belongs to. Consumers then mostly work unchanged. This is
  the suggested approach; the builder may choose differently if it meets the goals.
- **Damage is per block.** `Maze.damage_wall` (`maze/generator.py`) damages `wall.cell`, and destroying a block
  clears the grid cell, deactivates its faces and adds faces for neighbours (assumes four faces per cell). With
  curves, destroying a block must rebuild the curved outline in the neighbourhood, and every new segment must
  know which cell it damages. `wall_generation` must still go up so pymunk walls, weapon surfaces and hunter routes
  refresh.
- **Renderer caching.** `rendering/wall_renderer.py` paints walls once onto a cached surface and repaints only
  changed patches. Its tests (`tests/test_wall_renderer.py`, "honest shape") pin that the drawn ridge stays close to
  the true line; that intent carries over to the curve.
- **Axis-aligned assumption.** `hunter/visibility.py` `local_segments` merges collinear horizontal and vertical
  edges as a speed-up, with a speed test in `tests/test_hunter_visibility.py`. Curved segments fall off that fast
  path; visibility must stay fast enough.
- **Physics gates.** `physics/obstacle_world.py` mirrors walls as pymunk segments (follows automatically).
  `plank_fits` tests planks against cells as rects; see the gate swing rule in the anti-goals.
- **Grid users stay on the grid.** Par-time BFS (`scoring/par.py`), hunter routes (`hunter/maze_route.py`), spawn
  checks (`Maze.is_open`) and the editor all use cells. Spawns and the exit must not land inside a bulge.
  `is_open` already checks segment overlap.
- About 18 test files build `WallSegment`s directly; those keep working if the segment type is unchanged.

## Left to the builder

- How to compute the curved outline from the cells (blurred field and contour, smoothed polylines, or otherwise)
  and how many segments per curve, trading smoothness against collision and sight cost.
- How to guarantee the remaining anti-goals (gate swings, spawn discs, no broken thin walls), and how to test them,
  e.g. across many generated seeds and all `levels/*.json`.
- How to localise the rebuild after a block is destroyed so it stays cheap and the surrounding rock does not
  visibly jump.
- Whether to keep a way to fall back to square walls (for comparisons or old replays). Not asked for.
