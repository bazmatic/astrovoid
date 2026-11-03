// The runs: the status strip with its Pause/Resume/Stop buttons, the run list, and which run the charts show.
import {S,$,esc,taskOf,capabilities} from './state.js';
import {api,post} from './api.js';
import {savedChartStart} from './charts.js';
import {render,withAliases} from './layout.js';
import {loadRules} from './rules.js';
import {fillFrom,renderStart} from './settings-form.js';
import {fillReplay} from './replay.js';

export async function refresh(){if(!S.VIEW)return;const asked=S.VIEW;try{const r=await fetch(`api/runs/${S.VIEW}/data`,{cache:'no-store'});if(r.ok){const n=await r.json();withAliases(n);if(asked===S.VIEW&&n.length!==S.D.length){S.D=n;render()}}}catch(e){}}
export function currentTask(){return taskOf(S.RUNS.find(r=>r.name===S.STATUS?.run)||S.RUNS.at(-1))}
export function taskLabel(key){return S.SCHEMA?.tasks.find(t=>t.key===key)?.label||key}
export function syncCreature(){
  const run=S.STATUS?.run||S.RUNS.at(-1)?.name;
  if(run===S.DEFAULT_RUN)return;
  S.DEFAULT_RUN=run;$('task').value=currentTask();
  $('fresh-team').disabled=!capabilities($('task').value).fresh_weights;
  $('from-run').value='';fillFrom();fillReplay();
}

// The status strip: what is training, with the buttons that fit its state.
export function renderStatus(){
  const s=S.STATUS;if(!s)return;
  const state=s.run?s.state:'idle',iter=s.iteration!=null?s.iteration:'-';
  const phase=(state==='training'||state==='pausing')?s.phase:null;
  const started=s.started?new Date(s.started).toLocaleString([], {weekday:'short',hour:'numeric',minute:'2-digit'}):'-';
  const facts=s.run?`<span class="facts"><b>${esc(s.run)}</b> · ${esc(taskLabel(currentTask()))} · iteration ${iter}${s.iterations?` of ${s.iterations}`:''}${state==='idle'?'':` · started ${esc(started)}`}${s.seconds_per_iteration&&(state==='training'||state==='pausing')?` · last iteration ${s.seconds_per_iteration.toFixed(1)} s`:''}</span>`:'<span class="facts">No runs yet</span>';
  const buttons=(phase==='evaluating'||phase==='finished')?['stop']:({training:['pause','stop'],pausing:['stop'],paused:['resume','stop'],interrupted:['resume','stop'],idle:[]}[state]||[]);
  const label={pause:'Pause',resume:'Resume',stop:'Stop'};
  const note=phase==='evaluating'?'Running final evaluation; the iteration count stays fixed.':phase==='finished'?'Training finished; shutting down workers.':{pausing:'Pausing after this iteration…',paused:'Paused: resume to carry on where it stopped.',interrupted:'Interrupted (it ended without a pause or stop): resume to carry on from its last iteration.'}[state]||'';
  // The 5 s refresh only updates the numbers: rebuilding the strip would undo an armed Stop and clear a message.
  const key=`${state}|${phase}|${s.run}`;
  if(key!==S.STATUS_KEY){
    S.STATUS_KEY=key;
    $('status').innerHTML=`<span class="badge ${state}">${phase==='evaluating'?'Evaluating':phase==='finished'?'Finishing':{training:'Training',pausing:'Pausing',paused:'Paused',interrupted:'Interrupted',idle:'Idle'}[state]}</span><span id="status-facts"></span>${note?`<span class="msg">${note}</span>`:''}<span class="msg" id="status-msg"></span><span class="actions">${buttons.map(b=>`<button data-act="${b}" class="${b==='stop'?'danger':''}">${label[b]}</button>`).join('')}</span>`;
    $('status').querySelectorAll('button').forEach(b=>b.onclick=()=>act(b));
  }
  $('status-facts').outerHTML=facts.replace('<span class="facts">','<span class="facts" id="status-facts">');
  renderStart();
}
export async function act(button){
  const what=button.dataset.act;
  if(what==='stop'&&!button.classList.contains('armed')){       // Stop takes a second click
    button.classList.add('armed');button.textContent='Really stop?';
    setTimeout(()=>{if(button.isConnected){button.classList.remove('armed');button.textContent='Stop'}},5000);return}
  button.disabled=true;
  try{const body=what==='resume'?{run:S.STATUS.run}:{};
    if(what==='resume'&&Object.keys(S.EDITS).length){
      if($('from-run').value!==S.STATUS.run||$('task').value!==currentTask())throw new Error('Select the paused run as the settings source before resuming with edits.');
      body.changes={...S.EDITS};
    }
    const r=await post(`api/${what}`,body);
    if(what==='resume')S.EDITS={};
    S.STATUS_KEY=null;await loadStatus();$('status-msg').textContent={pause:`${r.run} will pause once its current iteration is saved.`,resume:`Resumed ${r.run}.`,stop:`Stopped ${r.run}.`}[what];
    await loadRuns()}
  catch(e){const m=$('status-msg');m.className='msg error';m.textContent=e.message;button.disabled=false}
}
export async function loadStatus(){try{S.STATUS=await api('api/status');syncCreature();renderStatus();if(S.FOLLOW&&S.STATUS.run&&S.STATUS.run!==S.VIEW)setView(S.STATUS.run)}catch(e){}}

// The charts, for the active run unless another one is chosen.
export async function loadRuns(){
  try{S.RUNS=await api('api/runs');syncCreature();fillFrom();fillReplay();renderStatus();
    const sel=$('view-run'),keep=S.FOLLOW?'':sel.value;
    sel.innerHTML=`<option value="">The active run</option>`+[...S.RUNS].reverse().map(r=>`<option value="${r.name}">${r.name} (${r.state}, ${r.iterations_done} iterations)</option>`).join('');
    sel.value=keep;renderStart();
    if(S.VIEW&&viewTask()!==S.VIEW_TASK){S.VIEW_TASK=viewTask();render()}}catch(e){}
}
export function viewTask(){return taskOf(S.RUNS.find(r=>r.name===S.VIEW))}
export function setView(run){if(run===S.VIEW)return;S.VIEW=run;S.VIEW_TASK=viewTask();S.D=[];S.CHART_START=savedChartStart(run);$('chart-start').value=String(S.CHART_START);$('rules').innerHTML='';$('rewards').innerHTML='';render();refresh();loadRules()}
export function initRuns(){
  $('view-run').onchange=()=>{const v=$('view-run').value;S.FOLLOW=!v;setView(v||S.STATUS?.run||null)};
}
