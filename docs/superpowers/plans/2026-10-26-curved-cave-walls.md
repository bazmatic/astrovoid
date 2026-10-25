# Curved Cave Walls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace square wall faces with smooth, irregular cave-rock outlines that collision, sight and drawing all share, while every level stays finishable.

**Architecture:** A sampled scalar field over the maze is built from the cell grid: blurred occupancy plus seeded value noise. Clamps enforce the anti-goals: corridor clearance, link tubes, wall cores, gate swings, square steel. The rock outline is the field's 0.5 contour, traced per maze cell (tile) with marching squares, simplified, and emitted as ordinary `WallSegment`s tagged with the wall cell that owns them. Every existing segment consumer keeps working. Destroying a block recomputes the field and re-traces only the tiles whose samples changed.

**Tech Stack:** Python, pygame, numpy, opencv-python (`cv2`, already in `requirements.txt`: Gaussian blur, connected components, distance transform), pytest.

**Spec:** `docs/superpowers/specs/2026-10-25-curved-cave-walls-design.md`

## Global Constraints

- Work on branch `feature/curved-cave-walls`.
- Levels and the editor keep storing cells. No change to `levels/*.json` format or `Layout`.
- Steel strong walls stay exactly today's square faces and plates.
- The curve scales with the cell. Tuning is in cell fractions, except clearances, which are pixel radii of creatures.
- Default tuning, between mockups C2 and C3:
  - `blurCells 0.34`
  - `noiseAmplitude 0.48`
  - `noiseScalesCells [0.85, 0.35]`
  - `noiseWeights [1.0, 0.5]`
- Noise term, as in the mockup: `amp * Σ w_i * (vnoise_i - 0.5)`.
- Field threshold `THRESHOLD = 0.5`. Clamps push values to `0.5 ± MARGIN`, with `MARGIN = 0.05`.
- The cave must never consume the global `random` stream; enemy placement depends on it. Noise comes from `numpy.random.default_rng(seed)`.
- Gameplay rules unchanged: hit points per block, destructibility (perimeter and strong are indestructible), blasts, rail.
- Run tests with `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy venv/bin/python -m pytest tests/<file> -q`.
- Do not start or restart any neural-hunter training run. Retraining is the user's call, later.

## Review Focus

1. **Old recorded training episodes and replays** must replay on square walls, because they were recorded there; only new runs use curves. Task 7 pins this.
2. **Big-celled levels** (level 1, grid 10, cells over 100 px) produce huge bulges. A spawn, the start or the exit must never sit inside rock. `is_open` has to reject points deep inside a bulge, not just points that touch a segment. Task 5 pins this.
3. **A grenade blast destroying several blocks in one frame** must not hitch visibly. Task 4 pins the per-rebuild budget, and Task 5 drives a multi-block blast.
4. **Hunters routing through the cell graph** (`hunter/maze_route.MazeRoutes.linked`) must keep every link between adjacent open cells. Task 2's link tube pins this.
5. **The level editor preview** builds a `Maze` from a layout with no seed. It must show the same rock as play, which uses the level's seed. Task 5 pins this.

---

## File Structure

- Create `maze/cave_field.py`: `SampleGrid`, plus `CaveField`, which builds and clamps the field (pure numpy and cv2, no pygame).
- Create `maze/cave_contour.py`: `tile_polylines`, marching squares and simplification for one tile.
- Create `maze/cave.py`: `CaveShape`. It turns grid plus field into `WallSegment`s, handles rebuild after a destroy, `is_rock`, and block territories for drawing.
- Modify `config.py` and `config/settings.json`: `CaveSettings` under `maze.cave`.
- Modify `maze/generator.py` (`Maze`): add the `seed`/`curved` params, curved `rebuild_walls`, `damage_wall`, `is_open` and `draw`.
- Modify `game.py`, `experiments/harness.py` and `tools/ppo_neural.py`: pass the seed, plus the `curved_walls` run flag.
- Modify `rendering/wall_renderer.py`: territory-masked fills and bites, per-wall flags, joints only at sharp turns, weed spacing by length.
- Modify `hunter/visibility.py` only if Task 6's speed test fails.
- Tests:
  - New: `tests/test_cave_field.py`, `tests/test_cave_contour.py`, `tests/test_cave_shape.py`, `tests/test_cave_maze.py`, `tests/test_cave_renderer.py`.
  - Edit: pin square-geometry tests to `curved=False`.

---

### Task 1: Cave settings

**Files:**
- Modify: `config.py:85` (`MazeSettings`), `config.py:488-495` (parsing), and constants near `config.py:634`
- Modify: `config/settings.json` (`maze` section)
- Test: `tests/test_cave_field.py`

**Interfaces:**
- Produces:
  - `config.CaveSettings`, a dataclass with these fields and defaults:
    - `enabled: bool = True`
    - `maxSampleSpacing: float = 6.0`
    - `minSamplesPerCell: int = 6`
    - `blurCells: float = 0.34`
    - `noiseAmplitude: float = 0.48`
    - `noiseScalesCells: Tuple[float, ...] = (0.85, 0.35)`
    - `noiseWeights: Tuple[float, ...] = (1.0, 0.5)`
    - `clearanceRadius: float = 16.0`
    - `linkClearance: float = 2.0`
    - `wallCoreCells: float = 0.15`
    - `simplifyTolerance: float = 0.75`
  - `MazeSettings.cave: CaveSettings`
  - `config.CAVE = SETTINGS.maze.cave`

`clearanceRadius` 16 is the largest radius of a creature that travels corridors (replay/Squiddler 15) plus 1. Bosses (30, 45) do not fit one-cell corridors today and are excluded.

- [ ] **Step 1: Write the failing test** `test_cave_settings_load_from_settings_json`: `config.CAVE.enabled is True`, `config.CAVE.blurCells == 0.34`, `config.CAVE.noiseScalesCells == (0.85, 0.35)` (a tuple, not a list), `config.CAVE.clearanceRadius == 16.0`.
- [ ] **Step 2: Run it.** Expected: FAIL with `AttributeError: ... CAVE`.
- [ ] **Step 3: Implement.**
  - Add the dataclass and a `cave` field with `default_factory`.
  - Parse with `CaveSettings(**{k: tuple(v) if isinstance(v, list) else v for k, v in raw["maze"].get("cave", {}).items()})`.
  - Add a `"cave"` object to `settings.json` holding every default above.
- [ ] **Step 4: Run it.** Expected: PASS.
- [ ] **Step 5: Commit** with `feat: cave wall settings`.

---

### Task 2: The cave field

**Files:**
- Create: `maze/cave_field.py`
- Test: `tests/test_cave_field.py`

**Interfaces:**
- Consumes: `config.CaveSettings`, and `MazePositionCalculator` (`cell_size_x`, `cell_size_y`, `offset_x`, `offset_y`).
- Produces:
  - `Cell = Tuple[int, int]`, meaning (col, row), matching `Maze.blocks` keys.
  - `THRESHOLD = 0.5` and `MARGIN = 0.05`.
  - `@dataclass(frozen=True) class SampleGrid`. Fields: `cols: int`, `rows: int`, `cell_w: float`, `cell_h: float`, `origin: Tuple[float, float]`, `per_x: int`, `per_y: int`. Members:
    - property `shape -> (rows*per_y + 1, cols*per_x + 1)`
    - `h_x`, `h_y`: the sample spacing in pixels
    - `point(iy: int, ix: int) -> Tuple[float, float]`
    - `fractional(x, y) -> Tuple[float, float]`: (fy, fx) sample coordinates
    - `cell_of_sample(iy, ix) -> Cell`: clamped, so samples on the far border belong to the last cell
    - `@classmethod for_maze(cls, calc, cols, rows, settings)`, where `per_x = max(minSamplesPerCell, ceil(cell_w / maxSampleSpacing))`, and the same for y
  - `class CaveField`:
    - Constructor: `__init__(self, grid: List[List[int]], samples: SampleGrid, *, strong: FrozenSet[Cell], keep_clear: Sequence[Tuple[Tuple[float, float], float]], seed: int, settings: CaveSettings)`. `grid` is held by reference and indexed as `grid[row][col]`, where 1 means wall.
    - Attributes:
      - `values: np.ndarray`, float32 of `samples.shape`
      - `rock: np.ndarray`, bool, `values >= THRESHOLD`
      - `owner: np.ndarray`, int32: `row*cols + col` of the owning non-steel wall cell, or -1
    - `rebuild(self) -> np.ndarray`: recomputes after the caller has mutated `grid`. Returns a bool `(rows, cols)` array of tiles where any sample's `rock` changed.
    - `value_at(self, x: float, y: float) -> float` (bilinear)
    - `is_rock(self, x: float, y: float) -> bool`
    - `required_clearance(self) -> float`, which is `min(settings.clearanceRadius, 0.5*min(cell_w, cell_h) - 1.0)`

**Build order** (`rebuild` runs all of it; a later step wins over an earlier one):
1. **Occupancy.** 1 for samples inside wall cells or outside the grid, else 0. A sample exactly on a cell border takes the max of the cells it touches.
2. **Blur.** Separable Gaussian, `σ_px = blurCells * sqrt(cell_w*cell_h)`. That is `σ_px/h_x` samples in x and `σ_px/h_y` in y, which keeps it isotropic in pixels. Kernel radius `ceil(3σ)`. Pad the array with 1s, i.e. outside the grid counts as rock.
3. **Noise.** Value noise in pixel space. Octave `i` has lattice spacing `noiseScalesCells[i] * sqrt(cell_w*cell_h)`, lattice values from `np.random.default_rng(seed*1009 + i)`, and smoothstep interpolation. Add `noiseAmplitude * Σ w_i (n_i - 0.5)`. Compute it once in `__init__` and cache it; it never changes.
4. **Wall core.** Wall-cell samples within `wallCoreCells*sqrt(cell_w*cell_h)` px of the wall skeleton get `max(v, THRESHOLD+MARGIN)`. The skeleton is each wall cell's centre, plus lines between centres of orthogonally adjacent wall cells. Perimeter cells also link to virtual cells outside the grid.
5. **Gate swings.** Open-cell samples inside any `keep_clear` circle get `min(v, THRESHOLD-MARGIN)`.
6. **Link tubes.** Open-cell samples within `linkClearance` px of the line between centres of orthogonally adjacent open cells, or within that distance of any open cell's centre, get `min(v, THRESHOLD-MARGIN)`.
7. **Steel.** Samples inside strong cells are set to 1.0. Samples in open cells within `0.5*min(cell_w,cell_h)` of a strong cell's rect get `min(v, THRESHOLD-MARGIN)`, so the steel face stays exposed and straight.
8. **Island and hole cleanup** (`cv2.connectedComponents`, 4-connectivity):
   - A rock component with no wall-core sample becomes open (`THRESHOLD-MARGIN`).
   - An open component containing no open-cell centre becomes rock (`THRESHOLD+MARGIN`).
9. **Corridor clearance.** Compute free space as `cv2.distanceTransform(~rock) >= required_clearance()/min(h_x,h_y)`. For each pair of orthogonally adjacent open cells (a, b), take the free mask cropped to the union of their two rects. If their two centres are not in the same free component inside that crop, clamp a tube for that pair: open-cell samples of a and b within `required_clearance()` px of the a–b centre line get `min(v, THRESHOLD-MARGIN)`. Because `required_clearance` is capped at half the cell, a corridor narrower than the clearance stays straight-walled (the user-approved rule).
10. **Repeat step 8 once** (a tube can cut a bulge loose). Then set `rock` and `owner`. The owner is the containing wall cell when that cell is non-steel; otherwise the nearest non-steel wall cell by rect distance among the 3x3 neighbours; otherwise -1.

`rebuild` may recompute everything. Task 4 sets a time budget, and windowing is allowed if needed, as long as results equal a fresh build.

- [ ] **Step 1: Write the failing tests** in `tests/test_cave_field.py`. Use `MazePositionCalculator` for real cell sizes, and grids from `RecursiveBacktrackingGenerator` seeded explicitly (COMPLEX, grid 26, seed 125) plus hand-built grids:
  - `test_deterministic_for_seed`: two fields with the same seed give `np.array_equal(values)`. A different seed differs.
  - `test_does_not_touch_global_random`: `random.getstate()` is unchanged across construction.
  - `test_curve_scales_with_cell`: the same 5x5 grid at grid sizes 10 and 30. The fraction of samples that differ from raw occupancy is within 25% between the two.
  - `test_wall_cores_stay_rock`: every wall-cell centre `is_rock`. For a one-cell-thick wall line, every sample on the skeleton line is rock.
  - `test_cell_centres_and_links_stay_open`: every open-cell centre and every point at 10 evenly spaced positions along every adjacent-open-cell link is not rock.
  - `test_corridor_clearance`: for every adjacent open pair, a disc of radius `required_clearance()` can travel from one centre to the other (the step-9 check rerun independently in the test).
  - `test_no_rock_islands`: every rock component contains a wall-cell centre.
  - `test_gate_swing_kept_clear`: with `keep_clear=[((cx, cy), r)]`, no open-cell sample inside that circle is rock.
  - `test_steel_cells_stay_square`: all samples inside a strong cell are rock. Samples in an adjacent open cell within half a cell of the steel face are open.
  - `test_rebuild_matches_fresh_build`: set `grid[r][c] = 0` for an interior wall cell and call `rebuild()`. `values` equals a fresh `CaveField` on the mutated grid within `1e-5`. The returned tile mask is True at (r, c).
- [ ] **Step 2: Run them.** Expected: FAIL with `ModuleNotFoundError: maze.cave_field`.
- [ ] **Step 3: Implement** `maze/cave_field.py` per the build order.
- [ ] **Step 4: Run them.** Expected: PASS.
- [ ] **Step 5: Commit** with `feat: cave rock field with clearance, core and steel clamps`.

---

### Task 3: Tracing a tile's outline

**Files:**
- Create: `maze/cave_contour.py`
- Test: `tests/test_cave_contour.py`

**Interfaces:**
- Consumes: `SampleGrid`, `THRESHOLD`.
- Produces: `tile_polylines(values: np.ndarray, samples: SampleGrid, tile: Cell, tolerance: float) -> List[List[Tuple[float, float]]]`.
  - The tile covers squares `iy in [row*per_y, (row+1)*per_y)` and `ix in [col*per_x, (col+1)*per_x)`.
  - Output is pixel coordinates.
  - Each polyline is oriented with **rock on the right**, i.e. clockwise around rock, matching `GridToWallsConverter.face`.
  - Polylines end on the tile border or are closed.
  - Crossing points come from linear interpolation on the sample edge. Neighbouring tiles therefore share identical end points.
  - Saddles are decided by the square's centre average.
  - Ramer–Douglas–Peucker with `tolerance`, keeping polyline end points fixed.

- [ ] **Step 1: Write the failing tests:**
  - `test_circle_traced_closely`: field `1 - dist/R` of a circle with R = 40 px over a 3x3 tile grid. Every polyline vertex is within 0.5 px of radius R. The union of polylines is closed.
  - `test_rock_on_the_right`: for each polyline edge, the point 2 px to the right of its midpoint has `values` above `THRESHOLD` by bilinear lookup.
  - `test_tiles_join_exactly`: every end point of a tile's open polyline equals, to within 1e-6, an end point in a neighbouring tile's polylines.
  - `test_simplify_reduces_vertices`: for the circle, using tolerance 0.75 gives fewer than half the vertices of tolerance 0, and every simplified vertex is a raw vertex.
- [ ] **Step 2: Run them.** Expected: FAIL (module missing).
- [ ] **Step 3: Implement** `tile_polylines`. Vectorise case lookup with numpy. Chain the segments with a dict keyed on the rounded end point (round to 6 decimal places).
- [ ] **Step 4: Run them.** Expected: PASS.
- [ ] **Step 5: Commit** with `feat: marching-squares outline per maze tile`.

---

### Task 4: CaveShape, from field to wall segments

**Files:**
- Create: `maze/cave.py`
- Test: `tests/test_cave_shape.py`

**Interfaces:**
- Consumes: `CaveField`, `SampleGrid`, `tile_polylines`, and `GridToWallsConverter` (its `face`, `on_perimeter`, `cell_rect`), plus `WallSegment`.
- Produces `class CaveShape`:
  - Constructor: `__init__(self, grid, calc: MazePositionCalculator, converter: GridToWallsConverter, *, strong: FrozenSet[Cell], keep_clear, seed: int, settings: CaveSettings, hit_points: Callable[[Cell], int])`.
  - `segments(self) -> List[WallSegment]`: the current outline.
    - Rock segments come from each tile's polylines. Each segment's `cell` is the owner (`field.owner`) sampled at its midpoint pushed `min(h_x, h_y)` to the right, i.e. into rock.
    - Drop rock segments whose midpoint lies within `max(h_x, h_y)` of a strong cell's rect, then add `converter.face(...)` for each exposed side of each strong cell, exactly as today.
    - `destructible = not (cell in strong or converter.on_perimeter(grid, *cell))`, and `hit_points = hit_points(cell)`.
    - A segment with no owner (-1) is assigned to the nearest wall cell to its midpoint.
  - `open_cell(self, cell: Cell) -> Tuple[List[WallSegment], List[WallSegment]]`. Call it after the caller has set `grid[row][col] = 0`. It runs `field.rebuild()`, re-traces the changed tiles plus their 8 neighbours, and returns `(removed, added)`.
    - `removed` holds the current segment objects that no longer exist.
    - `added` holds the new ones.
    - Segments whose key `(round(start, 3), round(end, 3), cell)` is unchanged keep the same object and appear in neither list.
  - `is_rock(self, pos) -> bool`, and `version: int`, which increments on each `open_cell`.
  - `territory(self, cell: Cell) -> Optional[Tuple[pygame.Rect, pygame.mask.Mask]]`: the pixels that are rock (bilinear field ≥ THRESHOLD) and owned by `cell`, cropped to their bounding rect. Cache it by `version`.

- [ ] **Step 1: Write the failing tests.** Use a COMPLEX grid-26 maze, seed 125, built through `MazePositionCalculator`:
  - `test_segments_follow_field`: every segment end point has `|value_at - THRESHOLD| < 0.08`, except steel faces.
  - `test_watertight`: for every wall-cell centre `q` and each orthogonally adjacent open-cell centre `p`, the segment p→q crosses at least one segment (`utils.math_utils.line_line_collision`).
  - `test_every_segment_owned_by_a_wall_cell`: `grid[row][col] == 1` for every segment's `cell`.
  - `test_steel_faces_identical`: for a grid with a strong cell, the segments whose `cell` is that strong cell equal `converter.face` output for its exposed sides.
  - `test_open_cell_matches_fresh_build`: destroy an interior block. Then `set(keys of segments())` equals the keys of a fresh `CaveShape` on the mutated grid, and the objects outside the 3x3 tiles around the changes are identical (`is`).
  - `test_open_cell_fast`: on grid 32 with real `config` screen sizes, the median over 10 `open_cell` calls is `< 10 ms`.
  - `test_segment_count_reasonable`: on grid 26, `len(segments())` is under 6x the square converter's count.
- [ ] **Step 2: Run them.** Expected: FAIL (module missing).
- [ ] **Step 3: Implement** `maze/cave.py`. If `test_open_cell_fast` fails, window `CaveField.rebuild` (cached noise, blur and clamps around the changed cell ± `ceil(3σ / cell)+1`, global cv2 cleanup), keeping `test_rebuild_matches_fresh_build` green.
- [ ] **Step 4: Run them.** Expected: PASS.
- [ ] **Step 5: Commit** with `feat: CaveShape emits curved wall segments and rebuilds after a destroy`.

---

### Task 5: Curved walls in the Maze

**Files:**
- Modify: `maze/generator.py`: `Maze.__init__` (:146), `rebuild_walls` (:233), `_refresh_block_fills` (:253), `damage_wall` (:272), `is_open` (:401), `draw` (:431)
- Modify: `game.py:316` and `game.py:669`: pass `seed=seed`
- Modify: `tests/test_solid_blocks.py`, `tests/test_outer_walls.py`, `tests/test_strong_walls.py`, and any other test that pins square face coordinates or counts: build with `curved=False`
- Test: `tests/test_cave_maze.py`

**Interfaces:**
- Consumes: `CaveShape`, and `physics.obstacle_world.plank_size(maze)` (import it inside the function to avoid a cycle).
- Produces:
  - `Maze.__init__(self, level, complexity=None, grid_size=0, layout=None, seed: Optional[int] = None, curved: Optional[bool] = None)`
  - Attributes:
    - `self.curved` (`config.CAVE.enabled` when None)
    - `self.cave_seed` (`level` when `seed` is None)
    - `self.layout`
    - `self.cave: Optional[CaveShape]`
    - `self.block_territories: Dict[BlockRect, Tuple[pygame.Rect, pygame.mask.Mask]]`
  - Gate keep-clear circles: for each `layout.gates` placement, centre `position_calculator.grid_center_to_screen(*g.cell)` and radius `half + thickness/2 + 2`, where `half, thickness = plank_size(self)`.
  - `damage_wall`, destroyed branch, when `self.cave` is set:
    - delete the block;
    - set `grid = 0`;
    - `removed, added = self.cave.open_cell(cell)`;
    - deactivate and `spatial_grid.update_wall` each removed segment, then filter `walls`;
    - give each added segment `hit_points = blocks[w.cell]` and pass it to `spatial_grid.add_wall`;
    - then `wall_generation += 1`.
    The square branch stays as it is.
  - `is_open` also returns False when `self.cave and self.cave.is_rock(pos)`.
  - `draw` passes `territories=self.block_territories` and `strong_cells=self.strong_cells` to the renderer (consumed in Task 6).

- [ ] **Step 1: Write the failing tests** in `tests/test_cave_maze.py`:
  - `test_maze_is_curved_by_default`: `Maze(1, EMPTY, 10)` has `cave` set, and some wall is neither horizontal nor vertical.
  - `test_square_mode_unchanged`: `Maze(1, EMPTY, 10, curved=False).walls` equals the square converter's output.
  - `test_block_shares_hit_points_across_segments`: one hit makes every segment with that `cell` drop to `WALL_HIT_POINTS - 1`.
  - `test_destroy_takes_wall_hit_points_hits`: after exactly `WALL_HIT_POINTS` hits the block is gone, `wall_generation` has gone up by 1, `walls` has no segment with that `cell`, and the spatial grid finds the new segments with `get_walls_along_path`.
  - `test_rim_never_destroyed`: as `test_outer_walls` does today, on a curved maze.
  - `test_spawns_never_inside_rock`: for every level in `levels/*.json` plus level 1 generated, every `get_valid_spawn_positions()` point has `not cave.is_rock`, and `start_pos` and the exit centre are not rock. Review Focus 2.
  - `test_ship_bounces_off_the_curve`: aim a circle of radius `SHIP_SIZE` at a non-axis-aligned segment and run `physics.thrust.sweep_walls`. The reflected velocity matches `v - 2(v·n)n`, where n is that segment's normal, within 1e-6.
  - `test_all_levels_meet_anti_goals`: across all `levels/*.json` and 20 seeds of each complexity preset at grid 18 and 32, the Task 2 and 4 checks (clearance, links, watertight, islands, gates) pass on the built maze.
  - `test_multi_block_blast_budget`: a blast destroying 4 adjacent blocks in one `CollisionHandler.handle_blast` call finishes in `< 40 ms` on grid 32. Review Focus 3.
  - `test_editor_preview_matches_play`: the editor preview's `Maze`, built as `rendering/level_editor.py:335` does, has the same segment keys as `Maze(level, ..., layout=..., seed=get_level_seed(level))`. Pass the seed in the editor too if needed. Review Focus 5.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement** the Maze changes and the `game.py` seed passing. Then pin the square-geometry tests with `curved=False`. Rule: a test that asserts exact square face coordinates or counts gets `curved=False`; any other failure is a bug to fix in the cave code.
- [ ] **Step 4: Run the full suite** `pytest tests -q`. Expected: all pass.
- [ ] **Step 5: Commit** with `feat: mazes use curved cave walls`.

---

### Task 6: Drawing curved rock, and fast enough visibility

**Files:**
- Modify: `rendering/wall_renderer.py`: `draw` (:155), `_paint_blocks` (:326), `_bites` (:415), `_paint_segments`, `_paint_joint`, `_paint_ridge` (:587), weed registration
- Modify (only if the speed test fails): `hunter/visibility.py:77-114` `local_segments`
- Test: `tests/test_cave_renderer.py`, `tests/test_hunter_visibility.py`

**Interfaces:**
- Consumes: `Maze.block_territories`, `Maze.strong_cells`, and `WallSegment.destructible` and `.cell`.
- Produces: `WallRenderer.draw(..., territories: Optional[Mapping[BlockRect, Tuple[pygame.Rect, pygame.mask.Mask]]] = None, strong_cells: FrozenSet[Cell] = frozenset())`.
  - When `territories` is given:
    - a block's fill, mottling, stains, cracks and bites are painted into its territory mask instead of its rect;
    - each wound goes to the nearest segment of that block and bites inward along that segment's normal (`Bite` takes float vectors);
    - damage shading is skipped for segments with `destructible == False`;
    - segments with `cell in strong_cells` are drawn as steel, not ridges;
    - `_paint_joint` runs only at free ends and at vertices where adjacent segments turn by more than 35°;
    - weeds are placed with the same density per pixel of ridge as square mode, not per segment.
  - Without `territories`, behaviour is unchanged.

- [ ] **Step 1: Write the failing tests** in `tests/test_cave_renderer.py`, painting a curved `Maze(..., seed=125)` onto a test surface:
  - `test_rock_pixels_filled`: every pixel where `cave.is_rock` holds, sampled every 3 px, is opaque. Every open pixel more than `MAX_REACH+2` from any segment is transparent.
  - `test_bites_stay_in_territory`: after wounds on one block, no pixel outside that block's territory mask (inflated by `MAX_REACH`) changes.
  - `test_destroyed_block_cleared`: after destroying a block, its former territory, minus the new rock, is transparent beyond `MAX_REACH+3` from the new segments.
  - `test_steel_still_plates`: a strong cell is steel-coloured and has no weed within its rect, as in `test_strong_walls`.
  - `test_weed_density_matches_square`: the weed count per 1000 px of ridge is within 0.5–2x of `curved=False` on the same grid.
  - `test_joints_only_at_sharp_turns`: the joint count is at most the number of vertices with a turn above 35°, plus the free ends.
- Add to `tests/test_hunter_visibility.py`: `test_visibility_on_curved_maze_stays_fast`. Over the same 20 open-cell origins and radius 400, the best of 3 timings of `visible_wall_portions` on the curved maze is under 4x the timing on that maze with `curved=False`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement** the renderer changes. If the visibility test fails, extend `local_segments` to merge consecutive near-collinear segments (angle < 3°, shared end point) in addition to axis-aligned runs, keeping the `tests/visibility_reference.py` comparisons green.
- [ ] **Step 4: Run** `pytest tests -q`. Expected: all pass.
- [ ] **Step 5: Look at it on the real display.** Use the `run` skill to launch the game fullscreen at the real 1352x878, not the dummy driver (it hides alpha bugs). Screenshot level 1, a grid-32 level, a level with steel walls (`grep -l strong_walls levels/*.json`), and a level with gates. Check the result against the C2–C3 look, steel square, and nothing transparent that should be rock. Report the screenshots to the user.
- [ ] **Step 6: Commit** with `feat: draw curved cave rock`.

---

### Task 7: Old training runs stay on square walls

**Files:**
- Modify: `game.py` (attribute beside `combat_ruleset`, :94), `experiments/harness.py:225-256`, `tools/ppo_neural.py:293` and `:460`
- Test: `tests/test_cave_maze.py`

**Interfaces:**
- Produces:
  - `Game.curved_walls: bool`. It defaults to `config.CAVE.enabled` and is read by both `Maze(...)` calls in `game.py` as `curved=self.curved_walls`.
  - `harness` takes a new parameter `curved_walls=False`, which sets `game.curved_walls`. This mirrors `combat_ruleset="legacy"`.
  - `ppo_neural` records `'curved_walls': True` for new runs and `prior.get('curved_walls', False)` for resumed runs, and passes it to the harness. The same goes for whatever replays an episode from a run record. Follow every reader of `combat_ruleset` and add `curved_walls` beside it.

- [ ] **Step 1: Write the failing tests:**
  - `test_harness_defaults_to_square_walls`: a harness game built with no `curved_walls` has `maze.cave is None`.
  - `test_new_run_records_curved_walls`: the run-record dict `ppo_neural` writes for a new run has `curved_walls is True`, and one resumed from a record lacking the key is False.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest tests -q`. Expected: all pass.
- [ ] **Step 5: Commit** with `feat: training runs record whether walls are curved; old runs stay square`.
