# Living weed: plants with a life cycle

## Intent

The cave already shows little tufts of swaying weed, but they are only part of the rock drawing
(`rendering/wall_renderer.py`, `Weed`): fixed to a wall segment, chosen from the segment's shape,
gone when the wall is shot away. Nothing else in the game knows they exist.

We want the weed to be alive: distinct things in the world that grow, reproduce and die. This is
groundwork. A later change will add a creature that eats them, so the plants and especially their
spores must be real objects with positions that other code can find and remove.

## The life cycle

1. **Seed.** A small green spot on rock.
2. **Growing.** The spot grows into a tuft of blades, in the style of today's weed.
3. **Fruiting.** The grown plant puts up one or more stalks, each with a pod that swells.
4. **Bursting.** A ripe pod bursts with a small puff and releases a few spores. A plant may fruit
   more than once in its life.
5. **Drifting.** Spores float slowly through open water, wandering rather than flying straight.
   They do not pass through rock.
6. **Landing.** A spore that touches soil becomes a seed there, and the cycle repeats. A spore that
   finds no soil within its own lifespan fades away.
7. **Withering.** Every plant eventually dies of old age: it browns, shrinks and is gone.

Most spores never land, and a spore cannot take root too close to a living plant. That crowding
rule is what keeps the population steady: in a cave, spores start beside rock, so most would land
without it. A generous safety cap on plants and spores stays as a backstop against frame cost, but
balance does not depend on it. (Crowding rule and backstop are my call.)

Weed dying out in one part of a level, for example after the player blasts a stretch of rock, is
fine. Dying out across a whole level should not happen in normal play, and the long-run test checks
it does not; no reseeding mechanism. (My call.)

## Goals

- Plants and spores are distinct objects, each with a position and a stage, that the game steps
  and draws every frame.
- The level starts with plants already there, at mixed stages, so the life cycle is visible at once.
- Other code can ask for the plants and spores near a point, and remove one (the future eater's
  hook). Nothing calls this yet apart from tests.
- When flora is on, living weed replaces the decorative weed in that cave.

## Non-goals

- No eater yet.
- The player and plants ignore each other. Ships fly through plants and spores, and shots pass
  through them.
- Plants are not enemies. They are not on the roster and do not affect clearing a level, the score,
  par time or stars. The hunter does not perceive them.
- No sound.

## Anti-goals

- **Overgrowth.** A cave carpeted in weed after a few minutes means the balance is wrong.
- **Frame cost.** This must stay cheap. The game already has expensive creatures (Inchworms cost
  about 0.6 ms a frame each). The whole flora, plants and spores together, should cost well under
  1 ms a frame on a typical level.
- **Leaking into training.** Trained brains must see the world they learned in. Creature training
  scenarios build their own caves and never create flora. Hunter training and the experiment lab
  (`experiments/harness.py`, used by `tools/ppo_neural.py` and `learning/adapters/hunter.py`) run
  the real `Game.start_level` and `Game.update`, so the game needs an explicit switch to turn the
  flora off, and the harness sets it. `tools/frame_timer.py` keeps the flora on, so its timings
  show what it costs.

## Constraints and decisions

- **Its own ecosystem, not Creatures.** Creatures are enemies or friends: they count towards
  clearing a level, `Encounter.target_entity_for` targets anything of another allegiance, and each
  one is comparatively expensive. Plants and spores can number in the hundreds. So the flora is a
  separate, lightweight system owned by `Game`, stepped in the play update next to the encounter
  and drawn after the rock and before the creatures. (User agreed to this approach.)
- **Off by default, switched on by a setting.** Flora is mainly useful in long-running scenarios,
  so a `flora.enabled` setting (false by default) turns it on. When on, every cave the player sees
  gets it: normal levels, the pilot duel and the Flockers vs Wallcrawlers team battle (both run in
  `STATE_DUEL`, through `Game.start_duel`, `Game.start_team_battle` and `Game._update_duel`).
  Training switches it off regardless. (User's decision, revised from "on everywhere".)
- **The painted weed stays when flora is off.** The rock drawing keeps its decorative weed, and
  stops drawing it only for a cave that has living flora, so caves are never bare. (User's
  decision, revised from "replace the painted weed".)
- **Soil is breakable rock.** Plants grow on rock walls and never on strong metal walls, the same
  rule today's weed follows. Unbreakable rock counts as soil. (My call, user did not object.)
- **A plant goes with its wall.** When the rock a plant grows on is destroyed, the plant is gone
  at once. The maze's `wall_generation` goes up whenever a block is destroyed; the flora can check
  its plants only then.
- **Plants grow out of the rock's face**, pointing away from it, like today's weed. A seed takes
  the surface point where the spore touched and the direction away from that wall.
- **Look:** grow today's swaying weed into the full cycle: a dot, then blades, then stalks with
  swelling pods, a puff of drifting spores, then browning and shrinking. Keep the existing weed
  palette and the gentle sway. (User agreed.)
- **Its own randomness.** The flora uses its own random number generator, seeded from the level,
  so adding it doesn't shift seeded enemy spawns or caves. (My call.)
- **Time** in the game is counted in frames at `config.FPS` (`dt` is frames). Tuning goes in
  `config/settings.json` with the rest of the game's tuning.
- **Starting population** roughly matches today's weed density, spread over breakable rock and
  avoiding the player's start.
- **Tests** cover the behaviour, not internals (project preference): for example, a seed grows and
  fruits; a burst releases spores; a spore landing on rock becomes a seed; plants die of old age;
  a plant goes when its wall is destroyed; nothing grows on strong walls; the population does not
  explode over a long simulated run; the "near a point / remove" query works. Existing tests about
  decorative weed in `tests/test_wall_renderer.py`, `tests/test_cave_renderer.py` and
  `tests/test_strong_walls.py` are rewritten for living weed or removed.
- Check the look on the real display, not only with the dummy SDL driver: real fullscreen is
  1352x878, and the dummy driver hides alpha bugs.

## Later, not now

The user likes the cellular-automaton feel (like the Game of Life) and wants to keep it in mind:
the rock surface as a row of evenly spaced planting spots, and neighbours affecting each other, for
example a crowded plant withering sooner, to give boom-and-bust waves along the walls. Keep it simple
for now, but don't build anything that would make this hard to add.

## Left to the builder

- Exact timings: how long each stage lasts, how many pods and spores, spore speed and lifespan.
  Rough starting point: a plant lives one to two minutes, fruits two or three times, each pod
  releases three to five spores, spores live up to about twenty seconds.
- How spores wander and how a landing is detected (the maze's spatial grid is the obvious tool).
- Module layout, names and data structures, following the code's existing style and the glossary.
- Whether the level editor preview shows plants. Today it shows decorative weed; showing none
  there is acceptable.
