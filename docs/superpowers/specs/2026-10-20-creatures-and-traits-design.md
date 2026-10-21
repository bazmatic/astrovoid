# Creatures and Traits: Design

Every enemy, and in the end the allied hunter, is one generic **Creature** assembled from `config/enemies.json`: a
**Body** (how it looks) and a list of **Traits** (what it does). Behaviour is shared by naming a trait in another
kind's entry; a neural-pilot jellyfish is a catalogue entry, not a class.

Decided with the user on 2026-10-20 (architecture review, candidate 2). Builds on candidate 1 (`enemy_kinds.py`, the
Enemy Kind catalogue, commit `361b3c8`) and candidate 3 (`game_handlers/enemy_roster.py`, the Roster, commit
`420b0e2`).

## Why

Today each kind is a class (`Enemy` with strategies, `ReplayEnemyShip` and its subclasses `Baby`, `SplitBoss`,
`MotherBoss`, `FlockerEnemyShip`, `FlighthouseEnemy`, `Egg`, `Anemone`, `EnemyHunter` and its subclasses) and the game
wires each one by hand: nine `update_X` methods in `EnemyUpdater`, nine hit loops in
`CollisionHandler.handle_projectile_enemy_collisions`, and `Game._fly_enemy_hunters`. Behaviour is fixed to classes:
the neural pilot only flies a `HunterShip`, only the Mother lays eggs, only the Squiddler Boss's split is reused (by
copying it for the Mother). The user wants to make new enemies and allies by reusing existing behaviour, configured
rather than coded.

## The model

**Creature**: one class. It holds what every creature has: kind (`type`), position, velocity, radius, angle, speed,
hit points, allegiance, its controls this frame, its Body and its Traits, and the per-creature state its traits keep.
It is a `GameEntity`, so the roster, death animations, gates and death portraits treat it like any enemy today.

**Body**: how a creature looks. `update(creature, dt, target)` animates (the target is where the creature's target
is, or None), `draw(screen, creature)`, `update_death(creature,
dt)`, `draw_death(screen, creature)`, `DEATH_DURATION`, `DEATH_FRICTION`, and `on_event(creature, name)`. The Urchin,
PatrolCrab and Jellyfish classes already have this shape; the squid, flocker, flighthouse, egg, anemone and hunter-ship
drawing moves out of their classes into Bodies. A Body never decides behaviour.

**Trait**: one piece of behaviour, stateless, configured by its own parameters from the catalogue. Hooks, each a
no-op by default:

| Hook | When |
|---|---|
| `on_spawn(creature, encounter)` | once, when the creature joins the encounter (set up its state) |
| `on_frame(creature, encounter, dt)` | every frame while it lives |
| `on_shot(creature, shot, encounter)` | a friendly shot struck it |
| `on_death(creature, encounter)` | it died |
| `on_event(creature, name, encounter)` | another trait emitted an event on it |
| `on_crowd(creatures, encounter, dt)` | once a frame for all live creatures of a kind that has this trait |

Per-creature state lives on the creature, never in the trait. A trait may declare `REQUIRES` (other trait names it
needs); the catalogue is rejected at startup when an entry breaks that.

**Brains and propulsion** are traits joined by `Controls` (`turn`, `thrust`, `fire`, `heading`, `aim`). A brain
decides the controls (neural pilot, rules pilot, replays the player, chase, patrol, flock, still); propulsion turns
them into motion (Thrusters: turn and thrust like a ship; Drift: steer the velocity toward a heading; Coasts: no drive,
momentum and friction only). A pilot requires Thrusters and Gun; the loader rejects a pilot on a creature without them.

**Events** let traits and Bodies react without knowing each other: `fired`, `hit`, `hit_wall`, `rammed`, `alert`.
The crab raises its claw on `fired`; the squid blinks on `hit` and `hit_wall`.

**Allegiance** (`friend` or `enemy`) is a per-kind field: it decides whom a creature targets and whose shots hurt it.

**Encounter**: what happens to the creatures on a level in one frame. `step(dt)` runs every live creature's traits in
roster order, then each kind's crowd traits; `shoot(projectile) -> bool` offers a friendly shot to each live creature
in roster order and stops at the first hit. It also gives traits what they act on: the target for a creature (the
nearest friend, the same rule as `combat_targets.nearest_friendly`), the maze, the ship, the scoring, the shots list,
the crystals, the command recorder, and `kill`, `drop_pickup` and `spawn`. `Game` and `DuelEnemies` each hold one.
`EnemyUpdater`, the collision handler's enemy-hit loops and `handle_enemy_to_enemy_avoidance` (dead code) go.

## The catalogue

Each migrated entry in `config/enemies.json` gains:

```json
"patrol": {
  "...": "the existing fields",
  "allegiance": "enemy",
  "body": "crab",
  "traits": {
    "patrol": {},
    "drift": {"speed": "patrol_speed"},
    "gun": {},
    "bouncesOffWalls": {},
    "ramsShip": {},
    "takesHits": {"hitPoints": 1},
    "dropsPickup": {}
  }
}
```

Trait order in the file is the order hooks run. A trait's numbers live in its own entry; `tuning` keeps only the
Body's look (sizes, colours, glow). Constants in `config.py` are removed as their last reader goes.

## Decisions

- Traits take over movement and AI too, not only the game's wiring: sharing behaviour (the neural pilot on any
  creature) is the point.
- Behaviour may drift numerically; play must stay the same, checked by the tests and by watching the 40-level run. It
  is a game: bit-identical play is not required.
- Squiddler Boss children stay Squidlets.
- Speed matters: a frame on the busiest levels may be at most about 20% slower than today. It is measured before any
  kind moves, so the design can change before much is built.
- Tests that check real behaviour are rewritten against the Encounter or a single trait; tests that only exercise old
  seams (class constructors, `update_X`, `handle_projectile_enemy_collisions`) are deleted, and the deletions listed
  for the user. This is part of the user's planned test cull.
- New glossary terms: Creature, Body, Trait, Brain, Propulsion, Encounter.

## Stages

Each stage is committed separately; after each, the whole suite passes and the seeded 40-level run plays normally.
Each stage after the first gets its own plan when it starts.

1. **Speed check**: frame timer, baseline, the Creature/Trait/Encounter skeleton, and a dispatch benchmark. A gate:
   more than ~20% slower stops the work for a rethink with the user.
2. **Urchin, Crab, Jelly** (`static`, `patrol`, `aggressive`). Deletes `Enemy` and `enemy_strategies.py`. Second
   speed gate on the real levels.
3. **The squids**: Squiddler, Squidlet, Squiddler Boss, Mother (ReplaysPlayer brain, Thrusters, FlinchesWhenHit,
   SplitsOnDeath, LaysEggs).
4. **Egg** (Hatches, grows), **Anemone** (PullsShip crowd trait, FlinchesWhenHit, Anchored), **Flocker** (Flocks crowd
   trait with the neighbour cache), **Flighthouse** (LaunchesFlock).
5. **The enemy hunters**: Terminator, Viber, Boss Viber, Vibelet, with Thrusters, Gun, Energy and a pilot trait that
   wraps `HunterFlight`. Deletes `EnemyHunter` and its subclasses and `VIBERS`.
6. **The allied hunter**: an entry with `allegiance: friend`, the hunter-ship Body and the Jev pilot; `HunterFlight`,
   the duel and the experiments move onto Creatures.
