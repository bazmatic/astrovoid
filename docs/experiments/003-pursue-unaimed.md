# 003: Pursue visible enemies that cannot yet be shot

Date: 2026-10-11. Switch: `pursue_unaimed`. Compared on the tune set, 6 seeds per level, against 001.

## Hypothesis and prediction

The hunter ignores a visible enemy while it has no firing solution, which wastes time. Heading for the
nearest such enemy (a course to its position) would cut idle time and raise the kill rate.

## Result

Identical to the baseline on every term: +0.000 for kill rate, wall hits, enemy hits, idle time and
score, with an interval of +0.000 to +0.000. The two arms played the same episodes move for move.

## Interpretation

The switch never fired. At this scale the sensor range is about 449 m and a shot reaches about 960 px,
so every enemy the hunter can see already has a firing solution. There are no "visible but not
shootable" enemies to pursue. The idle time in the baseline comes from having no enemy in sight, not
from enemies it can see but cannot hit. (The exact zero is also a check that the lab is deterministic.)

## Decision

Rejected; the switch stays off. It is left in `RuleParams` because it costs nothing, but it should not
be revisited unless the sensor range or shot reach changes.
