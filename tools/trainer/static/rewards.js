// The viewed run's reward rules (GET /api/runs/<run>/rewards) as the pinned panel beside the charts, and its task's
// cards (structured title / rows / note) above them. Both are pure: they return HTML for the payload.
import {esc} from './state.js';

const GROUPS=[['reward','Rewards'],['penalty','Penalties'],['shaping','Shaping']];
const shown=v=>v===null||v===undefined?'–':String(+v);

function rule(r,stage){
  const off=r.value===null||r.value===undefined||+r.value===0;
  const why=r.active?'':` <em>inactive · ${off?'off in this run':`not at stage ${esc(stage)}`}</em>`;
  const stages=r.stages.length?` Stage${r.stages.length>1?'s':''} ${r.stages.join(', ')}.`:'';
  const unrecorded=r.recorded?'':` <i>not recorded${r.value===null||r.value===undefined?'':` — default ${shown(r.value)}`}</i>`;
  const amount=r.kind==='penalty'?-r.value:r.value;
  const sign=amount<0?'−':r.kind==='shaping'?'':'+';
  const value=r.value===null||r.value===undefined?'–':`${sign}${shown(Math.abs(amount))}`;
  return `<li class="${esc(r.kind)}${r.active?'':' inactive'}" data-active="${r.active}"><b>${esc(value)}</b>`+
    `<span>${esc(r.title)}${why}<br><small>${esc(r.description)}${esc(stages)}${unrecorded}</small></span></li>`;
}

// open: whether the panel starts expanded (the page keeps the user's choice across refreshes).
export function renderRewards(payload,open=true){
  const rules=payload?.rules||[],stage=payload?.stage;
  const count=rules.filter(r=>r.active).length;
  const head=rules.length?`${count} of ${rules.length} active${stage!==null&&stage!==undefined?` at stage ${esc(stage)}`:''}`:'';
  const body=rules.length?GROUPS.map(([kind,title])=>{const items=rules.filter(r=>r.kind===kind);
      return items.length?`<h3>${title}</h3><ul>${items.map(r=>rule(r,stage)).join('')}</ul>`:''}).join('')
    :'<p>No reward rules are declared for this run’s task.</p>';
  return `<details class="card"${open?' open':''}><summary><h2>Reward rules</h2> <small>${head}</small></summary>${body}</details>`;
}

export function renderCards(cards){
  return (cards||[]).map(c=>`<div class="card"><h2>${esc(c.title)}</h2>`+
    (c.rows?.length?`<ul>${c.rows.map(r=>`<li><b>${esc(r.value)}</b><span>${esc(r.label)}${r.description?`<br><small>${esc(r.description)}</small>`:''}</span></li>`).join('')}</ul>`:'')+
    (c.note?`<p>${esc(c.note)}</p>`:'')+'</div>').join('');
}
