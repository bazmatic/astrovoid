"""Drive the dashboard page's ES modules under Node with a stand-in browser and a fake trainer server.

Each test imports the real modules (tools/trainer/static/*.js) through tests/trainer_js/harness.mjs and checks what a
user would see or what the page sends the trainer. Nothing launches training or a game."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

NODE = shutil.which('node')
HARNESS = (Path(__file__).resolve().parent / 'trainer_js' / 'harness.mjs').as_uri()
FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'dashboard'
pytestmark = pytest.mark.skipif(NODE is None, reason='Node.js is needed to exercise dashboard JavaScript')


def run_js(body, given=None):
    """Run `body` as an ES module with `page` (the harness), `assert` and `given` (JSON passed in) in scope."""
    script = (f"import {{page}} from '{HARNESS}';import assert from 'node:assert/strict';"
              "import fs from 'node:fs';const given=JSON.parse(fs.readFileSync(0,'utf8'));\n" + body)
    out = subprocess.run([NODE, '--input-type=module', '-e', script], input=json.dumps(given),
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return out.stdout


RUN1 = dict(name='run1', state='done', iterations_done=1, replayable=True, checkpoints=['iter0000'])


@pytest.mark.parametrize('level,expected', [('25', 0), ('26', 1), ('', 1), ('24', None)])
def test_watch_the_last_episode_picks_the_newest_episode_on_the_chosen_level(level, expected):
    run_js(r"""
const p=await page({routes:{'api/runs':[given.run],'api/episodes':[{episode:0,level:25},{episode:1,level:26}],'api/replay':{}}});
p.S.EPISODES=[{episode:99,level:26}];        // stale: the previously viewed iteration's episodes
p.el('rp-level').value=given.level;
await p.replay.watchLatest();
const watched=p.posted('api/replay').map(b=>b.episode);
assert.deepEqual(watched,given.expected===null?[]:[given.expected]);
assert.deepEqual(p.posted('api/episodes'),[{run:'run1',iteration:0}]);
if(given.expected===null)assert.match(p.el('rp-msg').textContent,/no episodes on level 24/);
else assert.match(p.el('rp-msg').textContent,new RegExp(`Opening episode ${given.expected} in the game window`));
""", dict(run=RUN1, level=level, expected=expected))


def test_episode_lists_share_a_pending_request_and_a_late_answer_does_not_replace_the_current_one():
    run_js(r"""
const answers=[];
const p=await page({routes:{'api/episodes':()=>new Promise(resolve=>answers.push(resolve))}});
p.el('rp-run').value='run1';p.el('rp-iter').value='0';
const first=p.replay.loadEpisodes(),same=p.replay.loadEpisodes();
await p.settle();assert.equal(answers.length,1);
p.el('rp-iter').value='1';const second=p.replay.loadEpisodes();await p.settle();
const newest=[{episode:0,level:25}],older=[{episode:0,level:26}];
answers[1](newest);assert.deepEqual(await second,newest);
answers[0](older);assert.deepEqual(await first,older);assert.deepEqual(await same,older);
const list=p.el('rp-list').innerHTML;                // the list shows iteration 1's episodes, not the late answer
assert.match(list,/<td>25<\/td>/);assert.doesNotMatch(list,/<td>26<\/td>/);
""")


def test_start_sends_the_chosen_checkpoint_and_settings_and_says_what_started():
    run_js(r"""
const p=await page({routes:{'api/runs':[{...given.run1,name:'run67',checkpoints:['iter0040']}],
  'api/start':{run:'run68',started_from:'run67/iter0040',changes:[{setting:'levels'}]}}});
p.el('task').value='hunter';p.el('from-run').value='run67';p.el('from-iter').value='40';
p.S.EDITS={levels:[25,26]};
await p.form.start();
assert.deepEqual(p.posted('api/start'),[{from:'run67/iter0040',changes:{levels:[25,26],task:'hunter'}}]);
assert.equal(p.el('next-msg').textContent,'Started run68 from run67/iter0040, changing levels.');
""", dict(run1=RUN1))


def test_fresh_weights_show_the_task_defaults_and_start_from_new_with_the_edits():
    run_js(r"""
const p=await page({routes:{'api/start':{run:'run1',started_from:'random',changes:[{setting:'episodes'}]}}});
const episodes={dest:'episodes',default:96,group:'Episodes',label:'Episodes',kind:'int'};
p.S.SCHEMA={levels:[],settings:[{dest:'horizon',default:90,group:'Episodes',label:'Horizon',kind:'int'},episodes,
  {dest:'workers',default:8,group:'Training',label:'Workers',kind:'int'}],tasks:[{key:'wallcrawler_team',defaults:{horizon:60,workers:4}}]};
p.el('task').value='wallcrawler_team';p.el('from-run').value='new';
await p.form.fromChanged();
const form=p.el('form').innerHTML;
assert.match(form,/id="set-horizon" value="60"/);assert.match(form,/id="set-workers" value="4"/);
assert.match(form,/id="set-episodes" value="96"/);
assert.ok(!p.server.requests.some(r=>r.path.endsWith('/settings')),'fresh weights must not load a source run');
p.form.setEdit(episodes,'8');assert.equal(p.el('changed-count').textContent,'· 1 setting changed');
await p.form.start();
assert.deepEqual(p.posted('api/start'),[{from:'new',changes:{episodes:8,task:'wallcrawler_team'}}]);
""")


def test_enemy_hit_points_convert_to_the_existing_training_scale():
    run_js(r"""
const {typed}=(await page()).form;
assert.equal(typed({kind:'float',display_scale:3.5},'7'),2);
assert.equal(typed({kind:'float',display_scale:3.5},'0'),0);
assert.equal(typed({kind:'float'},'0.97'),0.97);
""")


def test_the_creature_follows_the_active_run_until_chosen_and_replays_offer_only_its_runs():
    run_js(r"""
const p=await page();
p.S.STATUS={run:'run2'};
p.S.RUNS=[given.run1,{...given.run1,name:'run2',task:'wallcrawler_team'}];
p.el('task').value='hunter';
p.runs.syncCreature();
assert.equal(p.el('task').value,'wallcrawler_team');assert.equal(p.el('fresh-team').disabled,false);
assert.equal(p.el('rp-run').innerHTML,'<option value="run2">run2</option>');
p.el('task').value='hunter';p.runs.syncCreature();assert.equal(p.el('task').value,'hunter');   // the user's choice stays
p.S.STATUS.run='run1';p.runs.syncCreature();
assert.equal(p.el('task').value,'hunter');assert.equal(p.el('fresh-team').disabled,true);
assert.equal(p.el('rp-run').innerHTML,'<option value="run1">run1</option>');
""", dict(run1=RUN1))


@pytest.mark.parametrize('bonus', [0, .01])
def test_crawler_rules_show_reward_and_penalty_cards_from_recorded_run(bonus):
    run_js(r"""
const config={task:'wallcrawler_team',args:{episodes:8},manifest:{horizon:60,
 rewards:{team_hit:2,shot:-.02,...(given.bonus?{predicted_shot_accuracy:given.bonus}:{})}}};
const p=await page({routes:{'api/runs/run92/config':config}});
p.S.VIEW='run92';
await p.rules.loadRules();
const rules=p.el('rules').innerHTML;
assert.match(rules,/Active rewards/);assert.match(rules,/Active penalties/);
assert.match(rules,/Accepted projectile hit/);assert.match(rules,/>\+2</);
assert.match(rules,/Actual shot/);assert.match(rules,/0.02/);assert.match(rules,/8 episodes per iteration/);
assert.equal(rules.includes('Predicted shot accuracy'),given.bonus>0);
""", dict(bonus=bonus))


def test_chart_start_filters_charts_and_strip_and_is_remembered_per_run():
    run_js(r"""
const p=await page(),{setChartStart}=p.charts;
const text=id=>p.el(id).textContent,html=id=>p.el(id).innerHTML;
p.runs.setView('run1');await p.settle();
p.S.D=[{iteration:0,mean_return:-999,rollout_s:1},{iteration:100,mean_return:10,rollout_s:1},{iteration:101,mean_return:20,rollout_s:1}];
setChartStart(100);
assert.equal(p.el('chart-start').value,'100');
assert.match(html('strip'),/<span>Iterations<\/span><b>2<\/b>/);assert.match(html('strip'),/>15.0</);
assert.doesNotMatch(html('charts'),/-999/);
assert.match(html('charts'),/M44.0 /);          // the first included iteration starts at the chart's left edge
assert.equal(text('chart-range'),'Showing 100–101 (2 iterations)');
setChartStart(1000);
assert.match(text('chart-range'),/No data from iteration 1000/);
assert.match(html('charts'),/No iterations in the selected range/);
setChartStart(0);assert.match(html('strip'),/<span>Iterations<\/span><b>3<\/b>/);
setChartStart(-5);assert.equal(p.el('chart-start').value,'0');
setChartStart('invalid');assert.equal(p.el('chart-start').value,'0');
setChartStart(100);
p.runs.setView('run2');assert.equal(p.el('chart-start').value,'0');      // each run keeps its own start
p.runs.setView('run1');assert.equal(p.el('chart-start').value,'100');
""")


def test_watch_the_last_episode_waits_for_the_active_run_instead_of_opening_an_older_one():
    run_js(r"""
const old={...given.run1,task:'wallcrawler_team'};
const p=await page({routes:{'api/status':{run:'run2',state:'training'},
  'api/runs':[old,{...old,name:'run2',checkpoints:[]}]}});
await p.replay.watchLatest();
assert.match(p.el('rp-msg').textContent,/run2.*first episode/);
assert.deepEqual(p.posted('api/episodes'),[]);assert.deepEqual(p.posted('api/replay'),[]);
""", dict(run1=RUN1))


def test_watch_the_last_episode_opens_once_the_first_iteration_arrives():
    run_js(r"""
const run={...given.run1,name:'run2',task:'wallcrawler_team',checkpoints:[]};
const p=await page({routes:{'api/status':{run:'run2',state:'training'},'api/runs':[run],
  'api/episodes':[{episode:11,level:23}],'api/replay':{}}});
await p.replay.watchLatest();
assert.match(p.el('rp-msg').textContent,/automatically/);assert.deepEqual(p.posted('api/replay'),[]);
assert.equal(p.el('rp-latest').textContent,'Cancel waiting for episode');
p.server.routes['api/runs']=[{...run,checkpoints:['iter0000']}];
await p.timers.at(-1)();
assert.deepEqual(p.posted('api/replay').map(b=>b.episode),[11]);
assert.equal(p.el('rp-latest').textContent,'Watch the last episode');
""", dict(run1=RUN1))


def test_opening_the_page_follows_the_active_run_and_draws_its_charts_strip_and_status():
    from learning import dashboard
    rows = log_rows('crawler')
    run_js(r"""
const run={...given.run1,name:'run7',task:'wallcrawler_team',state:'training',iterations_done:3};
const p=await page({routes:{'api/tasks':given.layouts,'api/runs':[run],'api/runs/run7/data':given.rows,
  'api/status':{run:'run7',state:'training',iteration:2,iterations:50},'api/settings':{settings:[],levels:[],tasks:[]}}});
await p.boot();
assert.match(p.el('status').innerHTML,/Training/);
assert.match(p.el('charts').innerHTML,/<h2>Team projectile hits per minute<\/h2>/);
assert.match(p.el('strip').innerHTML,/<span>Iterations<\/span><b>3<\/b>/);
assert.match(p.el('task').innerHTML,/value="wallcrawler_team"/);
assert.deepEqual(p.intervals,[5000,15000,15000,60000]);     // status, runs, chart data, rules
""", dict(run1=RUN1, layouts=dashboard.resolve_all(), rows=rows))


# The charts area and stat strip render() draws from the real /api/tasks layouts, read back as
# (section headings, (title, subtitle) per chart, (label, value) per strip cell).
RENDER = r"""
const p=await page();
Object.assign(p.S,{LAYOUTS:given.layouts,VIEW_TASK:given.task,D:given.rows,VIEW:'run1'});
p.layout.render();
const all=(re,s)=>[...s.matchAll(re)].map(m=>m.slice(1));
const charts=p.el('charts').innerHTML;
console.log(JSON.stringify({sections:all(/<h3[^>]*>(.*?)<\/h3>/g,charts).map(m=>m[0]),
 charts:all(/<h2>(.*?)<\/h2><p>(.*?)<\/p>/g,charts),strip:all(/<span>(.*?)<\/span><b>(.*?)<\/b>/g,p.el('strip').innerHTML),
 text:charts.replace(/<[^>]*>/g,' ')}));
"""


def render(task, rows):
    from learning import dashboard
    return json.loads(run_js(RENDER, dict(layouts=dashboard.resolve_all(), task=task, rows=rows)))


def log_rows(name, n=3, **extra):
    """n rows carrying every numeric key a recorded run of this task logged."""
    keys = json.loads((FIXTURES / f'{name}_log_keys.json').read_text())['keys']
    return [{**{k: 1.23456 for k in keys}, 'iteration': i, **extra} for i in range(n)]


def test_render_draws_only_the_task_layout_charts():
    from learning import dashboard
    keys = json.loads((FIXTURES / 'jelly_log_keys.json').read_text())['keys']
    page = render('jelly_team', log_rows('jelly'))
    assert page['charts'] == [[m['title'], m['sub']] for m in dashboard.charted('jelly_team', keys)]
    assert page['sections'] == ['Training', 'Outcome', 'Navigation', 'Teamwork', 'Ship fight', 'Policy']


# The old page's stat strip for these rows (three iterations, every value 1.23456), as tools/trainer/page.html drew it
# before the dashboard became pluggable.
OLD_STRIPS = {
    'hunter': [['Iterations', '3'], ['Training return', '1.2'], ['Kills / min', '1.2'],
               ['Wall quotient / min', '1.23'], ['Hits taken / min', '1.23'], ['Last iteration (s)', '2.5'],
               ['Game time', '6 h']],
    'crawler': [['Iterations', '3'], ['Training return', '1.2'], ['Team hits / min', '1.2'], ['Accuracy', '1.23'],
                ['Survival', '1.23'], ['Last iteration (s)', '2.5'], ['Game time', '6 h']],
}


@pytest.mark.parametrize('task, log', [('hunter', 'hunter'), ('wallcrawler_team', 'crawler')])
def test_hunter_and_wallcrawler_pages_draw_the_same_charts_and_strip_as_before(task, log):
    keys = set(json.loads((FIXTURES / f'{log}_log_keys.json').read_text())['keys'])
    old = json.loads((FIXTURES / 'old_page_charts.json').read_text())
    page = render(task, log_rows(log))
    assert page['charts'] == [[c['title'], c['sub']] for c in old if c['key'] in keys]   # and nothing under Other
    assert page['strip'] == OLD_STRIPS[log]


def test_render_puts_undeclared_numeric_keys_in_other_and_never_strings_or_booleans():
    page = render('hunter', log_rows('hunter', brand_new_rate=.5, checkpoint_name='iter0001.npz', gate_open=False))
    assert page['sections'][-1] == 'Other'
    assert page['charts'][-1] == ['brand_new_rate', '']
    assert 'checkpoint_name' not in page['text'] and 'gate_open' not in page['text']


def test_render_with_no_rows_shows_an_empty_state():
    page = render('jelly_team', [])
    assert page['charts'] == [] and 'No iterations logged yet' in page['text']
    assert ['Iterations', '0'] in page['strip']


def test_unknown_task_shows_a_message_and_shared_charts_only():
    page = render('made_up_task', log_rows('hunter'))
    assert 'made_up_task' in page['text'] and 'not one this trainer knows' in page['text']
    declared = [title for title, sub in page['charts'] if sub]   # Other charts have no subtitle
    assert declared == ['Training return', 'Distance from the starting policy (KL)', 'Policy entropy']
