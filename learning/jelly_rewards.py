"""Jelly reward defaults and their manifest locations, shared by training, replay and the dashboard."""
DEFAULTS = {
    'catch_reward': 10., 'team_catch_share': .25, 'progress_reward': .002, 'stuck_penalty': .05,
    'flank_reward': .005, 'flank_range': 200., 'bunch_distance': 40., 'bunch_penalty': .01,
    'ship_hit_reward': 4., 'ship_kill_reward': 10., 'team_ship_share': .25,
    'death_penalty': 5., 'team_death_share': .25,
    'boredom_penalty': 0., 'boredom_window': 2., 'boredom_distance': 10.,
}
# setting -> (manifest block, field, multiplier); penalties are recorded as negative reward terms.
MANIFEST_FIELDS = {
    'boredom_penalty': ('rewards', 'boredom_per_decision', -1),
    'boredom_window': ('boredom', 'window_seconds', 1),
    'boredom_distance': ('boredom', 'distance_pixels', 1),
    'catch_reward': ('rewards', 'catch', 1),
    'team_catch_share': ('rewards', 'team_catch_share', 1),
    'progress_reward': ('rewards', 'progress_per_pixel', 1),
    'stuck_penalty': ('rewards', 'stuck_per_decision', -1),
    'flank_reward': ('rewards', 'stage2_flank_per_decision', 1),
    'flank_range': ('flank', 'range', 1),
    'bunch_distance': ('flank', 'bunch_distance', 1),
    'bunch_penalty': ('rewards', 'stage2_bunch_per_pair_decision', -1),
    'ship_hit_reward': ('rewards', 'stage3_ship_hit', 1),
    'ship_kill_reward': ('rewards', 'stage3_ship_kill', 1),
    'team_ship_share': ('rewards', 'stage3_team_ship_share', 1),
    'death_penalty': ('rewards', 'stage3_death', -1),
    'team_death_share': ('rewards', 'stage3_team_death_share', 1),
}
SETTINGS = tuple(f'jelly_{name}' for name in DEFAULTS)


def from_args(args):
    return {name: getattr(args, f'jelly_{name}', default) for name, default in DEFAULTS.items()}


def from_manifest(manifest):
    """Effective values, also for recordings made before these became CLI arguments."""
    return {name: manifest.get(block, {}).get(field, default / sign) * sign
            for name, default in DEFAULTS.items() for block, field, sign in (MANIFEST_FIELDS[name],)}


def recovered_settings(config):
    """An old Jelly run used its own manifest (or the original defaults), never a later run's experiment."""
    return {f'jelly_{name}': value for name, value in from_manifest(config.get('manifest') or {}).items()}
