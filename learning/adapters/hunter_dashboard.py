"""The Hunter's dashboard charts, in the order and words the trainer page has always used; tools/ppo_neural.py
writes these keys (no metrics() hook), so tests check them against a recorded Hunter log."""
from learning.dashboard import Layout, Metric, RewardRule, number

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
           'Must not fall.', higher_is_better=True, short='Kills / min', digits=1),
    Metric('wall_quotient_per_min', 'Wall collision quotient (per minute)',
           'Lower is better. Harder crashes count more.', higher_is_better=False,
           short='Wall quotient / min'),
    Metric('hits_taken_per_min', 'Enemy hits taken per minute',
           'Lower is better.', higher_is_better=False, short='Hits taken / min'),
)

LAYOUT = Layout(strip=('kills_per_min', 'wall_quotient_per_min', 'hits_taken_per_min'))

# Logged by tools/ppo_neural.py but never charted.
HIDDEN = ('score', 'rules_episodes')

# The reward terms tools/ppo_neural.py reward_summary() records in a run's config.json (its "rewards" rows), in its
# order and words. setting: the argument that sets it ('' for a fixed term). Rows are matched by name; older runs
# named the unaimed shot price "Shot with no enemy in sight".
_RULES = (   # key, recorded row names, kind, setting, description
    ('kills', ('Kills',), 'reward', '', 'points shared across all the enemies in an episode'),
    ('powerup', ('Powerup collected',), 'reward', 'powerup_reward', 'points each'),
    ('upgrade', ('Gun upgraded',), 'reward', 'upgrade_bonus', 'points per second with a hunter power boost'),
    ('wall', ('Wall impact',), 'penalty', 'wall_scale', 'points per full-speed hit (scales with the speed lost)'),
    ('enemy_hit', ('Enemy hit',), 'penalty', 'hit_scale', 'points each'),
    ('idle', ('Idle',), 'penalty', '', 'points per second beyond 20 s without a kill, until the field is clear'),
    ('speed', ('Flying below top speed',), 'penalty', 'speed_penalty',
     'points per second at a standstill, in proportion to the shortfall'),
    ('still', ('Crawling under the still speed',), 'penalty', 'still_penalty',
     'points per second below the still speed (see Reward details)'),
    ('turn_change', ('Starting or reversing a turn',), 'penalty', 'turn_change_penalty', 'points each'),
    ('reversal', ('Reversing a turn directly',), 'penalty', 'reversal_penalty', 'extra points each, left to right or back'),
    ('death', ('Death',), 'penalty', 'death_penalty',
     'points when the hunter is destroyed (it survives as many hits as its health: see Reward details)'),
    ('rules_bounty', ('Rules hunter destroyed',), 'reward', 'rules_bounty',
     'points, on top of its share of the kill reward'),
    ('compass', ('Following the enemy compass',), 'reward', 'compass_reward',
     'points per maze width the route to the nearest enemy shortens while none is in sight'),
    ('hit', ('Hit on an enemy',), 'reward', 'hit_reward', 'points per shot that reaches an enemy'),
    ('turning', ('Turning',), 'penalty', 'turning_penalty', 'points per second spent turning'),
    ('unaimed_shot', ('Unaimed shot', 'Shot with no enemy in sight'), 'penalty', 'shot_price',
     'points each, unless within 20° of an enemy in sight'),
    ('boredom', ('Boredom',), 'penalty', 'boredom_penalty',
     'points per second with no enemy in sight in a cell visited within the boredom window (see Reward details)'),
)
REWARD_RULES = tuple(RewardRule(key, names[0], description, kind, (), setting)
                     for key, names, kind, setting, description in _RULES)


def recorded(config):
    """The values the run's "rewards" rows record. reward_summary() leaves out zero terms, so a term without a row was
    off (0) in a run that has the rows; a config without them records nothing."""
    rows = config.get('rewards')
    if not isinstance(rows, list):
        return {}
    by_name = {row.get('name'): row.get('value') for row in rows if isinstance(row, dict)}
    found = {}
    for key, names, *_ in _RULES:
        value = next((by_name[n] for n in names if n in by_name), 0.)
        # Summary values retain the setting's sign; the renderer applies the rule's reward/penalty direction.
        found[key] = value if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.
    return found


def _levels(levels):
    """Level numbers as ranges, as the page has always written them: 3,5-7,25."""
    if not levels:
        return 'the tune set'
    ordered, out, i = sorted(set(levels)), [], 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and ordered[j + 1] == ordered[j] + 1:
            j += 1
        out.append(f'{ordered[i]}' if i == j else f'{ordered[i]}-{ordered[j]}')
        i = j + 1
    return ','.join(out)


def cards(config):
    """The old page's Hunter Episodes card, and the settings its reward rows spelled out."""
    e, args, found = config.get('episode') or {}, config.get('args') or {}, recorded(config)
    out = []
    if e:
        text = (f"Up to {number(e.get('horizon_seconds'))} s of fighting, then up to {number(e.get('after_clear_seconds'))}"
                f" s more to collect powerups once the last enemy is dead. {number(e.get('episodes_per_iteration'))} "
                'episodes per iteration.')
        if e.get('health'):
            text += (f" The hunter survives {number(e['health'])} energy: each enemy hit costs 1, and a wall takes up to "
                     f"{number(e.get('wall_energy'))} for a full-speed crash (less for a gentler one). The episode ends if "
                     'it is destroyed.')
        if e.get('levels'):
            text += f" Levels: {_levels(e['levels'])}."
        out.append(dict(title='Episodes', rows=[], note=text))
    details = []
    if found.get('death') and args.get('health'):
        details.append(dict(label='Health', value=f"{number(args['health'])} hits",
                            description='Hits the hunter survives before it is destroyed'))
    if found.get('still') and args.get('still_speed') is not None:
        details.append(dict(label='Still speed', value=f"{args['still_speed']:.0%}",
                            description='Share of top speed below which the hunter counts as crawling'))
    if found.get('boredom'):
        details.append(dict(label='Boredom window', value=f"{number(args.get('boredom_window', 10.))} s",
                            description='A cell visited within this time is not new'))
    if details:
        out.append(dict(title='Reward details', rows=details))
    return out
