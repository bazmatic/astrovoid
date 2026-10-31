// A stand-in browser for the dashboard's ES modules under Node: elements by id, a fake trainer server behind
// fetch, captured timers and an in-memory localStorage. Tests drive the page's real functions and read back what
// a user would see (element text, values, HTML) and what the page sent to the server.
const STATIC = new URL('../../tools/trainer/static/', import.meta.url);

function element(id) {
  return {id, value: '', innerHTML: '', textContent: '', className: '', outerHTML: '', hidden: false, disabled: false,
    dataset: {}, isConnected: true, selectedOptions: [{text: 'Normal'}], querySelectorAll: () => [],
    classList: {add() {}, remove() {}, toggle() {}, contains: () => false}};
}

export async function page({routes = {}} = {}) {
  const els = {};
  const el = id => (els[id] ??= element(id));
  const requests = [];
  // The trainer's answers by path; a function gets the posted body. Anything else is a 404 like the real server.
  const server = {routes: {'api/status': {}, 'api/runs': [], 'api/tasks': [], ...routes}, requests};
  const answer = path => {
    if (path in server.routes) return server.routes[path];
    if (/^api\/runs\/run\d+\/(data)$/.test(path)) return [];
    if (/^api\/runs\/run\d+\/(config|settings)$/.test(path)) return {};
    return undefined;
  };
  globalThis.fetch = async (url, opts = {}) => {
    const path = String(url).replace(/^\//, ''), body = opts.body ? JSON.parse(opts.body) : undefined;
    requests.push({path, body});
    let value = answer(path);
    if (typeof value === 'function') value = await value(body);
    const ok = value !== undefined;
    return {ok, status: ok ? 200 : 404, statusText: ok ? 'OK' : 'Not Found',
      json: async () => structuredClone(ok ? value : {error: 'not found'})};
  };
  globalThis.document = {getElementById: el, querySelector: () => null, querySelectorAll: () => [], documentElement: {}};
  globalThis.getComputedStyle = () => ({getPropertyValue: () => '#888'});
  const storage = new Map();
  globalThis.localStorage = {getItem: k => storage.get(k) ?? null, setItem: (k, v) => storage.set(k, String(v))};
  const timers = [];
  globalThis.setTimeout = fn => timers.push(fn);
  globalThis.clearTimeout = () => {};
  const intervals = [];
  globalThis.setInterval = (fn, ms) => intervals.push(ms);
  globalThis.matchMedia = () => ({addEventListener() {}});
  const load = name => import(new URL(name, STATIC));
  const [state, charts, layout, strip, rules, runs, form, replay] = await Promise.all(
    ['state.js', 'charts.js', 'layout.js', 'strip.js', 'rules.js', 'runs.js', 'settings-form.js', 'replay.js'].map(load));
  // Lets fire-and-forget requests (a chart refresh, an episode list) finish.
  const settle = async () => { for (let i = 0; i < 20; i++) await new Promise(r => setImmediate(r)); };
  const posted = path => requests.filter(r => r.path === path && r.body !== undefined).map(r => r.body);
  // Opens the page as the browser does: main.js wires the controls, loads, and starts polling.
  const boot = async () => { await load('main.js'); await settle(); };
  return {el, S: state.S, server, posted, timers, intervals, settle, boot, charts, layout, strip, rules, runs, form, replay};
}
