"""The training manager's web app: the page, and a small JSON API over the engine. Local only."""
import json
import re
import webbrowser
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from tools.trainer import control, runs
from tools.trainer.control import TrainerError
from tools.trainer.processes import REPO, list_processes
from tools.trainer.settings import SETTINGS, config_of, read_settings

PAGE = Path(__file__).with_name('page.html')
RUN_PATH = re.compile(r'/api/runs/(run\d+)/(data|config|settings)')


def available_levels():
    return sorted(int(p.stem) for p in (REPO / 'levels').glob('*.json') if p.stem.isdigit())


def run_json(run):
    return {'name': run.name, 'state': run.state, 'iterations_done': run.iterations_done, 'total': run.total,
            'started_from': run.started_from, 'checkpoints': run.checkpoints}


def make_handler(root, processes, launch):
    root = Path(root)

    class Handler(BaseHTTPRequestHandler):
        def send(self, code, body, kind='application/json'):
            data = body if isinstance(body, bytes) else json.dumps(body, default=str).encode()
            self.send_response(code)
            self.send_header('Content-Type', kind)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = self.path.split('?')[0]
            if path in ('/', '/index.html'):
                return self.send(200, PAGE.read_bytes(), 'text/html; charset=utf-8')
            if path == '/api/status':
                return self.send(200, runs.status(root, processes()))
            if path == '/api/runs':
                return self.send(200, [run_json(r) for r in runs.list_runs(root, processes())])
            if path == '/api/settings':
                return self.send(200, {'settings': [asdict(s) for s in SETTINGS], 'levels': available_levels()})
            match = RUN_PATH.fullmatch(path)
            if match and (root / match.group(1)).is_dir():
                run_dir, what = root / match.group(1), match.group(2)
                if what == 'data':
                    return self.send(200, runs.log_rows(run_dir))
                if what == 'config':
                    return self.send(200, config_of(run_dir) or {})
                values = read_settings(run_dir, runs.run_folders(root))
                return self.send(200, {dest: asdict(v) for dest, v in values.items()})
            self.send(404, {'error': 'not found'})

        def do_POST(self):
            try:
                length = int(self.headers.get('Content-Length') or 0)
                body = json.loads(self.rfile.read(length) or b'{}')
                if not isinstance(body, dict):
                    raise ValueError
            except ValueError:
                return self.send(400, {'error': 'the request is not a JSON object'})
            path = self.path.split('?')[0]
            try:
                if path == '/api/start':
                    started = control.start(body.get('from'), body.get('changes'), root=root,
                                            processes=processes(), launch=launch)
                    return self.send(200, {'run': started.run, 'started_from': started.started_from,
                                           'changes': [{'setting': d, 'old': o, 'new': n}
                                                       for d, o, n in started.changes]})
                if path == '/api/stop':
                    return self.send(200, {'run': control.stop(root=root, processes=processes())})
                if path == '/api/pause':
                    return self.send(200, {'run': control.pause(root=root, processes=processes())})
                if path == '/api/resume':
                    return self.send(200, {'run': control.resume(body.get('run'), root=root, processes=processes(),
                                                                 launch=launch)})
            except TrainerError as e:
                return self.send(409, {'error': str(e)})
            self.send(404, {'error': 'not found'})

        def log_message(self, *args):
            pass

    return Handler


def make_server(port, root=runs.RL_ROOT, host='127.0.0.1', processes=list_processes, launch=None):
    return ThreadingHTTPServer((host, port), make_handler(root, processes, launch))


def open_server(port, root=runs.RL_ROOT, **kwargs):
    """A server on `port`, or the next free port above it (the old dashboard may still hold 8765)."""
    for candidate in range(port, port + 11):
        try:
            return make_server(candidate, root, **kwargs), candidate
        except OSError:
            continue
    raise OSError(f'ports {port}-{port + 10} are all in use')


def serve(port=8765, open_browser=True, root=runs.RL_ROOT):
    httpd, used = open_server(port, root)
    if used != port:
        print(f'port {port} is in use (the old dashboard?), so using {used}')
    url = f'http://127.0.0.1:{used}/'
    print(f'training manager: {url}  (ctrl-c to close it; training carries on)')
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
