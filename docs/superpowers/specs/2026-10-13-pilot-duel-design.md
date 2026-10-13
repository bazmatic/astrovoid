# Pilot Duel and the "Fun" menu

Status: design, awaiting review.

## Goal

A new main-menu item, **FUN**, holds experimental levels. It starts with one: **Pilot fight: Rules vs Vibes**, an
empty maze in which the rules pilot and the neural pilot, each flying a hunter, treat each other as the enemy and fight
until one is destroyed. The player watches; they do not fly.

"Vibes" is the neural pilot. The name appears only in the menu.

## What the player sees

1. Main menu: START GAME, LEVELS, **FUN**, SELECT PROFILE, CONTROLS, QUIT.
2. FUN opens a list of experimental levels (one entry for now: "Pilot fight: Rules vs Vibes"). Up and down move,
   confirm starts, cancel goes back to the main menu. Keyboard and controller, like the level select.
3. The duel: an empty maze, two hunters starting far apart, the rules hunter and the neural hunter in distinguishable
   colours with a small name tag. The player's ship is hidden and takes no part. A health pip row for each hunter.
4. The level ends when one hunter is destroyed. A banner names the winner ("Rules wins", "Vibes wins"), then the game
   returns to the FUN list. If neither is destroyed within 120 seconds, or both are destroyed in the same frame, the banner says
   "Draw". Cancel at any time leaves the duel for the FUN list.
5. A duel changes nothing in the player's profile: no stars, no score, no level progress.

## Behaviour

- **Combatants.** Two `HunterShip`s. The rules hunter is built with `hunter_settings_for('rules')` and flown by the
  rules pilot through `PilotWorker`/`HunterController`. The neural hunter is built with `hunter_settings_for('neural')`
  and flown by `NeuralController` on `assets/neural/hunter.npz`. Each keeps its own pilot setup; `game.hunterPilot` is
  not used.
- **Enemies of each other.** Each pilot is shown the other hunter in its list of enemies, so its existing perception,
  senses and fire control chase and shoot it. Neither is shown the player or any maze enemy (there are none).
- **Damage.** In the duel only, hunters are destructible with `duel.health` hits each (default 5), and a projectile
  fired by one hunter damages the other (and never the one that fired it). Projectile damage and the damage-immunity
  window follow the existing hunter rules. Outside the duel nothing changes: hunters stay indestructible and their
  shots stay friendly.
- **Start positions.** The two farthest-apart safe cells of the maze, the rules hunter on one and the neural hunter on
  the other, facing each other.
- **Missing neural weights.** If the weights file is missing or invalid, the duel does not start. The screen shows
  "Vibes unavailable" with no winner and returns to the FUN list; it does not crash.
- **Isolation.** The duel lives in its own module and state. The single-hunter game loop, the Jev beacon and the normal
  levels are not touched, so nothing that works today can change.

## Components

- `STATE_FUN` and a `FunMenu` (list screen) with a state handler, wired into `StateHandlerRegistry` and the main menu.
  Menu entries are data (title and an action), so more experimental levels can be added later by adding a line.
- `STATE_DUEL`, a `DuelArena` (the two hunters, their controllers, the damage and end rules, the timeout) and its
  drawing, with a state handler for cancel.
- Settings: `duel.health` (5) and `duel.timeoutSeconds` (120).
- Tests: arena rules (damage, no self damage, end conditions, draw), menu navigation, that the profile is untouched, that normal
  hunters remain indestructible, and one full headless duel that ends.

## Out of scope

- The player joining the fight, other enemies in the maze, rounds or best-of series, and tournament tables.
- Choosing other pilots (the arena takes two pilot kinds, but the menu offers only this pairing).
- Any change to training.

## Review focus

1. A destroyed hunter must really stop (no ghost shots, no further damage) and the level must end exactly once.
2. A hunter's own shots must never damage itself, even at point-blank range.
3. Leaving the duel by cancel, or finishing it, must leave the normal game in a clean state (no stray hunter, projectiles or
   controller), so START GAME afterwards behaves as before.
4. Missing or corrupt neural weights must not crash the duel.
5. The profile (stars, score, progress) must be unchanged after any duel.
