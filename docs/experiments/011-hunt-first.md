# 011: Hunt before following the player

Date: 2026-10-12. Switch: `hunt_first`. Not an experiment so much as a rule, requested after playing: when no enemy
is in sight the rules hunter stayed with the player instead of hunting ("it dawdles in one area").

## What was measured first

With the enemies removed (so the hunter has nothing to shoot), 90 s, share of the maze the hunter covered:

| | player hidden (explores alone) | player visible |
|---|---|---|
| levels 17 to 27 | 3 to 5% | **0.1%**, always within two cells of the player |
| levels 13 and 15 | **0.1%** (a bug, below) | 0.1% |

Two causes. (1) With a player in view the hunter follows it and never explores. (2) Exploring alone is slow:
about 15 new cells per 30 s on a 1,000-cell maze, because the left-hand wall rule retraces corridors.

## A bug found on the way (fixed, 9b30daa)

On levels 13 and 15 the hunter spawned in an inside corner and never moved. Wall-following aimed into the wall
ahead, where the safe speed is tiny; reaching it needed a burn of 0.6 of a frame, below the 2-frame noise cutoff
on burns, so the burn was "not needed" and the hunter sat still forever. At or near rest any burn now counts.
Lab score unchanged (104.1 tune, 89.1 held-out against 103.0 and 88.2).

## The rule

While any enemy remains alive anywhere, seen or not, the hunter does not use the follow-the-player behaviour: it
hunts (wall-follow exploration) instead. Once none remain, it follows the player again. The perception now
reports `enemies_present` (a boolean: the hunter is told the level is not clear, nothing more).

## Lab result

Player visible, 6 seeds on the tune set, candidate minus base: score +0.06 (-3.8 to +3.6), no term differs
(kills +0.03, idle +0.002, wall hits -0.11, enemy hits +0.05). The numbers match the hidden-player baseline
exactly. The lab cannot see the benefit: its parked player sits at the start, and the enemies come to the
hunter whatever it does, so it is never far from a fight. A player who wanders off with enemies far away is
the case the rule is for, and the lab has no such scenario.

## Decision

Adopted for the rules pilot (`RULES.hunt_first` is true); the lab shows it does no harm. Jev and the student are
unchanged, because Jev's written instructions describe the old follow behaviour.

## Still weak

Hunting without sight of an enemy is only wall-following, which is slow (4 to 5% of the maze in 90 s). The next
improvement is exploration that remembers where it has been and heads for unvisited ground. A scenario with a
moving player would be needed to measure the follow behaviour properly.
