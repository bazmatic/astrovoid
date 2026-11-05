"""Physical outcomes for the inchworm curriculum."""
from learning.dashboard import Layout, Metric, RewardRule
from learning.inchworm_rewards import DEFAULTS, recovered_settings

METRICS = tuple(Metric(key,title,description,section='Body',higher_is_better=better) for key,title,description,better in (
    ('success','Lesson success','Fraction of episodes meeting the physical lesson objective.',True),
    ('bites','Accepted bites','Actual health-reducing bites.',True),
    ('distance','Goal distance','Final body-to-goal or mouth-to-prey gap in pixels.',False),
    ('backward_distance','Backward travel','Tail-first rear-segment travel in pixels; anchored bends and stun motion excluded.',False),
    ('effort','Muscle effort','Mean fraction of available bending torque.',False),
    ('airborne_fraction','Detached time','Fraction of frames without either grip.',False),
    ('recovered','Recovered grip','Fraction with at least 30 planted frames after the scheduled shove.',True),
    ('survived','Survival','Fraction still alive at episode end.',True),
))
LAYOUT = Layout(sections=('Training','Body','Policy'),strip=('success','bites','distance'))
HIDDEN = ('seconds','return_total','stage')
REWARD_RULES = tuple(RewardRule(n,n.replace('_',' ').capitalize(),
    'Head-first approach earns progress; retreat pays in full. Rear/curl drills use signed mouth-to-marker progress.' if n=='progress_reward' else
    'Net tail-first travel of the body centre along the surface, after crediting up to 30 px of forward travel; excludes retained rear anchors and forced stun motion.' if n=='backward_cost' else
    'About-face only: change in (facing the goal, clamped at 0) × (body stretched out); finishing the turn pays this once.' if n=='turn_reward' else
    'Crawl only: extra reward on arrival, scaled by the fraction of the time limit still left, so a faster crawl pays more.' if n=='speed_bonus' else
    'Crawl only: extra penalty per second on top of the time cost, so a slow crawl loses reward the whole way, not just at arrival.' if n=='crawl_time_cost' else
    'About-face only: extra penalty per second on top of the time cost, so turning and getting going quickly pays.' if n=='about_face_time_cost' else
    'Walking only (Crawl, and About-face once it faces the goal): penalty per second when the tail or head link is more than 15 degrees off parallel to the ground, scaled up to a right angle.' if n=='end_pitch_cost' else
    'Weight pulling the policy toward the scripted controller in the states it reaches during About-face (not a reward).' if n=='dagger_weight' else
    'Run-scoped inchworm reward coefficient; rates and events are documented in docs/notes/inchworm-training.md.',
    'penalty' if n.endswith(('cost','penalty')) else 'reward',(), 'inchworm_'+n,v) for n,v in DEFAULTS.items())


def stage(row):
    return row.get('battle_stage')
