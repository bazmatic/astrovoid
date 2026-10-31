// The page's entry point: wires the controls, loads the layouts and settings, then polls the trainer.
import {S,$,esc} from './state.js';
import {api} from './api.js';
import {setChartStart} from './charts.js';
import {render} from './layout.js';
import {loadRules} from './rules.js';
import {initRuns,loadRuns,loadStatus,refresh} from './runs.js';
import {initSettingsForm} from './settings-form.js';
import {initReplay} from './replay.js';

export async function boot(){
  try{S.LAYOUTS=await api('api/tasks')}catch(e){}
  try{S.SCHEMA=await api('api/settings')}catch(e){}
  $('task').innerHTML=(S.LAYOUTS.length?S.LAYOUTS:S.SCHEMA?.tasks||[]).map(t=>`<option value="${t.key}">${esc(t.label)}</option>`).join('');$('fresh-team').disabled=true;
  render();
  await loadRuns();await loadStatus();
  setInterval(loadStatus,5000);setInterval(loadRuns,15000);setInterval(refresh,15000);setInterval(loadRules,60000);
}
export function start(){
  initSettingsForm();initRuns();initReplay();
  $('chart-start').onchange=()=>setChartStart($('chart-start').value);
  $('chart-all').onclick=()=>setChartStart(0);
  render();boot();matchMedia('(prefers-color-scheme: dark)').addEventListener('change',render);
}
// Loaded by the page (<script type="module">) this starts it; tests import the modules without a page.
if(typeof document!=='undefined'&&document.getElementById('charts'))start();
