// The stat strip above the charts: iterations, training return, the task's strip metrics, timing and game time.
import {S} from './state.js';
import {smooth} from './charts.js';

// Game time is estimated: the log has no episode lengths, so each episode is taken as EPISODE_S seconds of play.
export const EPISODE_S=75;
export const gameTime=s=>{const h=s/3600;return h<48?`${h.toFixed(0)} h`:`${Math.floor(h/24)} d ${Math.round(h%24)} h`};
// The strip's HTML for these rows (the chosen range) under this layout; epi: episodes per iteration.
export function renderStrip(layout,D,epi=S.EPI){
  const last=D.at(-1)||{},sm=k=>{const v=smooth(D.map(d=>d[k]),25);return v.at(-1)};
  const shown=(k,n=1)=>Number.isFinite(sm(k))?sm(k).toFixed(n):'-';
  const metric=k=>layout.metrics.find(m=>m.key===k);
  return [
   ['Iterations',D.length?D.length:'0'],['Training return',D.length?shown('mean_return',1):'-'],
   ...layout.strip.filter(metric).map(k=>[metric(k).short||metric(k).title,shown(k,metric(k).digits??2)]),
   ['Last iteration (s)',D.length?((last.rollout_s||0)+(last.update_s||0)).toFixed(1):'-'],
   ['Game time',D.length?gameTime(D.length*epi*EPISODE_S):'-']].map(([a,b])=>`<div class="stat"><span>${a}</span><b>${b}</b></div>`).join('');
}
