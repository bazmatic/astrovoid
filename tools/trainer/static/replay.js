// Replays: an iteration's episodes, optionally flown again to see how each went, each one watchable.
import {S,$,taskOf,esc} from './state.js';
import {post} from './api.js';
import {currentTask,loadRuns,loadStatus} from './runs.js';
import {setIters,snapIter} from './settings-form.js';

export function replayRuns(){return S.RUNS.filter(r=>r.replayable&&r.checkpoints.length&&taskOf(r)===currentTask())}
export function fillReplay(){
  const sel=$('rp-run'),keep=sel.value,usable=replayRuns().reverse();
  sel.innerHTML=usable.map(r=>`<option value="${r.name}">${r.name}</option>`).join('');
  if(keep&&usable.some(r=>r.name===keep))sel.value=keep;
  const run=S.RUNS.find(r=>r.name===sel.value);
  setIters($('rp-iter'),$('rp-range'),run?run.checkpoints:[]);
  loadEpisodes();
}
// The chosen iteration's episodes. Asking again for the same iteration shares the pending request; a late answer
// for an iteration no longer chosen is returned to its caller but not shown.
export async function loadEpisodes(){
  const run=$('rp-run').value,iteration=$('rp-iter').value,key=`${run}/${iteration}`;
  if(!run||iteration===''){S.RP_KEY='';S.EPISODES=[];fillLevels();renderEpisodes();return [];}
  if(key===S.RP_KEY)return S.EPISODE_REQUEST;
  S.RP_KEY=key;S.EPISODES=[];renderEpisodes();
  S.EPISODE_REQUEST=(async()=>{
    try{const e=await post('api/episodes',{run,iteration:+iteration});if(S.RP_KEY===key){S.EPISODES=e;fillLevels();renderEpisodes()}return e}
    catch(e){if(S.RP_KEY===key){S.RP_KEY='';$('rp-msg').className='msg error';$('rp-msg').textContent=e.message==='not found'?'This training manager is older than the page: close it (ctrl-c) and run ./run-trainer.sh again.':e.message}return null}
  })();
  return S.EPISODE_REQUEST;
}
function fillLevels(){
  const sel=$('rp-level'),keep=sel.value,levels=[...new Set(S.EPISODES.map(e=>e.level))].sort((a,b)=>a-b);
  sel.innerHTML='<option value="">All</option>'+levels.map(l=>`<option value="${l}">${l}</option>`).join('');
  if(levels.includes(+keep))sel.value=keep;
}
export function renderEpisodes(){
  const list=$('rp-list'),level=$('rp-level').value;
  let rows=S.EPISODES.filter(e=>level===''||e.level===+level);
  list.hidden=!S.EPISODES.length;
  list.innerHTML=`<table><thead><tr><th>Episode</th><th>Level</th><th>Stage</th><th></th></tr></thead><tbody>${rows.map(e=>
    `<tr><td>${e.episode}</td><td>${e.level}</td><td>${e.lesson?esc(e.lesson):e.practice_stage==='pursuit'?'Jellyfish pursuit':e.practice_stage==='dodge'?'Dodge / reposition':e.practice_stage==='shooting'?'Shooting':'—'}</td><td><button data-ep="${e.episode}">Watch</button></td></tr>`).join('')}</tbody></table>`;
  list.querySelectorAll('button[data-ep]').forEach(b=>b.onclick=()=>watchEpisode(+b.dataset.ep));
}
export async function watchEpisode(episode){
  const m=$('rp-msg'),speed=+$('rp-speed').value;
  try{await post('api/replay',{run:$('rp-run').value,iteration:+$('rp-iter').value,episode,speed});
    m.className='msg';m.textContent=`Opening episode ${episode} in the game window${speed===1?'':` at ${$('rp-speed').selectedOptions[0].text.toLowerCase()} speed`} (Esc closes it).`}
  catch(e){m.className='msg error';m.textContent=e.message}
}
// "Watch the last episode": the newest run's last finished iteration, its last episode on the chosen level. While
// the active run has no episode yet it waits, retrying every 5 s; clicking again cancels the wait.
export async function watchLatest(){
  const button=$('rp-latest');
  if(S.LATEST_WAIT!==null){clearTimeout(S.LATEST_WAIT);S.LATEST_WAIT=null;button.textContent='Watch the last episode';$('rp-msg').textContent='Stopped waiting for an episode.';return}
  const retry=()=>{S.LATEST_WAIT=null;return watchLatest()};
  const m=$('rp-msg'),level=$('rp-level').value;
  m.className='msg';m.textContent='Checking the latest episode…';
  await loadStatus();await loadRuns();
  const active=S.RUNS.find(r=>r.name===S.STATUS?.run&&taskOf(r)===currentTask());
  if(active&&(!active.replayable||!active.checkpoints.length)){m.className='msg';m.textContent=`${active.name} is preparing its first episode. It will open automatically when ready; click again to cancel.`;button.textContent='Cancel waiting for episode';S.LATEST_WAIT=setTimeout(retry,5000);return}
  button.textContent='Watch the last episode';
  const run=active||replayRuns().at(-1);
  if(!run){m.className='msg error';m.textContent='No run can be replayed yet.';return}
  const iteration=+run.checkpoints.at(-1).slice(4);
  $('rp-run').value=run.name;$('rp-iter').value='';fillReplay();$('rp-iter').value=String(iteration);
  try{const e=await loadEpisodes();if(e===null)return;
    const matching=e.filter(e=>level===''||e.level===+level);
    if(!matching.length)throw new Error(level===''?'This iteration has no episodes.':`The newest iteration has no episodes on level ${level}. Choose All or another level.`);
    $('rp-level').value=level;renderEpisodes();
    await watchEpisode(matching.at(-1).episode)}
  catch(e){m.className='msg error';m.textContent=e.message}
}
export function initReplay(){
  $('rp-latest').onclick=watchLatest;
  $('rp-run').onchange=()=>{$('rp-iter').value='';fillReplay()};
  $('rp-iter').onchange=()=>{snapIter($('rp-iter'));loadEpisodes()};
  $('rp-last').onclick=()=>{$('rp-iter').value='';fillReplay()};
  $('rp-level').onchange=renderEpisodes;
}
