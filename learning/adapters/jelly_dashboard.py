"""The Jelly team's starter dashboard: keys from jelly_scenario.summarise(), which metrics() writes into train.log over
all of an iteration's episodes. The per-stage stage<n>_* copies are left to the automatic "Other" section for now."""
from learning.dashboard import Layout, Metric, RewardRule

METRICS = (
    Metric('catches_per_minute', 'Catches per minute',
           'Target catches per minute over all episodes. Ship-fight episodes have no target, so they pull it down.',
           unit='/min', section='Outcome', higher_is_better=True, short='Catches / min', digits=1),
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
LAYOUT = Layout(sections=('Training', 'Outcome', 'Navigation', 'Teamwork', 'Ship fight', 'Policy'),
                strip=('catches_per_minute', 'stuck_fraction'))

# The per-stage copies jelly_scenario.metrics() writes as stage<n>_<key> (its STAGE_KEYS, repeated here so the dashboard
# need not import the game; a test checks they match). Per-stage charts are a later addition.
_STAGE_KEYS = {1: ('episodes', 'catches', 'seconds', 'catches_per_minute', 'stuck_fraction', 'time_to_contact'),
               2: ('episodes', 'catches', 'seconds', 'catches_per_minute', 'stuck_fraction', 'time_to_contact',
                   'angular_spread', 'bunched_fraction'),
               3: ('episodes', 'seconds', 'stuck_fraction', 'time_to_contact', 'ship_hits', 'ship_kills',
                   'jelly_deaths', 'survival_fraction', 'time_to_ship_kill')}
# Raw counters behind the charted rates, and imitation_loss (imitation bootstrap is off for the Jelly).
HIDDEN = ('catches', 'seconds', 'stuck_seconds', 'ship_kills', 'bunched_seconds', 'flank_seconds', 'time_to_ship_kill',
          'mean_episode_return', 'episodes', 'imitation_loss',
          *(f'stage{stage}_{key}' for stage, keys in _STAGE_KEYS.items() for key in keys))

# The Jelly's reward constants (learning/adapters/jelly_scenario.py) as run settings, defaulting to their values there.
# A run recorded before they were settings reports them as not recorded, with these defaults (what it trained with).
# Stage 3 mixes stage-1 and stage-2 retention cases into its training, where catches still pay.
REWARD_RULES = (
    RewardRule('catch', 'Catch', 'To the Jelly that touches the target with its body; the target reappears at least '
               '300 px from every Jelly. Stages 1-2 (and the stage-3 retention cases).',
               'reward', (1, 2, 3), 'jelly_catch_reward', 10.),
    RewardRule('team_catch_share', 'Teammate catch share', "Share of the catch reward every other living Jelly gets for "
               "a teammate's catch.", 'shaping', (1, 2, 3), 'jelly_team_catch_share', .25),
    RewardRule('progress', 'Closing on the quarry', 'Per pixel a Jelly closes on its quarry (the target, or the ship at '
               'stage 3) over a decision, about 0.03 at full speed; moving away costs the same.',
               'reward', (1, 2, 3), 'jelly_progress_reward', .002),
    RewardRule('stuck', 'Stuck', 'Per decision spent stuck: pushing throughout the last second while moving less than '
               '10 px (0.5 per second at the default).', 'penalty', (1, 2, 3), 'jelly_stuck_penalty', .05),
    RewardRule('flank', 'Flanking', 'Per decision to every living Jelly, times the flank spread (0 all from one side, 1 '
               'an even ring) of the Jellies within the flank range of the quarry, when two or more are that close.',
               'reward', (2, 3), 'jelly_flank_reward', .005),
    RewardRule('flank_range', 'Flank range', 'px: Jellies this close to the quarry count towards its flank spread.',
               'shaping', (2, 3), 'jelly_flank_range', 200.),
    RewardRule('bunch_distance', 'Bunching distance', 'px between Jelly centres: closer than this is bunched (about two '
               'body widths).', 'shaping', (2, 3), 'jelly_bunch_distance', 40.),
    RewardRule('bunch', 'Bunching', 'Per decision, to each Jelly of every pair closer than the bunching distance.',
               'penalty', (2, 3), 'jelly_bunch_penalty', .01),
    RewardRule('ship_hit', 'Ship hit', "To the Jelly whose touch costs the training ship a hull point (none during the "
               "hull's immunity after a hit).", 'reward', (3,), 'jelly_ship_hit_reward', 4.),
    RewardRule('ship_kill', 'Ship kill', "On top of the hit reward, to the Jelly whose touch takes the ship's last hull "
               "point.", 'reward', (3,), 'jelly_ship_kill_reward', 10.),
    RewardRule('team_ship_share', 'Teammate ship share', "Share of a teammate's ship hit and kill rewards every other "
               "living Jelly gets.", 'shaping', (3,), 'jelly_team_ship_share', .25),
    RewardRule('death', 'Jelly killed', 'To a Jelly the ship kills, on the decision it dies.',
               'penalty', (3,), 'jelly_death_penalty', 5.),
    RewardRule('team_death_share', 'Teammate death share', 'Share of the death penalty every surviving Jelly loses for '
               'each teammate lost.', 'shaping', (3,), 'jelly_team_death_share', .25),
)


def stage(row):
    """The highest stage whose episodes the row's iteration flew (stage<n>_episodes, from jelly_scenario.metrics());
    lower stages are its retention cases."""
    flown = [n for n in _STAGE_KEYS if row.get(f'stage{n}_episodes')]
    return max(flown) if flown else None
