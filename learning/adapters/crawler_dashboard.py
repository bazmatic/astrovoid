"""The Wallcrawler team's dashboard charts, in the order and words the trainer page has always used. Keys come from
crawler_scenario.metrics(), learning.run (battle_stage) and learning.ppo.update_team (imitation_loss)."""
from learning.dashboard import Metric

METRICS = (
    Metric('hits_per_minute', 'Team projectile hits per minute',
           'Wallcrawler team: accepted bullet impacts on the frozen opponents.', higher_is_better=True),
    Metric('mean_aim_quality', 'Predicted shot quality',
           'Mean launch-time interception quality, from 0 to 1. A shaping signal, not measured hits.'),
    Metric('target_clear_rate', 'Targets cleared',
           'Share of practice trials in which every target was hit.', higher_is_better=True),
    Metric('accuracy', 'Team accuracy',
           'Accepted hits divided by actual crawler shots.', higher_is_better=True),
    # The per-drill keys appear only in iterations that flew that kind of trial.
    Metric('precision_accuracy', 'Stationary-target accuracy',
           'Accepted hits / shots in harmless stationary-target drills.', higher_is_better=True, optional=True),
    Metric('tracking_accuracy', 'Moving-target accuracy',
           'Accepted hits / shots in harmless moving-target drills.', higher_is_better=True, optional=True),
    # Logged only by runs with the battle curriculum.
    Metric('battle_stage', 'Battle curriculum stage',
           '0: one Jelly; 1: two; 2: four; 3: four plus the armed hunter.', optional=True),
    Metric('pursuit_survival', 'Battle survival',
           'Fraction of battle crawlers alive at trial end.', higher_is_better=True, optional=True),
    Metric('pursuit_accuracy', 'Combat accuracy',
           'Accepted hits / shots in retained Jellyfish and neural-hunter encounters.', higher_is_better=True,
           optional=True),
    Metric('reversals_per_episode', 'Walking reversals per trial',
           'Actual direction changes while walking; stops and airborne motion excluded.'),
    Metric('jumps_per_episode', 'Voluntary jumps per trial',
           'Actual voluntary launches, excluding damage-induced detachment.'),
    Metric('bullet_hits_taken_per_episode', 'Bullet hits received per trial',
           'Average damaging bullet impacts received by the whole crawler team per trial. Lower is better.',
           higher_is_better=False),
    Metric('contact_hits_taken_per_episode', 'Jellyfish contact hits per trial',
           'Average accepted damaging contacts received by crawlers; repeated overlap is limited by a shared cooldown.',
           higher_is_better=False),
    Metric('imitation_loss', 'Demonstration rehearsal loss',
           'Weighted auxiliary loss that helps retain demonstrated jump and landing choices. This is not an '
           'escape-success score.'),
    Metric('airborne_fraction', 'Time airborne',
           'Share of crawler simulation time spent unattached, including stun and voluntary flight.'),
    Metric('survival', 'Crawler survival',
           'Share of the team still alive at trial end.', higher_is_better=True),
)
