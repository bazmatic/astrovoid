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
const ctx={$:id=>els[id],RUNS:[{name:'run1',replayable:true,checkpoints:['iter0000']}],
  EPISODES:[{episode:99,level:26}], // stale data from the previously viewed iteration
  fillReplay(){},renderEpisodes(){},async loadEpisodes(){return episodes},
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
const ctx={$:id=>els[id],RP_KEY:'',EPISODES:[],FLOWN:false,EPISODE_REQUEST:null,
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
