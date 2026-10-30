# Neural Jelly — design

## Intent

Today's Jellies (`aggressive` in `config/enemies.json`, traits `chase` + `drift`)
are scripted. They steer straight at the nearest target with no sense of walls,
so they get stuck in caves (the only remedy is the `Chase` back-off at a random
angle) and they bunch up behind each other instead of working together.

Build a neural Jelly using the modular training system (`docs/modular-training.md`)
that:

1. Hunts adversaries intelligently through cave geometry: it never gets stuck and
   finds its way around walls to reach the target.
2. Cooperates with other Jellies: pincer movements and other flanking, not
   clumping or a blind rush.

## Goals

- A new modular task (`jelly_team`) registered in `learning/tasks.py`, trained
  with the same trainer, dashboard, checkpoints, replay and held-out evaluation
  as `hunter` and `wallcrawler_team`.
- A production Jelly brain that loads the trained policy and drives the Jelly in
  the real game.
- Target selection by **allegiance**: a Jelly (`enemy`) hunts the nearest living
  creature of the opposite allegiance. That includes the player's ship, allied
  hunters, and any other ally present. (Matches the existing `Encounter.target_for`
  nearest-friendly idea; the builder must confirm how hunters and allied
  creatures are represented there.)
- The policy chooses a heading and an **acceleration** (accelerate or decelerate),
  not a target speed. Speed is the integrated result, bounded by zero and the
  Jelly's maximum, so a Jelly can brake to a stop and wait (for example to hold
  position while teammates circle round). Its current speed must be an input to
  the policy. Acceleration/braking rates are left to the builder.
- Coordination through observation only: each Jelly sees its teammates' positions
  and headings. No message channel.

## Non-goals and anti-goals

- No Jelly-to-Jelly messages (no equivalent of `WallcrawlerTeam` radio/inbox).
  This was an explicit decision.
- Not a rewrite of the trainer, the Wallcrawler, or the hunter.
- Anti-goal: a Jelly that technically scores well in training but in the real game
  sticks on walls, orbits uselessly, or all pile onto one side. Evaluation must
  include the real-game-like cave arenas, not just the training arenas.
- The Jelly does not shoot; its attack is contact (existing `RamsShip` behaviour).
  Contact damage and Jelly health stay as they are today (my call).

## Constraints

- Follow the Wallcrawler precedent: an adapter (`learning/adapters/jelly.py`:
  features, heads, `SPEC`, `observe`, action-to-intention, critic input, `enabled`,
  policy driver/loader) and a scenario module (`learning/adapters/jelly_scenario.py`:
  environment, rewards, cases, curriculum, `metrics`, `selection_score`,
  `promote`, `compare`). The hook list is in `docs/modular-training.md` step 3.
- All Jellies share one policy with per-agent recurrent state, via the existing
  multi-agent `Snapshot` / `Transition` seam. Use per-agent rewards
  (`agent_rewards`) where credit assignment matters, with a team critic.
- Wall sensing: reuse the hunter's 16 wall rays (`hunter/senses.py`
  `ray_distances`) plus target bearing/distance and relative velocity, and
  teammate positions/headings (nearest few, fixed slot count, as the crawler does).
- A learned mechanism goes in production code first (new brain trait / controller),
  then the adapter exposes observation, mask and actuator. The current `Drift`
  trait has fixed speed, so the neural brain must apply acceleration to the
  Jelly's velocity itself.
- Bump the scenario version on any rule change; use the immutable per-run manifest
  and exact action replay like the existing tasks.
- Tests: extend `tests/test_creature_learning.py` and add Jelly-specific ones;
  existing Jelly tests are `tests/test_jellyfish.py`, `tests/test_jelly_creature.py`.

## Training curriculum (decided with the user)

1. **Moving target.** Jellies hunt a plain drifting target that does not shoot.
   Use or adapt the existing `learning/adapters/practice_targets.py`
   (`PracticeTarget`, firing can be disabled). Learns wall reading, routing, and
   not getting stuck.
2. **Flanking.** Several Jellies, still the plain target. Reward approach from
   differing angles; penalise bunching. Exact reward shaping is left to the builder.
3. **Hunting ship.** A training-only ship, slower and weaker than the real one,
   acts as the normal ship would and hunts the Jellies. The Jellies must hunt it
   while avoiding being hunted. Training-only: the real player ship is never used
   in training.

Stage advancement follows the existing `promote` pattern (stage plus iteration
choosing the case mix).

## Left to the builder

- Group size per case and per stage; arena selection (reuse `TRAIN_LEVELS` /
  `HOLDOUT_LEVELS` style splits).
- Reward constants and shaping, observation feature details, network sizing.
- Whether a scripted teacher + imitation bootstrap is worth it (the crawler used one).
- How the "weaker, slower ship" is built (stats, scripted behaviour reusing the
  existing hunter logic where possible).
- Held-out evaluation metrics (catch rate, time to contact, stuck time, angular
  spread of Jellies around the target) and the baseline comparison against the
  scripted Jelly.

## Clarifications from the builder check

Decided by the user: the target rule is allegiance-based, so `Encounter.target_for`
(and `nearest_friendly`) is extended to consider any living creature of the
opposite allegiance, not just ship and hunter. That is shared code; keep the
change small and covered by tests. Stage 3 (hunting ship) is part of the request,
not optional, though stages 1-2 are a sensible first shippable milestone.

## Calls I made (not discussed with the user)

- The scripted Jelly stays the default in `config/enemies.json` until the user
  chooses to switch; the neural brain is opt-in via config.
- Contact damage, Jelly HP and the Jelly's body/visuals are unchanged.
- Task key `jelly_team`.
- **Brain selection:** a new brain trait that replaces `chase`, `drift` and
  `keepsApart` on a Jelly kind that opts in (a new enemy kind in
  `config/enemies.json`, not a global flag), applied to the 1-HP `aggressive`
  Jelly only. If the weights are missing or fail to load, fall back to the
  scripted traits. Mixed neural and scripted Jellies in one level are allowed.
  How weights are packaged in the macOS bundle (the game uses the NumPy
  inference path in `learning/policy.py`, so Torch is not needed at runtime) is
  left to the builder.
- **Walls:** `bouncesOffWalls` stays only as physical collision response, and
  training uses the same collision code as the game, so there is no reliance on
  a safety net the policy won't have. Stuck time is measured separately.
- **Action limits:** heading turn rate and acceleration/braking limits are
  bounded (no instant heading change); values are the builder's.
- **Catch (stages 1-2):** contact with the plain target counts as a catch. The
  target is not destroyed; it respawns elsewhere and the episode continues until
  a timeout, so Jellies must catch repeatedly. A catch reward goes to the Jelly
  that makes contact plus a smaller shared team reward, so rushing alone is
  worse than coordinating.
- **Stage 3:** the training ship shoots as the normal ship does, at reduced fire
  rate, damage and speed. A Jelly dying is penalised; contact damaging the ship
  is rewarded. The episode ends when the ship dies, all Jellies die, or on timeout.
- **Pass bar:** a stage promotes when it beats the scripted Jelly on held-out
  arenas for catch rate and stuck time. The real-game cave arenas are a hard
  gate for `selection_score`, not just reported.
