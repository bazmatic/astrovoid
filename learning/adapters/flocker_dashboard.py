"""Flocker outcome, coordination and rest metrics."""
from learning.dashboard import Layout, Metric, RewardRule
from learning.flocker_rewards import DEFAULTS, recovered_settings

METRICS = tuple(Metric(key,title,description,unit='%' if key in ('perch_success','accuracy','aim_accuracy') else '',section=section,higher_is_better=better) for key,title,description,section,better in (
    ('hits_per_minute','Hits / minute','Accepted projectile damage per minute.','Combat',True),
    ('accuracy','Damage / shot','Shots that reduce health divided by emitted shots; damage immunity can block otherwise accurate hits.','Combat',True),
    ('aim_accuracy','Aim accuracy','Shots that physically land divided by emitted shots, including hits blocked by damage immunity.','Combat',True),
    ('survival_fraction','Survival','Fraction of Flockers alive at episode end.','Combat',True),
    ('useful_volleys_per_minute','Useful volleys / minute','Synchronized same-target launch groups that hit.','Coordination',True),
    ('participation','Volley participation','Share of eligible nearby teammates joining a volley.','Coordination',True),
    ('median_launch_spread','Launch spread','Median frames between first and last shot; 7 means no volleys.','Coordination',False),
    ('cohesion','Cohesion','Share of Flocker time with a teammate within 100 pixels.','Flight',True),
    ('alignment','Velocity alignment','Time-weighted agreement with nearby teammates’ travel directions; stationary birds earn zero.','Flight',True),
    ('bunched_fraction','Teammate contact','Share of time touching or overlapping a teammate; legacy proximity runs retain their recorded distance rule.','Flight',False),
    ('hard_landings','Wall impacts','Hard wall, gate and boundary collisions; gentle perches are excluded.','Flight',False),
    ('wall_collision_cost','Wall collision cost','Total reward deducted from the birds that collided.','Flight',False),
    ('stuck_fraction','Stuck','Share of time thrusting without meaningful movement.','Flight',False),
    ('mean_throttle','Mean throttle','Applied continuous throttle, from zero to one.','Flight',None),
    ('fractional_throttle_fraction','Fractional throttle','Time applying throttle between 0.05 and 0.95.','Flight',None),
    ('perches','Gentle perches','Successful physical wall attachments.','Perching',True),
    ('perch_success','Perch success (%)','Successful attachments divided by attempts in training episodes. Stage 2 requires 90% on held-out validation trials.','Perching',True),
    ('perched_fraction','Time perched','Share of Flocker time attached to a wall.','Perching',None),
))
LAYOUT = Layout(sections=('Training','Combat','Coordination','Flight','Perching','Policy'),
                strip=('hits_per_minute','useful_volleys_per_minute','survival_fraction'))
HIDDEN = ('seconds','episodes','shots','hits','landed_hits','non_damaging_hits','volleys','kills')
REWARD_RULES = tuple(RewardRule(n,'Teammate contact penalty' if n=='bunch_penalty' else n.replace('_',' ').capitalize(),('Credit for improving aim toward a visible target’s predicted intercept; target motion alone earns nothing.'
                  if n=='aim_progress_reward' else 'Cost per actual wall impact, charged to the colliding bird; gentle perching costs nothing.'
                  if n=='wall_collision_penalty' else
                  'Per hit point a Flocker loses to incoming fire (a hit does half a point at stage 5 full strength), charged to the bird hit.'
                  if n=='damage_penalty' else
                  'Per decision a bird is in the line of fire: a hostile shot will pass within hitting distance in the next second.'
                  if n=='threat_penalty' else
                  'Legacy proximity threshold in pixels; ignored when contact_only is 1.'
                  if n=='bunch_distance' else
                  '1 penalizes only touching or overlapping; 0 retains the legacy proximity rule. Movement is not blocked.'
                  if n=='contact_only' else
                  'Per decision while touching or overlapping a teammate; once per bird regardless of neighbour count.'
                  if n=='bunch_penalty' else 'Run-scoped Flocker reward coefficient.'),
                               'shaping' if n in ('bunch_distance','contact_only') else 'penalty' if n.endswith(('cost','penalty')) else 'reward',(), 'flocker_'+n,v)
                     for n,v in DEFAULTS.items())


def stage(row):
    return row.get('battle_stage')
