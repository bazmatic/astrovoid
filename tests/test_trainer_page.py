"""Run the dashboard's replay handlers with fake requests; never launch training or a game."""
import shutil
import subprocess
from pathlib import Path

import pytest


NODE = shutil.which('node')
PAGE = Path(__file__).resolve().parents[1] / 'tools/trainer/page.html'


@pytest.mark.skipif(NODE is None, reason='Node.js is needed to exercise dashboard JavaScript')
@pytest.mark.parametrize('level,expected', [('25', 0), ('26', 1), ('', 1), ('24', None)])
def test_latest_replay_respects_the_selected_level(level, expected):
    script = r"""
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync(process.argv[1],'utf8');
const level=process.argv[2],expected=JSON.parse(process.argv[3]);
const handler=html.slice(html.indexOf("$('rp-latest').onclick=async()=>{"),html.indexOf("$('rp-run').onchange="));
const els=Object.fromEntries(['rp-latest','rp-msg','rp-run','rp-iter','rp-level'].map(id=>[id,{value:id==='rp-level'?level:'',className:'',textContent:''}]));
let watched=null;
const episodes=[{episode:0,level:25},{episode:1,level:26}];
const ctx={$:id=>els[id],LATEST_WAIT:null,clearTimeout(){},STATUS:null,async loadStatus(){},async loadRuns(){},RUNS:[{name:'run1',replayable:true,checkpoints:['iter0000']}],
  EPISODES:[{episode:99,level:26}], // stale data from the previously viewed iteration
  replayRuns(){return ctx.RUNS},fillReplay(){},renderEpisodes(){},async loadEpisodes(){return episodes},
  async post(){throw new Error('Unexpected request')},async watchEpisode(n){watched=n}};
vm.createContext(ctx);vm.runInContext(handler,ctx);
els['rp-latest'].onclick().then(()=>{
  assert.equal(watched,expected);
  if(expected===null)assert.match(els['rp-msg'].textContent,/no episodes on level 24/);
}).catch(e=>{console.error(e);process.exitCode=1});
"""
    import json
    subprocess.run([NODE, '-e', script, str(PAGE), level, json.dumps(expected)], check=True,
                   capture_output=True, text=True)


@pytest.mark.skipif(NODE is None, reason='Node.js is needed to exercise dashboard JavaScript')
def test_episode_loads_share_the_pending_request_and_return_the_requested_data():
    script = r"""
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync(process.argv[1],'utf8');
const loader=html.slice(html.indexOf('async function loadEpisodes(){'),html.indexOf('function fillLevels(){'));
const els={'rp-run':{value:'run1'},'rp-iter':{value:'0'},'rp-msg':{}};
let requests=[];
const ctx={$:id=>els[id],RP_KEY:'',EPISODES:[],EPISODE_REQUEST:null,
 renderEpisodes(){},fillLevels(){},post(){return new Promise(resolve=>requests.push(resolve))}};
vm.createContext(ctx);vm.runInContext(loader,ctx);
(async()=>{
 const first=ctx.loadEpisodes(),same=ctx.loadEpisodes();
 assert.equal(requests.length,1);
 els['rp-iter'].value='1';const second=ctx.loadEpisodes();
 const newest=[{episode:0,level:25}],older=[{episode:0,level:26}];
 requests[1](newest);assert.deepEqual(await second,newest);
 requests[0](older);assert.deepEqual(await first,older);assert.deepEqual(await same,older);
 assert.deepEqual(ctx.EPISODES,newest); // late responses cannot overwrite the current iteration
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    subprocess.run([NODE, '-e', script, str(PAGE)], check=True, capture_output=True, text=True)


@pytest.mark.skipif(NODE is None, reason='Node.js is needed to exercise dashboard JavaScript')
def test_start_keeps_selected_levels_while_the_new_run_has_no_checkpoint():
    script = r"""
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync(process.argv[1],'utf8');
const handler=html.slice(html.indexOf("$('start').onclick=async()=>{"),html.indexOf('// The charts, for the active run'));
const els={start:{},task:{value:'hunter'},'from-run':{value:'run67'},'from-iter':{value:'40'},'next-msg':{}};
let submitted;
const ctx={$:id=>els[id],EDITS:{levels:[25,26]},FOLLOW:false,
 checkpointName:n=>`iter${String(n).padStart(4,'0')}`,
 async post(path,body){submitted=structuredClone(body);return {run:'run68',started_from:'run67/iter0040',changes:[{setting:'levels'}]}},
 async loadRuns(){},async loadStatus(){},
 fillFrom(){if(!els['from-run'].value){els['from-run'].value='run67';ctx.EDITS={}}}};
vm.createContext(ctx);vm.runInContext(handler,ctx);
els.start.onclick().then(()=>{
 assert.deepEqual(submitted.changes.levels,[25,26]);
 assert.deepEqual(ctx.EDITS.levels,[25,26], 'Starting must preserve the submitted levels, not reload run67 levels');
 assert.equal(els['from-run'].value,'run67');
}).catch(e=>{console.error(e);process.exitCode=1});
"""
    subprocess.run([NODE, '-e', script, str(PAGE)], check=True, capture_output=True, text=True)


@pytest.mark.skipif(NODE is None, reason='Node.js is needed to exercise dashboard JavaScript')
def test_enemy_hit_points_convert_to_the_existing_training_scale():
    script = r"""
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync(process.argv[1],'utf8');
const typed=html.slice(html.indexOf('function typed(s,raw){'),html.indexOf('function edited(s)'));
const ctx={};vm.createContext(ctx);vm.runInContext(typed,ctx);
assert.equal(ctx.typed({kind:'float',display_scale:3.5},'7'),2);
assert.equal(ctx.typed({kind:'float',display_scale:3.5},'3.5'),1);
assert.equal(ctx.typed({kind:'float',display_scale:3.5},'0'),0);
assert.equal(ctx.typed({kind:'float'},'0.97'),0.97);
"""
    subprocess.run([NODE, '-e', script, str(PAGE)], check=True, capture_output=True, text=True)


@pytest.mark.skipif(NODE is None, reason='Node.js is needed to exercise dashboard JavaScript')
def test_fresh_team_uses_task_defaults_and_submits_edited_settings():
    script = r"""
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync(process.argv[1],'utf8');
const fresh=html.slice(html.indexOf('async function fromChanged()'),html.indexOf('const same='));
const start=html.slice(html.indexOf("$('start').onclick=async()=>{"),html.indexOf('// The charts, for the active run'));
const els={start:{},task:{value:'wallcrawler_team'},'from-run':{value:'new'},'from-iter':{value:''},'next-msg':{}};
let submitted;
const ctx={$:id=>els[id],BASE:{},EDITS:{levels:[25]},FOLLOW:false,
 SCHEMA:{settings:[{dest:'horizon',default:90},{dest:'workers',default:8},{dest:'episodes',default:96}],tasks:[{key:'wallcrawler_team',defaults:{horizon:60,workers:4}}]},
 fillIters(){},renderForm(){},renderStart(){},checkpointName(){throw Error('No checkpoint for fresh weights')},
 async api(){throw Error('Fresh weights must not load a source run')},
 async post(path,body){submitted=structuredClone(body);return {run:'run1',started_from:'random',changes:[]}},
 async loadRuns(){},async loadStatus(){}};
vm.createContext(ctx);vm.runInContext(fresh+start,ctx);
(async()=>{
 await ctx.fromChanged();
 assert.equal(ctx.BASE.horizon.value,60);assert.equal(ctx.BASE.workers.value,4);
 assert.equal(ctx.BASE.task.value,'wallcrawler_team');assert.equal(Object.keys(ctx.EDITS).length,0);
 ctx.EDITS={episodes:8};await els.start.onclick();
 assert.equal(submitted.from,'new');assert.equal(submitted.changes.task,'wallcrawler_team');
 assert.equal(submitted.changes.episodes,8);
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    subprocess.run([NODE,'-e',script,str(PAGE)],check=True,capture_output=True,text=True)


@pytest.mark.skipif(NODE is None, reason='Node.js is needed to exercise dashboard JavaScript')
def test_current_creature_defaults_and_replay_filter():
    script = r"""
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync(process.argv[1],'utf8');
const helpers=html.slice(html.indexOf('let DEFAULT_RUN='),html.indexOf('async function api('));
const els={'task':{value:'hunter'},'fresh-team':{},'from-run':{value:'run1'}};
const ctx={$:id=>els[id],LATEST_WAIT:null,setTimeout(){return 1},clearTimeout(){},STATUS:{run:'run2'},SCHEMA:{tasks:[]},
 RUNS:[{name:'run1',replayable:true,checkpoints:['iter0000']},
 {name:'run2',task:'wallcrawler_team',replayable:true,checkpoints:['iter0000']}],
 fillFrom(){},fillReplay(){}};
vm.createContext(ctx);vm.runInContext(helpers,ctx);
ctx.syncCreature();assert.equal(els.task.value,'wallcrawler_team');
assert.deepEqual(Array.from(ctx.replayRuns(),r=>r.name),['run2']);
els.task.value='hunter';ctx.syncCreature();assert.equal(els.task.value,'hunter');
ctx.STATUS.run='run1';ctx.syncCreature();assert.equal(els.task.value,'hunter');
assert.deepEqual(Array.from(ctx.replayRuns(),r=>r.name),['run1']);
"""
    subprocess.run([NODE, '-e', script, str(PAGE)], check=True, capture_output=True, text=True)


@pytest.mark.skipif(NODE is None, reason='Node.js is needed to exercise dashboard JavaScript')
@pytest.mark.parametrize('bonus', [0, .01])
def test_crawler_rules_show_reward_and_penalty_cards_from_recorded_run(bonus):
    script = r"""
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync(process.argv[1],'utf8'),bonus=+process.argv[2];
const code=html.slice(html.indexOf('async function loadRules(){'),html.indexOf('async function refresh(){'));
const rules={innerHTML:''};
const config={task:'wallcrawler_team',args:{episodes:8},manifest:{horizon:60,
 rewards:{team_hit:2,shot:-.02,...(bonus?{predicted_shot_accuracy:bonus}:{})}}};
const ctx={VIEW:'run92',EPI:0,$:()=>rules,document:{getElementById:()=>rules},
 fetch:async()=>({ok:true,json:async()=>config}),render(){},esc:x=>String(x)};
vm.createContext(ctx);vm.runInContext(code,ctx);
ctx.loadRules().then(()=>{
 assert.match(rules.innerHTML,/Active rewards/);assert.match(rules.innerHTML,/Active penalties/);
 assert.match(rules.innerHTML,/Accepted projectile hit/);assert.match(rules.innerHTML,/>\+2</);
 assert.match(rules.innerHTML,/Actual shot/);assert.match(rules.innerHTML,/0.02/);
 assert.equal(rules.innerHTML.includes('Predicted shot accuracy'),bonus>0);
}).catch(e=>{console.error(e);process.exitCode=1});
"""
    subprocess.run([NODE, '-e', script, str(PAGE), str(bonus)], check=True, capture_output=True, text=True)


@pytest.mark.skipif(NODE is None, reason='Node.js is needed to exercise dashboard JavaScript')
def test_chart_start_filters_all_statistics_and_smoothing_and_is_saved_per_run():
    script = r"""
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync(process.argv[1],'utf8');
const code=html.slice(html.indexOf('let D=[],'),html.indexOf('async function loadRules(){'));
const els=Object.fromEntries(['chart-start','chart-range','charts','strip'].map(id=>[id,{value:'',innerHTML:'',textContent:''}]));
const storage=new Map();
const ctx={$:id=>els[id],VIEW:'run1',document:{getElementById:id=>els[id]},
 getComputedStyle:()=>({getPropertyValue:()=> '#888'}),localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)}};
vm.createContext(ctx);vm.runInContext(code,ctx);
vm.runInContext("D=[{iteration:0,mean_return:-999,rollout_s:1},{iteration:100,mean_return:10,rollout_s:1},{iteration:101,mean_return:20,rollout_s:1}]",ctx);
ctx.setChartStart(100);
assert.equal(els['chart-start'].value,'100');
assert.match(els.strip.innerHTML,/>15.0</);assert.doesNotMatch(els.charts.innerHTML,/-999/);
assert.equal(ctx.chartData().length,2);assert.equal(ctx.savedChartStart('run1'),100);
assert.equal(ctx.savedChartStart('run2'),0);
const chart=ctx.chart({title:'test',sub:'',key:'mean_return'});
assert.match(chart,/M44.0 /); // first included iteration starts at the left edge
ctx.setChartStart(1000);assert.equal(ctx.chartData().length,0);
assert.match(els['chart-range'].textContent,/No data from iteration 1000/);
assert.match(els.charts.innerHTML,/No iterations in the selected range/);
ctx.setChartStart(0);assert.equal(ctx.chartData().length,3);
ctx.setChartStart(-5);assert.equal(els['chart-start'].value,'0');
ctx.setChartStart('invalid');assert.equal(els['chart-start'].value,'0');
"""
    subprocess.run([NODE, '-e', script, str(PAGE)], check=True, capture_output=True, text=True)


@pytest.mark.skipif(NODE is None, reason='Node.js is needed to exercise dashboard JavaScript')
def test_latest_replay_waits_for_current_run_instead_of_opening_old_rules():
    script=r"""
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync(process.argv[1],'utf8');
const handler=html.slice(html.indexOf("$('rp-latest').onclick=async()=>{"),html.indexOf("$('rp-run').onchange="));
const els=Object.fromEntries(['rp-latest','rp-msg','rp-level'].map(id=>[id,{value:'',textContent:''}]));
const old={name:'run1',task:'wallcrawler_team',replayable:true,checkpoints:['iter0000']};
const ctx={$:id=>els[id],LATEST_WAIT:null,setTimeout(){return 1},clearTimeout(){},STATUS:{run:'run2'},RUNS:[old,{name:'run2',task:'wallcrawler_team',replayable:true,checkpoints:[]}],
 currentTask(){return 'wallcrawler_team'},async loadStatus(){},async loadRuns(){},replayRuns(){return [old]},
 async loadEpisodes(){throw Error('Must not open the old run')},async watchEpisode(){throw Error('Must not launch')}};
vm.createContext(ctx);vm.runInContext(handler,ctx);
els['rp-latest'].onclick().then(()=>assert.match(els['rp-msg'].textContent,/run2.*first episode/)).catch(e=>{console.error(e);process.exitCode=1});
"""
    subprocess.run([NODE,'-e',script,str(PAGE)],check=True,capture_output=True,text=True)


@pytest.mark.skipif(NODE is None, reason='Node.js is needed to exercise dashboard JavaScript')
def test_latest_replay_queue_opens_when_first_iteration_arrives():
    script=r"""
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync(process.argv[1],'utf8');
const handler=html.slice(html.indexOf("$('rp-latest').onclick=async()=>{"),html.indexOf("$('rp-run').onchange="));
const els=Object.fromEntries(['rp-latest','rp-msg','rp-level','rp-run','rp-iter'].map(id=>[id,{value:'',textContent:''}]));
let retry,watched=null;
const run={name:'run2',task:'wallcrawler_team',replayable:true,checkpoints:[]};
const ctx={$:id=>els[id],LATEST_WAIT:null,STATUS:{run:'run2'},RUNS:[run],currentTask(){return 'wallcrawler_team'},
 async loadStatus(){},async loadRuns(){},replayRuns(){return [run]},setTimeout(fn){retry=fn;return 42},clearTimeout(){},
 fillReplay(){},renderEpisodes(){},async loadEpisodes(){return [{episode:11,level:23}]},async watchEpisode(n){watched=n}};
vm.createContext(ctx);vm.runInContext(handler,ctx);
(async()=>{await els['rp-latest'].onclick();assert.equal(watched,null);assert.match(els['rp-msg'].textContent,/automatically/);
 run.checkpoints=['iter0000'];await retry();assert.equal(watched,11);assert.equal(ctx.LATEST_WAIT,null);
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    subprocess.run([NODE,'-e',script,str(PAGE)],check=True,capture_output=True,text=True)


# The charts area and stat strip drawn by render() from the real /api/tasks layouts, read back as
# (section headings, (title, subtitle) per chart, (label, value) per strip cell).
RENDER = r"""
const fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync(process.argv[1],'utf8');
const given=JSON.parse(fs.readFileSync(0,'utf8'));
const code=html.slice(html.indexOf('let D=[],'),html.indexOf('async function loadRules(){'));
const els=Object.fromEntries(['chart-start','chart-range','charts','strip'].map(id=>[id,{value:'',innerHTML:'',textContent:''}]));
const ctx={$:id=>els[id],VIEW:'run1',document:{getElementById:id=>els[id]},given,
 getComputedStyle:()=>({getPropertyValue:()=>'#888'}),localStorage:{getItem(){},setItem(){}}};
vm.createContext(ctx);vm.runInContext(code,ctx);
vm.runInContext('LAYOUTS=given.layouts;VIEW_TASK=given.task;D=given.rows;render()',ctx);
const all=(re,s)=>[...s.matchAll(re)].map(m=>m.slice(1));
const charts=els.charts.innerHTML;
console.log(JSON.stringify({sections:all(/<h3[^>]*>(.*?)<\/h3>/g,charts).map(m=>m[0]),
 charts:all(/<h2>(.*?)<\/h2><p>(.*?)<\/p>/g,charts),strip:all(/<span>(.*?)<\/span><b>(.*?)<\/b>/g,els.strip.innerHTML),
 text:charts.replace(/<[^>]*>/g,' ')}));
"""
FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'dashboard'


def render(task, rows):
    import json
    from learning import dashboard
    given = json.dumps(dict(layouts=dashboard.resolve_all(), task=task, rows=rows))
    out = subprocess.run([NODE, '-e', RENDER, str(PAGE)], input=given, check=True, capture_output=True, text=True)
    return json.loads(out.stdout)


def log_rows(name, n=3, **extra):
    """n rows carrying every numeric key a recorded run of this task logged."""
    import json
    keys = json.loads((FIXTURES / f'{name}_log_keys.json').read_text())['keys']
    return [{**{k: 1.23456 for k in keys}, 'iteration': i, **extra} for i in range(n)]


@pytest.mark.skipif(NODE is None, reason='Node.js is needed to exercise dashboard JavaScript')
def test_render_draws_only_the_task_layout_charts():
    from learning import dashboard
    import json
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


@pytest.mark.skipif(NODE is None, reason='Node.js is needed to exercise dashboard JavaScript')
@pytest.mark.parametrize('task, log', [('hunter', 'hunter'), ('wallcrawler_team', 'crawler')])
def test_hunter_and_wallcrawler_pages_draw_the_same_charts_and_strip_as_before(task, log):
    import json
    keys = set(json.loads((FIXTURES / f'{log}_log_keys.json').read_text())['keys'])
    old = json.loads((FIXTURES / 'old_page_charts.json').read_text())
    page = render(task, log_rows(log))
    assert page['charts'] == [[c['title'], c['sub']] for c in old if c['key'] in keys]   # and nothing under Other
    assert page['strip'] == OLD_STRIPS[log]


@pytest.mark.skipif(NODE is None, reason='Node.js is needed to exercise dashboard JavaScript')
def test_render_puts_undeclared_numeric_keys_in_other_and_never_strings_or_booleans():
    page = render('hunter', log_rows('hunter', brand_new_rate=.5, checkpoint_name='iter0001.npz', gate_open=False))
    assert page['sections'][-1] == 'Other'
    assert page['charts'][-1] == ['brand_new_rate', '']
    assert 'checkpoint_name' not in page['text'] and 'gate_open' not in page['text']


@pytest.mark.skipif(NODE is None, reason='Node.js is needed to exercise dashboard JavaScript')
def test_render_with_no_rows_shows_an_empty_state():
    page = render('jelly_team', [])
    assert page['charts'] == [] and 'No iterations logged yet' in page['text']
    assert ['Iterations', '0'] in page['strip']


@pytest.mark.skipif(NODE is None, reason='Node.js is needed to exercise dashboard JavaScript')
def test_unknown_task_shows_a_message_and_shared_charts_only():
    page = render('made_up_task', log_rows('hunter'))
    assert 'made_up_task' in page['text'] and 'not one this trainer knows' in page['text']
    declared = [title for title, sub in page['charts'] if sub]   # Other charts have no subtitle
    assert declared == ['Training return', 'Distance from the starting policy (KL)', 'Policy entropy']
