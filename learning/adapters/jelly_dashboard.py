"""The Jelly team's starter dashboard: keys from jelly_scenario.summarise(), which metrics() writes into train.log over
all of an iteration's episodes. The per-stage stage<n>_* copies are left to the automatic "Other" section for now."""
from learning.dashboard import Layout, Metric

METRICS = (
    Metric('catches_per_minute', 'Catches per minute',
           'Target catches per minute over all episodes. Ship-fight episodes have no target, so they pull it down.',
           unit='/min', section='Outcome', higher_is_better=True),
    Metric('catch_probability', 'Episodes with a catch',
           'Share of episodes in which the team caught the target at least once.',
           section='Outcome', higher_is_better=True),
    Metric('stuck_fraction', 'Time stuck',
           'Share of Jelly time spent pushing for a whole second while moving less than 10 px.',
           section='Navigation', higher_is_better=False),
    Metric('time_to_contact', 'Time to first contact',
           'Mean seconds to the first catch or ship hit; an episode without one counts its whole length.',
           unit='s', section='Navigation', higher_is_better=False),
    Metric('team_catches_per_minute', 'Team catches per minute',
           'Catches per minute in episodes with two or more Jellies; 0 when there were none.',
           unit='/min', section='Teamwork', higher_is_better=True),
    Metric('angular_spread', 'Flank spread',
           'How evenly the Jellies within 200 px of their quarry surround it: 0 all from one side, 1 an even ring or '
           'pincer. Averaged over the time two or more were that close.',
           section='Teamwork', higher_is_better=True),
    Metric('bunched_fraction', 'Time bunched',
           'Share of Jelly time spent within 40 px of a teammate.',
           section='Teamwork', higher_is_better=False),
    Metric('ship_hits', 'Ship hits',
           'Hull points the Jellies knocked off the training ship, summed over the iteration\'s episodes.',
           section='Ship fight', higher_is_better=True),
    Metric('jelly_deaths', 'Jelly deaths',
           'Jellies killed, summed over the iteration\'s episodes.',
           section='Ship fight', higher_is_better=False),
    Metric('survival_fraction', 'Jelly survival',
           'Share of Jellies still alive at the end of ship-fight episodes; 1 when the iteration had none.',
           section='Ship fight', higher_is_better=True),
)

# Training return first and policy drift last, as for every task, with the Jelly's own sections between them.
LAYOUT = Layout(sections=('Training', 'Outcome', 'Navigation', 'Teamwork', 'Ship fight', 'Policy'))
