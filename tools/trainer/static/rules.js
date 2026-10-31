// The viewed run's reward and penalty cards and its episode description, from its recorded config.
import {S,esc,fmtLevels} from './state.js';
import {render} from './layout.js';

export async function loadRules(){
  if(!S.VIEW)return;
  try{const r=await fetch(`api/runs/${S.VIEW}/config`,{cache:'no-store'});if(!r.ok)return;const c=await r.json();
    const team=c.task==='wallcrawler_team';
    let rows=c.rewards||[];
    if(team){
      const rewards=c.manifest?.rewards||c.shaping||{};
      rows=[
        {name:'Accepted projectile hit',sign:'+',value:rewards.team_hit,unit:c.manifest?.reward_scope==='individual'?'Reward only for the crawler whose bullet hit':'Shared team reward for a genuine accepted bullet hit'},
        {name:'Actual shot',sign:'-',value:Math.abs(rewards.shot||0),unit:'Cost for each shot actually fired'}
      ];
      if(rewards.successful_landing&&!c.manifest?.battle_rewards)rows.push({name:'Successful landing',sign:'+',value:rewards.successful_landing,unit:'Combat trials only in current runs; aiming drills earn no landing bonus. Once per completed voluntary jump to the landing crawler.'});
      const battle=c.manifest?.battle_rewards;
      if(battle)rows.push(
        {name:'Battle time alive',sign:'+',value:battle.alive_per_second,unit:'Per living crawler per second'},
        {name:'Battle survived',sign:'+',value:battle.survival_bonus,unit:'Per crawler alive at terminal battle success: time limit or hunter-free Jelly clear'},
        {name:'Crawler killed',sign:'-',value:battle.death_cost,unit:'Once per death in battle'},
        {name:'Jelly destroyed',sign:'+',value:battle.jelly_kill,unit:'To the shooter, in addition to hit rewards'});
      if(rewards.trial_completion)rows.push({name:'Aiming trial cleared',sign:'+',value:rewards.trial_completion,unit:'Once per successful clear, shared equally by living crawlers. No bonus for timeout or team death.'});
      if(rewards.jump_proximity)rows.push({name:'Jump near enemy',sign:'+',value:rewards.jump_proximity,unit:`Pursuit trials: per actual launch, scales from zero at ${c.manifest.jump_proximity.range_pixels}px body clearance to this maximum at contact; nearest visible enemy only; reward goes to jumper only.`});
      if(rewards.contact_hit)rows.push({name:'Struck by Jellyfish',sign:'-',value:Math.abs(rewards.contact_hit),unit:'Cost to the struck crawler only; shared contact cooldown prevents repeated overlap charges'});
      if(rewards.bullet_hit)rows.push({name:'Struck by bullet',sign:'-',value:Math.abs(rewards.bullet_hit),unit:'Cost to the struck crawler only, once per damaging bullet impact'});
      if(rewards.walk_reversal)rows.push({name:'Walking reversal',sign:'-',value:Math.abs(rewards.walk_reversal),unit:'Cost per actual attached walking reversal; stopping does not reset direction history'});
      if(rewards.voluntary_jump)rows.push({name:'Voluntary jump',sign:'-',value:Math.abs(rewards.voluntary_jump),unit:c.manifest?.curriculum?`Shooting trials: ${Math.abs(rewards.voluntary_jump)}; dodge trials: ${c.manifest.curriculum.dodge_jump_cost}; pursuit trials: ${c.manifest.jump_proximity?.pursuit_jump_cost??c.manifest.curriculum.dodge_jump_cost}. Damage-induced detachment excluded.`:'Cost per actual voluntary launch; damage-induced detachment is excluded'});
      if(rewards.predicted_shot_accuracy)rows.push({name:'Predicted shot accuracy',sign:'+',
        value:rewards.predicted_shot_accuracy,unit:'Up to this amount per shot for predicted interception quality; blocked paths excluded. This is not a measured hit.'});
    }
    if(!rows.length)return;
    const list=(sign,cls)=>rows.filter(x=>x.sign===sign).map(x=>`<li class="${cls}"><b>${sign==='-'?'&minus;':'+'}${+x.value}</b><span>${x.name}<br><small>${x.unit}</small></span></li>`).join('');
    const e=c.episode||{};
    const episodes=team?c.args?.episodes:e.episodes_per_iteration;
    if(episodes&&episodes!==S.EPI){S.EPI=episodes;render()}
    const teacherNote=c.manifest?.jump_teacher?` Bootstrap teacher: pre-contact escape demonstrations train aiming, firing, detachment and legal landing selection; PPO episodes use the learned policy${c.manifest.jump_teacher.rehearsal_weight?` with jump/landing rehearsal (weight ${c.manifest.jump_teacher.rehearsal_weight})`:``}. `:'';
    const teamEpisode=team?`<div class="card"><h2>Episodes</h2><p>Up to ${c.manifest?.horizon??e.horizon_seconds} seconds or until all crawlers die${c.manifest?.practice_targets?.dies_on_hit?' or every target is hit':''}. ${episodes} episodes per iteration.${teacherNote} ${c.manifest?.pursuers?`Jellyfish pursuit curriculum: ${Math.round((1-c.manifest.curriculum.shooting_share)*100)}% pursuit trials (${c.manifest.pursuers.count} allied Jellyfish${c.manifest.pursuers.health?`, ${c.manifest.pursuers.health} HP each`:``}; ${c.manifest.pursuers.contact_damage} HP contact damage; speed ${c.manifest.pursuers.speed} px/frame), ${Math.round(c.manifest.curriculum.shooting_share*100)}% shooting trials. Two crawlers until paired evaluation supports progression. `:c.manifest?.curriculum?`Dodge and reposition curriculum: ${Math.round((1-c.manifest.curriculum.shooting_share)*100)}% dodge trials (${c.manifest.curriculum.dodge_targets} targets, ${c.manifest.curriculum.burst_size}-shot aimed bursts), ${Math.round(c.manifest.curriculum.shooting_share*100)}% shooting trials. Two crawlers until paired evaluation supports progression. `:''} ${c.manifest?.ships_fire===false?'Opponent ships do not fire. ':''}${c.manifest?.aiming_practice?`Aiming practice: ${c.manifest.practice_walking?'walking enabled':'walking disabled'}; voluntary jumping ${c.manifest.practice_jumping?'enabled':'disabled'}.${c.manifest.practice_fire_interval_frames?` Reload time: ${c.manifest.practice_fire_interval_frames/60} seconds.`:''} `:''}${c.manifest?.practice_targets?`Up to ${c.manifest.practice_targets.count} practice targets.${c.manifest.practice_targets.return_fire?` Slow return fire every ${c.manifest.practice_targets.return_fire.interval_frames/60} seconds.`:''} `:'Frozen neural opponents; '}No pickups or passive power drain. ${c.manifest?.reward_scope==='individual'?'Individual rewards: each crawler receives only its own hits and costs.':'Rewards are shared by the crawler team.'}</p></div>`:'';
    document.getElementById('rules').innerHTML=
     `<div class="card gain"><h2>Active rewards</h2><ul>${list('+','gain')}</ul></div>`+
     `<div class="card cost"><h2>Active penalties</h2><ul>${list('-','cost')}</ul></div>`+
     (team?teamEpisode:`<div class="card"><h2>Episodes</h2><p>Up to ${e.horizon_seconds} s of fighting, then up to ${e.after_clear_seconds} s more to collect powerups once the last enemy is dead. ${e.episodes_per_iteration} episodes per iteration.${e.health?` The hunter survives ${e.health} energy: each enemy hit costs 1, and a wall takes up to ${e.wall_energy} for a full-speed crash (less for a gentler one). The episode ends if it is destroyed.`:''}${e.levels?.length?` Levels: ${esc(fmtLevels(e.levels))}.`:''}</p></div>`);
  }catch(e){}
}
