# Star rating from what the player did

Date: 2026-10-18. Status: design, approved in conversation; awaiting review of this document.

## Purpose

Today a level's stars come from its score: 20, 40, 60, 80 and 95 points out of 100. The score mixes time, collisions,
shots, fuel, kills and pickups, so a player can't tell what to do better. The user wants the maximum stars to mean
something plain: **every enemy killed, every powerup collected, within a "reasonably possible" time.** Each star
should say what it was for, so a player who missed one knows why.

Success: a player can look at the level-complete screen and say which star they missed and what it would have
taken; five stars means all enemies dead, all crystals collected and a finish inside par.

## The rule (agreed with the user)

Five stars, each earned on its own:

| Star | Earned when |
|---|---|
| Finish | The player reaches the exit. Finishing always gives at least one star. |
| Half the enemies | At least half the level's enemies were killed. |
| Every enemy | Every enemy was killed. |
| Every crystal | Every powerup crystal was collected. |
| Par time | The level was finished within its par time. |

They are independent: for example all crystals and a finish inside par with half the enemies killed is four stars.

- **Kills and pickups by the Jev hunter count** as if the player had made them (the user's rule).
- **Enemies counted** are everything that was alive at any point in the level, including enemies that appear during
  it: babies hatched from eggs, the children a split or mother boss leaves, eggs a mother lays, Vibelets and so on.
  The share killed is kills ÷ (kills + enemies still alive when the player leaves).
  - An egg that hatches is neither killed nor alive afterwards: it doesn't count either way, and its babies do.
  - "Every enemy" means none left alive at the exit. A level that never had an enemy earns both enemy stars.
- **Crystals counted** are every powerup crystal that appeared during the level. Crystals are never placed at the
  start of a level today; they only drop from killed enemies, by chance. Crystals don't expire. The Jev beacon is not
  a powerup crystal and doesn't count.
  - "Every crystal" means none left uncollected at the exit. A level where none dropped earns the star (my call).
- **Par time**, worked out when the level starts:

  > par = route time + 6 s per enemy + 30 s per spawning boss + 3 s per crystal

  - Route time: the shortest path through the maze grid from the start cell to the exit cell (moving between
    neighbouring open cells, four directions), its length in pixels, flown at half the ship's top speed. Top speed is
    `SHIP_MAX_SPEED` (8 px per frame, 480 px/s), so half is 240 px/s.
  - The enemies counted are those on the level when it starts. Enemies that appear later (eggs, babies, a boss's
    children) do not extend par: a Mother lays an egg every 3 s, so letting them extend it would hand the par star to
    anyone who waits (agreed with the user).
  - Instead each boss that spawns enemies, the Mother and the Squiddler Boss (`mother_boss`, `split_boss`), adds a
    flat 30 s in place of its 6 s, for killing it and what it spawns (agreed). Killing her quickly makes par easy;
    letting her fill the maze doesn't. The Boss Viber spawns nothing and counts as an ordinary enemy.
  - Crystals add their 3 s when they drop (my call): they only drop from kills, so they can't run away the way eggs
    can, and a crystal the player must fetch needs the time.
  - On a level whose exit opens on a timer (`timer` exit policy), par is never shorter than the timer plus 10 s, so
    the par star stays possible (my call).
  - The numbers (the speed share, 6 s, 30 s, 3 s, 10 s) go in `config/settings.json` so the user can tune them after
    playing.
  - Example: 14 enemies, 3 crystals and a 2,400 px route gives 10 + 84 + 9 = 103 s.
- **The clock for par** is play time, `Game.play_seconds`: it starts on the player's first move and stops while the
  game is paused or frozen, the same clock a timer exit uses (my call). The HUD's TIME gauge counts wall-clock time
  from when the level loads, so the two can differ by a few seconds; the level-complete screen shows play time next
  to par so the comparison is fair.

## While playing

Today the stars during play are sound only: a `StarIndicator` follows the live score and plays a chime when the star
count changes, but nothing is drawn. The user agreed to this:

- A row of five small stars is drawn during play, showing what the player would get if they reached the exit now:
  - the finish star is always lit;
  - the two enemy stars light at half the enemies killed and at none left, and go out again if new enemies appear;
  - the crystal star is lit while no crystal is left uncollected, and goes out when one drops;
  - the par star is lit from the start, pulses for the last 10 seconds before par, then goes out.
- The existing star-gained and star-lost chimes play when a star lights or goes out.
- Where the row sits is left to the builder. The side panel is full below the gauges (see the EXIT block and the
  hunter gauge); the space around the level number at the top, or a slim row in the panel, are candidates. It must be
  checked on the real fullscreen display (1352×878).

## The level-complete screen

- The five stars keep fixed places, in the order of the table above and the same as the row during play, so a missed
  star shows as a gap (my call). Earned stars land with today's animation and chimes.
- The record glow: when this run's star count beats the level's previous best count, every lit star glows (my call).
  Profiles still save only the count, so which stars were earned before isn't known.
- Under each star, one short line saying what it was for and how close the player came: `FINISHED`,
  `9/14 ENEMIES`, `14/14 ENEMIES`, `2/3 CRYSTALS`, `1:42 / PAR 1:43`. Exact wording, layout and colours are left to
  the builder; the lines must fit the screen and be checked on the real display.

## What stays the same

- The score is still calculated, shown and kept as the level's best score. POWER still drains, and running out still
  fails the level (no stars, as today). `NO_POWER_DRAIN` and observer mode change only the power drain; stars are
  worked out the same way.
- Stars already saved in profiles stay as they are; the best count still only goes up.
- The stars a level gives are still a number from 0 to 5 saved through `profiles.record_level_result`.

## What it replaces

- `StarIndicator.SCORE_THRESHOLDS` and `calculate_star_count(score_percentage)` as the source of stars, and the score
  percentage passed to `AnimatedStarRating`. The tests that pin the score thresholds
  (`tests/test_star_thresholds.py`, parts of `tests/test_reward_stars.py`) are rewritten for the new rule.
- Kills by the Jev hunter are not counted anywhere today (only player kills reach the score); the new tally counts
  both. The score itself is unchanged: hunter kills still don't add to it.

## Tests

- The star rule on its own, from plain numbers (kills, alive, crystals collected and left, play time, par): each star
  on and off, and the edge cases (no enemies, no crystals, exactly half, exactly on par).
- Par: the route length on a hand-made layout; spawning bosses at 30 s; later enemies not extending par; crystals
  adding 3 s as they drop; a timer exit's floor.
- In a game: player and hunter kills both counted; babies and boss children counted; a crystal collected by the
  hunter counted; the beacon not counted.
- The live row: which stars are lit as the level changes, and the chime on each change.
- The level-complete screen's lines, checked on the real display.

## Left to the builder

Module and class names; where the tally lives; how the route is computed (a new BFS over `maze.grid`, or reusing the
hunter perception's); the live row's position and look; the level-complete lines' layout and wording; the settings
key names.
