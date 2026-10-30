"""Performance-gated battle difficulty, independent of actor and team-size schemas."""
STAGES = (
    {'name':'single_jelly', 'jelly_count':1, 'neural_hunter':False},
    {'name':'two_jellies', 'jelly_count':2, 'neural_hunter':False},
    {'name':'four_jellies', 'jelly_count':4, 'neural_hunter':False},
    {'name':'armed_hunter', 'jelly_count':4, 'neural_hunter':True},
)
MIN_TRIALS = 100
MIN_SURVIVAL = .5
MIN_SUCCESS = .6
INITIAL_STATE = dict(stage=0, trials=0, survivors=0, crawlers=0, successes=0)


def advance(state, summary):
    """Accumulate complete battle trials; promote only after a successful evidence block."""
    state = dict(state)
    for field in ('trials','survivors','crawlers','successes'):
        state[field] += summary.get('battle_'+field, 0)
    if state['trials'] >= MIN_TRIALS:
        ready = (state['survivors']/max(1,state['crawlers']) >= MIN_SURVIVAL
                 and state['successes']/state['trials'] >= MIN_SUCCESS)
        state = dict(INITIAL_STATE, stage=min(len(STAGES)-1,state['stage']+int(ready)))
    return state


def metadata():
    return dict(stages=list(STAGES), minimum_trials=MIN_TRIALS,
                minimum_crawler_survival=MIN_SURVIVAL, minimum_trial_success=MIN_SUCCESS,
                evidence='non_overlapping_completed_training_battle_blocks',
                initial_stage=INITIAL_STATE['stage'], heldout='full_encounter')
