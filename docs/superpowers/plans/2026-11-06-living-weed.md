# Living Weed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the decorative weed painted with the rock by living plants that grow from seeds on rock, fruit pods that burst into drifting spores, take root where spores land, and die of old age.

**Architecture:** A new `flora` package holds a lightweight ecosystem (`Flora`) of `Plant`s and `Spore`s, separate from the Creature/Encounter system. `Game` creates one for each cave it shows and hangs it on the maze (`maze.flora`); `Maze.draw` draws it after the rock, and `Game` steps it in the play update and the duel/battle update. The rock drawing (`WallRenderer`) stops making weed.

**Tech Stack:** Python 3, pygame, pytest.

**Spec:** `docs/superpowers/specs/2026-11-06-living-weed-design.md`

## Global Constraints

- Time is frames at `config.FPS`; `dt` is frames.
- Soil is breakable rock: an active `WallSegment` with a `cell` that is not in `maze.strong_cells`. Unbreakable (outer) rock is soil.
- Plants and spores are not Creatures: not on any roster, not targeted, not hit by shots, not touched by ships. No sound.
- The flora uses its own `random.Random`, never the `random` module's global state.
- Flora is on by default everywhere a cave is shown (levels, pilot duel, team battle). It is off only where switched off: `Game.grows_flora = False`, set by `experiments/harness.py`. Creature training scenarios never create flora.
- Whole flora (plants and spores) well under 1 ms a frame on a typical level.
- Tests cover behaviour, not internals. No compatibility shims for the old decorative weed.
- Names: the ecosystem is **Flora**, one living thing is a **Plant**, what drifts is a **Spore**, a seed is a Plant in its first stage. Add these to `GLOSSARY.md`.
- Leave room for the "Later" idea in the spec (planting spots, neighbour effects): crowding lives in one method, `Flora.has_room(point)`.

## Review Focus

1. **Curved rock re-forming after a neighbouring block is destroyed** moves the outline; a plant whose base is no longer on its block's rock must go, not float in water (Task 2 test `test_plant_goes_when_its_rock_reforms_away`).
2. **A big frame hitch (`dt` of several frames)** must not let a spore tunnel through thin rock; movement is swept (Task 3 test `test_spore_does_not_pass_through_rock_on_a_long_frame`).
3. **Spores leaving the maze area** (through an opening, or rounding off the screen) are removed, not kept forever (Task 3 test `test_spore_outside_the_maze_is_gone`).
4. **Starting a new level, duel or battle, or restarting** replaces the flora; nothing from the last cave carries over (Task 4 test `test_new_level_gets_fresh_flora`).
5. **A spore touching a strong wall or a gate** does not take root there (Task 3 test `test_spore_does_not_root_on_a_strong_wall`).

---

### Task 1: The plant life cycle and its tuning

**Files:**
- Create: `flora/__init__.py` (exports `Flora`, `Plant`, `Spore`)
- Create: `flora/plants.py`
- Modify: `config.py` (add `FloraSettings`, `Settings.flora` with `default_factory`, `FLORA = SETTINGS.flora`)
- Modify: `config/settings.json` (add a `"flora"` section with the same values)
- Test: `tests/test_flora.py`

**Interfaces:**
- Produces: `FloraSettings` dataclass fields, all in frames or px:
  `seedFrames=300, growFrames=1200, podFrames=600, restFrames=600, fruitingsMin=2, fruitingsMax=3, stalksMin=1, stalksMax=2, witherFrames=300, lifeJitter=0.2, sporesMin=3, sporesMax=5, sporeSpeed=0.6, sporeDrag=0.985, sporeWander=0.03, sporeFrames=1200, sporeRadius=1.5, plantSpacing=14.0, startDensity=4.0` (plants per 1000 px of soil), `startClear=120.0` (px kept clear around the ship's start), `maxPlants=400, maxSpores=300`.
- Produces: `Plant` dataclass in `flora/plants.py`: `base: Point`, `direction: Point` (unit, away from the rock), `cell: Tuple[int, int]`, `age: float`, `fruitings: int`, `stalks: int`, `phase: float` (sway), `color: Color`, plus the frame each stage ends (rolled from the settings with ±`lifeJitter`). Properties: `stage -> str` (one of `'seed'`, `'growing'`, `'fruiting'`, `'withering'`), `growth -> float` (0 to 1 through `'growing'`), `pod_ripeness -> float` (0 to 1 while a pod is swelling, 0 while resting), `withered -> float` (0 to 1 through `'withering'`), `dead -> bool`.
- Produces: `Plant.new(base, direction, cell, rng: random.Random, settings: FloraSettings, age: float = 0.0) -> Plant`
- Produces: `Plant.advance(dt: float) -> int`, which ages the plant and returns how many pods burst during this step (0 normally; pods burst when a pod's swelling completes).

Stage order and timing: `seed` for `seedFrames`, `growing` for `growFrames`, then `fruitings` rounds of (`podFrames` swelling, then burst) separated by `restFrames`, then `withering` for `witherFrames`, then `dead`. Each round bursts `stalks` pods at once.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_seed_grows_fruits_withers_and_dies():
    plant = Plant.new((0, 0), (0, -1), (1, 1), random.Random(1), config.FLORA)
    stages = []
    while not plant.dead:
        plant.advance(1.0)
        if not stages or stages[-1] != plant.stage:
            stages.append(plant.stage)
    assert stages == ['seed', 'growing', 'fruiting', 'withering']

def test_every_fruiting_bursts_each_stalk_once():
    plant = Plant.new((0, 0), (0, -1), (1, 1), random.Random(2), config.FLORA)
    bursts = 0
    while not plant.dead:
        bursts += plant.advance(1.0)
    assert bursts == plant.fruitings * plant.stalks

def test_a_long_step_still_bursts_every_pod():
    plant = Plant.new((0, 0), (0, -1), (1, 1), random.Random(3), config.FLORA)
    bursts = 0
    while not plant.dead:
        bursts += plant.advance(500.0)
    assert bursts == plant.fruitings * plant.stalks
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `venv/bin/pytest tests/test_flora.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'flora'`

- [ ] **Step 3: Add `FloraSettings` to `config.py` and `config/settings.json`, then implement `Plant` in `flora/plants.py`**

Pick `color` from today's weed palette `((70, 170, 120), (95, 190, 110), (60, 150, 140))`. Store stage boundaries as absolute ages so `advance` can count the pod bursts crossed in one long step.

- [ ] **Step 4: Run them to make sure they pass**

Run: `venv/bin/pytest tests/test_flora.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add flora config.py config/settings.json tests/test_flora.py
git commit -m "Plants have a life cycle: seed, growth, fruiting, withering"
```

---

### Task 2: Flora on a cave: starting plants on soil, and plants going with their rock

**Files:**
- Modify: `flora/plants.py` (add `Flora`)
- Test: `tests/test_flora.py`

**Interfaces:**
- Consumes: `Plant.new`, `Plant.advance`, `Plant.dead` (Task 1); `maze.walls`, `maze.spatial_grid.get_nearby_walls(pos, radius)`, `maze.strong_cells`, `maze.blocks`, `maze.is_open(pos, radius)`, `maze.start_pos`, `maze.wall_generation`.
- Produces: `Flora(maze, seed: int, settings: FloraSettings = config.FLORA)`, with `plants: List[Plant]` and `spores: List[Spore]` (empty until Task 3).
- Produces: `Flora.seeded(maze, seed: int, settings=config.FLORA) -> Flora`, a flora with starting plants: `round(soil length / 1000 * startDensity)` placed on soil, chosen by length, at a random point along the segment, on the face whose side `maze.is_open` finds open (probe 2 px out), at a random age spread over the whole life, none within `startClear` of `maze.start_pos`, and only where `has_room`.
- Produces: `Flora.has_room(point) -> bool`: no living plant within `plantSpacing`, and fewer than `maxPlants` plants.
- Produces: `Flora.step(dt: float) -> None`: advances every plant, drops dead ones, and whenever `maze.wall_generation` has changed since the last step, drops each plant whose `cell` is no longer in `maze.blocks` or that no active wall of its own cell lies within 3 px of `base`.

- [ ] **Step 1: Write the failing tests**

Use the curved cave from `tests/test_cave_renderer.py` (`Maze(1, complexity=MazeComplexity.COMPLEX, grid_size=18, seed=125, curved=True)`) and the strong-wall layout from `tests/test_strong_walls.py` (`data()` / `maze()` there; copy what you need, don't import test modules).

```python
def test_a_new_cave_starts_with_plants_at_every_stage():
    flora = Flora.seeded(cave(), seed=7)
    assert len(flora.plants) > 20
    assert {p.stage for p in flora.plants} == {'seed', 'growing', 'fruiting', 'withering'}

def test_plants_grow_out_of_rock_into_open_water():
    m = cave()
    for plant in Flora.seeded(m, seed=7).plants:
        tip = (plant.base[0] + plant.direction[0] * 4, plant.base[1] + plant.direction[1] * 4)
        assert m.is_open(tip, 1)

def test_nothing_grows_on_a_strong_wall():
    m = strong_wall_maze()
    area = pygame.Rect(m.converter.cell_rect(*STRONG)).inflate(4, 4)
    assert not any(area.collidepoint(p.base) for p in Flora.seeded(m, seed=1).plants)

def test_nothing_grows_beside_the_ship_start():
    m = cave()
    assert all(math.dist(p.base, m.start_pos) >= config.FLORA.startClear
               for p in Flora.seeded(m, seed=7).plants)

def test_plant_goes_with_its_wall():
    m = cave()
    flora = Flora.seeded(m, seed=7)
    plant = next(p for p in flora.plants if not on_perimeter(m, p.cell))  # outer rock can't be destroyed
    destroy_block(m, plant.cell)   # damage one of its faces until the block is gone
    flora.step(1.0)
    assert plant not in flora.plants

def test_plant_goes_when_its_rock_reforms_away():
    # Destroy a block next to a plant's block on curved rock; any plant left must still sit on its rock.
    m = cave()
    flora = Flora.seeded(m, seed=7)
    destroy_block(m, neighbour_of_some_plant(m, flora))
    flora.step(1.0)
    for p in flora.plants:
        assert any(w.active and w.cell == p.cell and circle_line_collision(p.base, 3, w.start, w.end)
                   for w in m.spatial_grid.get_nearby_walls(p.base, 3))

def test_the_same_seed_grows_the_same_flora():
    assert [p.base for p in Flora.seeded(cave(), seed=7).plants] == [p.base for p in Flora.seeded(cave(), seed=7).plants]
```

`destroy_block(m, cell)`: call `m.damage_wall(face)` on an active face of `cell` until `cell not in m.blocks`. `on_perimeter(m, cell)`: `m.converter.on_perimeter(m.grid, *cell)`. Write these helpers in the test file.

- [ ] **Step 2: Run them to make sure they fail**

Run: `venv/bin/pytest tests/test_flora.py -v`
Expected: the new tests FAIL with `ImportError: cannot import name 'Flora'`

- [ ] **Step 3: Implement `Flora`, `Flora.seeded`, `Flora.has_room` and `Flora.step` in `flora/plants.py`**

- [ ] **Step 4: Run them to make sure they pass**

Run: `venv/bin/pytest tests/test_flora.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add flora tests/test_flora.py
git commit -m "Flora: plants start on breakable rock and go with it"
```

---

### Task 3: Spores: bursting, drifting, taking root, and the eater's query

**Files:**
- Modify: `flora/plants.py` (add `Spore`, spore handling in `Flora.step`, queries)
- Test: `tests/test_flora.py`

**Interfaces:**
- Consumes: `Plant.advance` burst count, `Flora.has_room` (Tasks 1–2); `maze.spatial_grid.get_walls_along_path(start, end, radius)`, `maze.gate_segments`; `utils.circle_line_collision_swept` or `get_closest_point_on_line` for landing.
- Produces: `Spore` dataclass: `x, y, vx, vy: float`, `age: float`, `life: float`.
- Produces: `Flora.spores_near(pos, radius) -> List[Spore]`, `Flora.plants_near(pos, radius) -> List[Plant]`, `Flora.remove(thing: Union[Plant, Spore]) -> None`. These are the eater's hooks; nothing in the game calls them yet.
- Produces: in `Flora.step`, each burst releases `randint(sporesMin, sporesMax)` spores per pod at the pod's tip (`base + direction * blade length`), moving away from the rock at about `sporeSpeed` within ±60°, capped by `maxSpores`. Each step a spore wanders (`sporeWander` random push), slows (`sporeDrag ** dt`), and moves with a swept check from its old to new position. On touching an active wall: if that wall is soil and `has_room(contact point)`, a new seed Plant is made there with `direction` from the contact point towards the spore, and the spore is gone; otherwise (strong wall, crowded) the spore is gone. A spore crossing a gate segment is gone. A spore older than `life`, or outside the maze area, is gone.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_ripe_pod_bursts_into_spores():
    flora = Flora(cave(), seed=3)
    plant = fruiting_plant_on(flora)   # a Plant placed on soil, aged to just before its first burst
    flora.plants.append(plant)
    flora.step(2.0)
    assert config.FLORA.sporesMin * plant.stalks <= len(flora.spores) <= config.FLORA.sporesMax * plant.stalks

def test_a_spore_that_touches_rock_becomes_a_seed():
    m = cave()
    flora = Flora(m, seed=3)
    face = a_breakable_face(m)
    flora.spores.append(spore_heading_at(face))   # 6 px out in open water, moving onto the face's middle
    for _ in range(60):
        flora.step(1.0)
    assert [p.stage for p in flora.plants] == ['seed'] and not flora.spores

def test_a_spore_does_not_root_beside_a_living_plant():
    ...  # as above, with a plant already within plantSpacing of the face's middle: no new plant, spore gone

def test_spore_does_not_root_on_a_strong_wall():
    ...  # strong_wall_maze(), spore heading at a steel face: no plant, spore gone

def test_spore_does_not_pass_through_rock_on_a_long_frame():
    ...  # spore 6 px from a face moving at 20 px/frame onto it; flora.step(5.0); it ends as a seed on that face

def test_a_spore_that_finds_no_rock_fades_away():
    ...  # spore in the middle of an EMPTY maze, velocity 0; step past sporeFrames; spores == []

def test_spore_outside_the_maze_is_gone():
    ...  # spore placed beyond the maze's right edge; one step; spores == []

def test_the_eater_can_find_and_remove_a_spore():
    flora = Flora(cave(), seed=3)
    spore = Spore(x=300.0, y=300.0, vx=0.0, vy=0.0, age=0.0, life=1000.0)
    flora.spores.append(spore)
    assert flora.spores_near((305, 300), 10) == [spore]
    assert flora.spores_near((340, 300), 10) == []
    flora.remove(spore)
    assert flora.spores == []

def test_weed_neither_dies_out_nor_overgrows():
    m = cave()
    flora = Flora.seeded(m, seed=11)
    start = len(flora.plants)
    counts = []
    for frame in range(0, 5 * 60 * config.FPS, 2):
        flora.step(2.0)
        counts.append(len(flora.plants))
    assert min(counts[len(counts) // 2:]) >= start * 0.4
    assert max(counts) <= start * 2.5
```

Fill in the `...` tests in the style shown; helpers live in the test file.

- [ ] **Step 2: Run them to make sure they fail**

Run: `venv/bin/pytest tests/test_flora.py -v`
Expected: the new tests FAIL with `ImportError: cannot import name 'Spore'`

- [ ] **Step 3: Implement spores in `flora/plants.py`**

- [ ] **Step 4: Run them to make sure they pass, then tune**

Run: `venv/bin/pytest tests/test_flora.py -v`
Expected: PASS. If `test_weed_neither_dies_out_nor_overgrows` fails, tune `plantSpacing`, `sporeFrames` and `sporesMin/Max` in both `config.py` and `config/settings.json`; don't loosen the test's bounds. Also print the time of 100 `flora.step(1.0)` calls on this cave once the flora has settled: the average must be well under 1 ms. Report the number.

- [ ] **Step 5: Commit**

```bash
git add flora config.py config/settings.json tests/test_flora.py
git commit -m "Spores drift from bursting pods and take root on rock"
```

---

### Task 4: Draw it, wire it into the game, and retire the decorative weed

**Files:**
- Create: `rendering/flora_renderer.py`
- Modify: `maze/generator.py` (`Maze.flora: Optional[Flora] = None` set in `__init__`; `Maze.draw` draws it after `wall_renderer.draw` and before `wall_debris`)
- Modify: `game.py` (`grows_flora`, `_plant_flora`, calls in `start_level`, `start_duel`, `start_team_battle`; `flora.step` in `update` after `self.maze.update(dt)` and in `_update_duel`)
- Modify: `experiments/harness.py` (`game.grows_flora = False` before `game.start_level`)
- Modify: `rendering/wall_renderer.py` (remove `Weed`, `WEED_*`, `weeds`, `_weed_by_segment`, `_draw_weeds`, the weed roll in `_paint_ridge`, and the now-unused `time_seconds`/`animate` parameters of `draw`; update the module docstring)
- Modify: `tests/test_wall_renderer.py`, `tests/test_cave_renderer.py`, `tests/test_strong_walls.py`, `tests/test_outer_walls.py`, `tests/test_solid_blocks.py` (drop the weed tests and the `animate=False` arguments)
- Modify: `GLOSSARY.md` (Flora, Plant, Spore under "Things in the maze"), `ARCHITECTURE.md` (a row for `flora/`)
- Test: `tests/test_flora_game.py`

**Interfaces:**
- Consumes: `Flora.seeded`, `Flora.step`, `Plant` properties `stage`, `growth`, `pod_ripeness`, `withered`, `stalks`, `phase`, `color`, `base`, `direction`; `Spore.x/y/age/life` (Tasks 1–3).
- Produces: `draw_flora(screen: pygame.Surface, flora: Flora, time_seconds: Optional[float] = None) -> None` in `rendering/flora_renderer.py`. Time defaults to `pygame.time.get_ticks() / 1000`.
- Produces: `Game.grows_flora: bool = True` and `Game._plant_flora(seed: Optional[int]) -> None`, which sets `self.maze.flora = Flora.seeded(self.maze, seed)` when `grows_flora`, else `None`. The seed is the maze's seed when it has one, else a fresh random one from `random.SystemRandom`.

Look: a seed is a 1–2 px green dot. Growing: today's blades (keep `WEED_SWAY = 2.5` px and `WEED_SWAY_SPEED = 1.6` rad/s, blades 5–9 px), scaled by `growth`. Fruiting: `stalks` thin stalks rising past the blades, each with a pod that swells with `pod_ripeness` from 1 px to 3 px radius and pales toward yellow-green. A burst leaves nothing to draw; the spores show it. Withering: colour lerps to brown `(120, 95, 60)` and blades shorten with `withered`. Spores: 1 px pale dots `(200, 230, 170)`, fading over the last quarter of their life.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_level_has_living_weed(game):
    game.start_level()
    assert game.maze.flora is not None and game.maze.flora.plants

def test_weed_grows_while_the_level_plays(game):
    game.start_level()
    plant = game.maze.flora.plants[0]
    age = plant.age
    game.update(1.0)   # the flora grows from the start, before the player moves
    assert plant.age > age

def test_new_level_gets_fresh_flora(game):
    game.start_level()
    first = game.maze.flora
    game.start_level()
    assert game.maze.flora is not first

def test_training_switches_weed_off(game):
    game.grows_flora = False
    game.start_level()
    assert game.maze.flora is None

def test_the_duel_and_the_battle_have_weed(game):
    ...  # start_team_battle (and start_duel where the test setup allows): maze.flora has plants, and it ages in _update_duel

def test_drawing_weed_puts_green_on_the_rock_edge():
    ...  # draw_flora onto a black surface for a flora with one grown plant: some pixel near its base is greenish
```

Build `game` the way `tests/test_anemone_game.py` or the nearest existing game-level test does; reuse its fixture if there is a shared one.

- [ ] **Step 2: Run them to make sure they fail**

Run: `venv/bin/pytest tests/test_flora_game.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rendering.flora_renderer'` or `AttributeError: 'Maze' object has no attribute 'flora'`

- [ ] **Step 3: Implement `draw_flora`, `Maze.flora` and `Maze.draw`, the `Game` wiring and the harness switch**

- [ ] **Step 4: Remove the decorative weed from `WallRenderer` and its tests**

- [ ] **Step 5: Run the whole suite**

Run: `venv/bin/pytest -q`
Expected: all pass. Report any failure with its output; don't skip it.

- [ ] **Step 6: Look at it on the real display**

Run `./run.sh`, start a level, and leave it running for two minutes. Real fullscreen is 1352x878; don't rely on the dummy SDL driver. Check the following: plants are visible at every stage, spores drift visibly, and nothing grows on steel. After two minutes the walls are neither bare nor carpeted. Take a screenshot for the user.

- [ ] **Step 7: Update `GLOSSARY.md` and `ARCHITECTURE.md`, then commit**

```bash
git add flora rendering/flora_renderer.py rendering/wall_renderer.py maze/generator.py game.py experiments/harness.py GLOSSARY.md ARCHITECTURE.md \
  tests/test_flora_game.py tests/test_wall_renderer.py tests/test_cave_renderer.py tests/test_strong_walls.py tests/test_outer_walls.py tests/test_solid_blocks.py
git commit -m "Living weed grows on the cave rock in place of the painted weed"
```
