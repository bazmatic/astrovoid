// The viewed run's reward rules panel and its task's cards, from GET /api/runs/<run>/rewards (its own config).
import {S,$} from './state.js';
import {render} from './layout.js';
import {renderRewards,renderCards} from './rewards.js';

export async function loadRules(){
  if(!S.VIEW)return;
  const asked=S.VIEW;
  try{const r=await fetch(`api/runs/${asked}/rewards`,{cache:'no-store'});if(!r.ok||asked!==S.VIEW)return;const p=await r.json();
    if(asked!==S.VIEW)return;
    if(p.episodes&&p.episodes!==S.EPI){S.EPI=p.episodes;render()}
    const open=$('rewards').querySelector?.('details')?.open??true;
    $('rewards').innerHTML=renderRewards(p,open);
    $('rules').innerHTML=renderCards(p.cards);
  }catch(e){}
}
