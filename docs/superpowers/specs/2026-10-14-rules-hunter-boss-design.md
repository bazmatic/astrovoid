# The Rules hunter: an enemy for the neural pilot, and the level 25 boss

Date: 2026-10-14. Status: design, awaiting review.

## Purpose

The neural pilot has only fought ordinary enemies, which cannot dodge, aim or hunt. The only thinking opponent it has
met is the Rules pilot in the FUN-menu duel, which is not a level and teaches nothing during training. This adds the
Rules pilot as an **enemy**, so that:

- training can put the neural hunter against a thinking opponent, among a few ordinary enemies; and
- the normal game gets a boss that fights the player the same way, with real aim.

Success: the neural pilot meets an opponent that dodges and shoots back; the training log shows how often it wins; and
level 25 is a boss level a player can win.

## What was decided

- **One enemy type, used by both.** The same class serves the boss level and training (approach A of three considered:
  duel code for training plus a separate boss; and a scripted imitation, both rejected as unfaithful or duplicated).
- **Hostile only to its protagonist.** The protagonist is the player's ship in a level and the neural hunter in
  training. The enemy sees only that target and its bullets, never other enemies, pickups or a friend, so it never fires
  at other enemies and ignores the parked player in training.
- **In the normal game there is no hunter on this level.** Boss levels summon none, and the player is the target.
- **The boss level is level 25**, the first endless level, which today has no file. Levels 1 to 24, the designed arc, and
  the every-sixth-level boss rotation from level 30, are unchanged.
- **Arena and escorts.** A dense rocky maze of 26 cells (`complex`, as in the duel), with 2 aggressive and 2 flocker
  escorts.

## The Rules hunter

An enemy type in the entity manager, like the flockers. It owns a hunter ship (`HunterShip`) flown by the Rules pilot
through `HunterFlight` (`hunter/flight.py`).

- **Surroundings.** A new surroundings for `HunterFlight` that answers: `enemies()` is the protagonist alone;
  `threats()` is the protagonist's shots (the projectiles that are not enemy shots); `pickups()` is empty; `friend()` is
  `None`; `maze` is the level's maze. This is what the duel already gives each hunter.
- **Protagonist.** The game names it through one method, `Game.protagonist()`. It returns the player's ship. The training
  harness replaces it so that it returns the neural hunter.
- **Weapons.** Its shots are enemy shots: they hurt the protagonist like any enemy bullet and pass through other enemies.
- **Health.** 12 hits destroy it, between a Split Boss (8) and a Mother Boss (20). Shots from the protagonist, and in
  training from the hunter, damage it. It has the usual enemy death, and no crystal drops from it.
- **Look.** The enemy colour (red), with a health bar like the other bosses.
- **Pilot thread.** In the game it gets its own Rules-pilot worker (`PilotWorker` with `RulesClient`), closed with the
  level, as the duel does. In training it uses the lab's synchronous worker (`SyncWorker`), so episodes stay
  deterministic and spawn no threads.
- **Counts as one enemy** for kills, the kill score and the star rating.

## Level 25 in the normal game

- `levels/25.json`: a `complex` maze of 26 cells, enemies `aggressive: 2`, `flocker: 2`, `rules_hunter: 1`.
- A new key `rules_hunter` in a level file's `enemies` block, read by a getter that defaults to 0, as the boss counts are.
- `is_boss_level` counts it. Everything that comes with a boss level then applies: the exit stays locked until every
  enemy is dead, ammo is infinite, and no Jev beacon appears.
- It starts as far from the player's start as the maze allows and never within 300 pixels of the player, like every
  enemy.

## Training

- **The level.** Level 25 is already in the training level set (`TUNE_LEVELS`), so the arena joins training with no new
  plumbing. In training the Rules hunter's protagonist is the hunter.
- **Share.** A new flag `--rules-share` (default 0.25): that fraction of an iteration's episodes fly level 25; the rest
  cycle through the other levels as now.
- **Reward.** The Rules hunter counts as an enemy in the kill reward. A new flag `--rules-bounty` (default 50 points)
  adds a bounty for destroying it. The death penalty applies if it kills the hunter. Both appear in the dashboard's
  rewards panel.
- **Logging.** A new field `rules_beaten`: the share of arena episodes in which the Rules hunter was destroyed, plus a
  dashboard chart for it.
- **Comparability.** Level 25's content changes, so lab scores from before and after are not comparable.

## Tests and documentation

Tests:

- the Rules hunter targets only its protagonist: it ignores other enemies and, in training, the parked player;
- its shots hurt only the protagonist;
- 12 hits destroy it and it leaves no crystal;
- `is_boss_level(25)` is true, and the exit stays locked until it dies;
- the training reward carries the bounty and the share, and `rules_beaten` is logged;
- level 25's file loads; the arc test and the endless-formula tests still pass, with any that assumed level 25 was an
  ordinary level updated.

Documentation: a row for level 25 in the README level table, the `rules_hunter` key in `levels/README.md`, and this
spec.

## Out of scope

- A hunter ally on level 25 in the normal game.
- Rules hunters on levels other than 25, or in the endless boss rotation.
- Making the Rules hunter use Jev or the neural pilot.
- A different bounty or health per level (the numbers above are constants for now).
