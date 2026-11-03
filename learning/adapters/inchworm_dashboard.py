"""Physical outcomes for the inchworm curriculum."""
from learning.dashboard import Layout, Metric, RewardRule
from learning.inchworm_rewards import DEFAULTS, recovered_settings

METRICS = tuple(Metric(key,title,description,section='Body',higher_is_better=better) for key,title,description,better in (
    ('success','Lesson success','Fraction of episodes meeting the physical lesson objective.',True),
    ('bites','Accepted bites','Actual health-reducing bites.',True),
    ('distance','Goal distance','Final body-to-goal or mouth-to-prey gap in pixels.',False),
    ('effort','Muscle effort','Mean fraction of available bending torque.',False),
    ('airborne_fraction','Detached time','Fraction of frames without either grip.',False),
    ('recovered','Recovered grip','Fraction with at least 30 planted frames after the scheduled shove.',True),
    ('survived','Survival','Fraction still alive at episode end.',True),
))
LAYOUT = Layout(sections=('Training','Body','Policy'),strip=('success','bites','distance'))
HIDDEN = ('seconds','return_total','stage')
REWARD_RULES = tuple(RewardRule(n,n.replace('_',' ').capitalize(),
    'Signed reduction in goal distance; moving away subtracts reward.' if n=='progress_reward' else
    'Run-scoped inchworm reward coefficient; rates and events are documented in neural-inchworm.md.',
    'penalty' if n.endswith(('cost','penalty')) else 'reward',(), 'inchworm_'+n,v) for n,v in DEFAULTS.items())


def stage(row):
    return row.get('battle_stage')
