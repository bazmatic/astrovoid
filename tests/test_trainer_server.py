import json
import socket
import threading
import urllib.error
import urllib.request

import pytest

from tests.test_trainer_control import FakeLaunch, make_run, trainer
from tools.trainer import server as server_module

LINE = 'policy_loss=0.1 iteration={i} score=70.5 rollout_s=18.0 update_s=3.0'


@pytest.fixture
def setup(tmp_path):
    make_run(tmp_path, 'run51', 2)
    run52 = make_run(tmp_path, 'run52', 3)
    (run52 / 'train.log').write_text(''.join(LINE.format(i=i) + '\n' for i in range(3)) + 'policy_loss=0.2 itera')
    state = {'processes': [], 'launch': FakeLaunch()}
    httpd = server_module.make_server(0, root=tmp_path, processes=lambda: state['processes'],
                                      launch=lambda *a: state['launch'](*a))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    state['url'] = f'http://127.0.0.1:{httpd.server_address[1]}'
    state['root'] = tmp_path
    yield state
    httpd.shutdown()
    httpd.server_close()


def get(setup, path):
    with urllib.request.urlopen(setup['url'] + path) as response:
        return response.status, response.headers, response.read()


def get_json(setup, path):
    return json.loads(get(setup, path)[2])


def post(setup, path, body=None):
    request = urllib.request.Request(setup['url'] + path, data=json.dumps(body or {}).encode(), method='POST',
                                     headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_status_and_runs_are_served(setup):
    assert get_json(setup, '/api/status')['state'] == 'idle'
    setup['processes'] = [trainer(9, setup['root'] / 'run52')]
    status = get_json(setup, '/api/status')
    assert status['state'] == 'training' and status['run'] == 'run52' and status['iteration'] == 2
    runs = get_json(setup, '/api/runs')
    assert [r['name'] for r in runs] == ['run51', 'run52'] and runs[1]['checkpoints'] == ['iter0000', 'iter0001', 'iter0002']
    assert runs[1]['state'] == 'training'
    _, headers, _ = get(setup, '/api/status')
    assert headers['Cache-Control'] == 'no-store'


def test_run_data_skips_bad_lines_and_unknown_runs_are_404(setup):
    assert [row['iteration'] for row in get_json(setup, '/api/runs/run52/data')] == [0, 1, 2]
    assert get_json(setup, '/api/runs/run52/config')['args']['iterations'] == 50
    for path in ('/api/runs/run99/data', '/api/runs/../x/data', '/nope'):
        with pytest.raises(urllib.error.HTTPError) as e:
            get(setup, path)
        assert e.value.code == 404


def test_settings_carry_their_sources_and_the_levels_to_choose_from(setup):
    values = get_json(setup, '/api/runs/run52/settings')
    assert values['speed_penalty'] == {'value': 3.0, 'source': 'recorded'}
    schema = get_json(setup, '/api/settings')
    assert {'dest': 'levels', 'kind': 'levels'}.items() <= next(s for s in schema['settings'] if s['dest'] == 'levels').items()
    assert 1 in schema['levels'] and 25 in schema['levels'] and schema['levels'] == sorted(schema['levels'])


def test_start_posts_from_and_changes_and_returns_the_new_run(setup):
    code, body = post(setup, '/api/start', {'from': 'run51/iter0000', 'changes': {'speed_penalty': 2, 'levels': [1, 2]}})
    assert code == 200 and body['run'] == 'run53' and body['started_from'] == 'run51/iter0000'
    assert body['changes'] == [{'setting': 'levels', 'old': list(range(1, 31)), 'new': [1, 2]},
                               {'setting': 'speed_penalty', 'old': 3.0, 'new': 2.0}]
    assert len(setup['launch'].commands) == 1


def test_a_busy_trainer_is_a_409_with_the_message(setup):
    setup['processes'] = [trainer(9, setup['root'] / 'run52')]
    assert post(setup, '/api/start') == (409, {'error': 'run52 is training; stop or pause it first'})
    assert post(setup, '/api/resume', {'run': None})[0] == 409
    setup['processes'] = []
    assert post(setup, '/api/stop') == (409, {'error': 'nothing is training'})


def test_pause_and_stop_act_on_the_training_run(setup):
    setup['processes'] = [trainer(9, setup['root'] / 'run52')]
    assert post(setup, '/api/pause') == (200, {'run': 'run52'})
    assert (setup['root'] / 'run52' / 'PAUSE').exists()


def test_bad_requests_are_a_400(setup):
    assert post(setup, '/api/start', {'changes': {'speed_penalty': 'fast'}})[0] == 409
    request = urllib.request.Request(setup['url'] + '/api/start', data=b'{nope', method='POST',
                                     headers={'Content-Type': 'application/json'})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(request)
    assert e.value.code == 400


def test_the_page_is_served(setup):
    code, headers, body = get(setup, '/')
    assert code == 200 and headers['Content-Type'].startswith('text/html') and b'id="status"' in body


def test_a_taken_port_moves_to_the_next_one(tmp_path):
    taken = socket.socket()
    taken.bind(('127.0.0.1', 0))
    taken.listen()
    port = taken.getsockname()[1]
    try:
        httpd, used = server_module.open_server(port, root=tmp_path)
        assert used != port and port < used <= port + 10
        httpd.server_close()
    finally:
        taken.close()


def raw_post(setup, path, headers):
    request = urllib.request.Request(setup['url'] + path, data=b'{}', method='POST', headers=headers)
    try:
        with urllib.request.urlopen(request) as response:
            return response.status
    except urllib.error.HTTPError as e:
        return e.code


def test_other_web_pages_cannot_drive_the_trainer(setup):
    setup['processes'] = [trainer(9, setup['root'] / 'run52')]
    assert raw_post(setup, '/api/pause', {'Content-Type': 'text/plain'}) == 415          # no-cors simple request
    assert raw_post(setup, '/api/pause', {'Content-Type': 'application/json', 'Origin': 'https://evil.example'}) == 403
    assert raw_post(setup, '/api/pause', {'Content-Type': 'application/json', 'Host': 'evil.example:8765'}) == 403
    assert not (setup['root'] / 'run52' / 'PAUSE').exists()
    port = setup['url'].rsplit(':', 1)[1]
    assert raw_post(setup, '/api/pause', {'Content-Type': 'application/json',
                                         'Origin': f'http://localhost:{port}', 'Host': f'localhost:{port}'}) == 200


def replayable(setup):
    run = setup['root'] / 'run52'
    config = json.loads((run / 'config.json').read_text())
    config.update({'episode': {'episodes_per_iteration': 6, 'levels': [3, 16], 'rules_share': 0.0},
                   'shaping': {'horizon': 60.0}, 'decision_frames': 6, 'turn_rate': 1.0})
    (run / 'config.json').write_text(json.dumps(config))
    return run


def test_an_iterations_episodes_are_listed_with_their_levels(setup):
    replayable(setup)
    code, body = post(setup, '/api/episodes', {'run': 'run52', 'iteration': 2})
    assert code == 200 and [e['episode'] for e in body] == list(range(6))
    assert {e['level'] for e in body} <= {3, 16}
    assert post(setup, '/api/episodes', {'run': 'run52', 'iteration': 3}) == \
        (409, {'error': 'run52 has not finished iteration 3'})
    assert post(setup, '/api/episodes', {'run': '../x', 'iteration': 0})[0] == 409


def test_a_run_from_before_replays_says_so(setup):
    code, body = post(setup, '/api/episodes', {'run': 'run52', 'iteration': 1})
    assert code == 409 and body['error'].startswith('run52 cannot be replayed')


def test_flying_reports_how_each_episode_went(setup, monkeypatch):
    replayable(setup)
    import tools.watch_episode as watch_episode
    monkeypatch.setattr(watch_episode, 'fly_all', lambda run, iteration, workers:
                        [(16, 0.5, -100.0, 1, 'died', 20.0), (3, 0.0, 40.0, 10, 'cleared', 30.0)])
    code, body = post(setup, '/api/episodes', {'run': 'run52', 'iteration': 2, 'fly': True})
    assert code == 200 and body[0] == {'episode': 0, 'level': 16, 'panic': 0.5, 'return': -100.0, 'kills': 1,
                                       'end': 'died', 'seconds': 20.0}


def test_watching_opens_the_episode_at_the_chosen_speed(setup):
    run = replayable(setup)
    assert post(setup, '/api/replay', {'run': 'run52', 'iteration': 2, 'episode': 5, 'speed': 0.5}) == \
        (200, {'watching': 5})
    assert setup['launch'].commands[-1][1:] == ['-m', 'tools.watch_episode', str(run), '2', '5', '--speed', '0.5']
    assert post(setup, '/api/replay', {'run': 'run52', 'iteration': 2, 'episode': 6})[0] == 409
    assert post(setup, '/api/replay', {'run': 'run52', 'iteration': 2, 'episode': 0, 'speed': 4})[0] == 409
    assert len(setup['launch'].commands) == 1


def test_runs_say_whether_they_can_be_replayed(setup):
    replayable(setup)
    assert [(r['name'], r['replayable']) for r in get_json(setup, '/api/runs')] == [('run51', False), ('run52', True)]


def test_explicit_network_bind_accepts_its_own_host_and_origin_only(tmp_path):
    from types import SimpleNamespace
    handler = object.__new__(server_module.make_handler(tmp_path, lambda: [], None))
    handler.server = SimpleNamespace(server_address=('100.76.248.12', 8766))
    handler.headers = {'Host': '100.76.248.12:8766', 'Origin': 'http://100.76.248.12:8766'}
    assert handler.from_this_page()
    handler.headers['Origin'] = 'http://unrelated.example'
    assert not handler.from_this_page()
    handler.headers = {'Host': 'unrelated.example:8766'}
    assert not handler.from_this_page()


def test_tailscale_aliases_accept_replays_and_reject_untrusted_origins(tmp_path):
    from types import SimpleNamespace
    aliases = ['quiescent', 'quiescent.tailf8052b.ts.net']
    handler = object.__new__(server_module.make_handler(tmp_path, lambda: [], None, allowed_hosts=aliases))
    handler.server = SimpleNamespace(server_address=('100.76.248.12', 8766))
    for name in aliases + ['Quiescent']:
        handler.headers = {'Host': f'{name}:8766', 'Origin': f'http://{name}:8766'}
        assert handler.from_this_page()
        handler.headers['Origin'] = 'http://unrelated.example:8766'
        assert not handler.from_this_page()
    handler.headers = {'Host': 'unrelated.example:8766', 'Origin': 'http://unrelated.example:8766'}
    assert not handler.from_this_page()
