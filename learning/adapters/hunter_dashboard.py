"""The Hunter's dashboard charts, in the order and words the trainer page has always used; tools/ppo_neural.py
writes these keys (no metrics() hook), so tests check them against a recorded Hunter log."""
from learning.dashboard import Metric

METRICS = (
    Metric('speed_fraction', 'Speed',
           'Higher is better. Average speed as a share of top speed.', higher_is_better=True),
    Metric('powerups_per_episode', 'Powerups per episode',
           'Higher is better. Crystals the hunter collects.', higher_is_better=True),
    Metric('upgraded_fraction', 'Hunter power boost',
           'Share of time the generic power boost is active.'),
    Metric('deaths_per_episode', 'Deaths per episode',
           'Lower is better. Share of episodes in which the hunter is destroyed.', higher_is_better=False),
    Metric('compass_follow', 'Follows the enemy compass',
           'Higher is better. Share of the time with no enemy in sight that the hunter heads within 45° of the compass.',
           higher_is_better=True),
    Metric('hits_per_episode', 'Hits per episode',
           'Higher is better. Hunter shots that reach an enemy.', higher_is_better=True),
    # Runs before the rename logged free_shots_per_episode.
    Metric('unaimed_shots_per_episode', 'Unaimed shots per episode',
           'Shots not within 20° of an enemy in sight (at walls, at nothing, or well wide), each at the shot price.',
           aliases=('free_shots_per_episode',)),
    Metric('panic_fraction', 'Time in panic',
           'Share of decisions made in panic: after the last 5 s scored below the panic level, choices are more random '
           'until the score recovers.'),
    Metric('bored_fraction', 'Bored time',
           'Lower is better. Share of the time with no enemy in sight in which nothing new has come into view for a '
           'second: the same nearby walls (within 3 cells) and crystals as in the last 10 s.', higher_is_better=False),
    Metric('rules_beaten', 'Rules hunter beaten',
           'Higher is better. Share of Rules-hunter episodes in which it is destroyed.', higher_is_better=True),
    Metric('kills_per_min', 'Kills per minute',
           'Must not fall.', higher_is_better=True),
    Metric('wall_quotient_per_min', 'Wall collision quotient (per minute)',
           'Lower is better. Harder crashes count more.', higher_is_better=False),
    Metric('hits_taken_per_min', 'Enemy hits taken per minute',
           'Lower is better.', higher_is_better=False),
)

# Logged by tools/ppo_neural.py but never charted.
HIDDEN = ('score', 'rules_episodes')
