"""Show neural teams on a real display, optionally recording the displayed frames with ffmpeg."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import numpy as np


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run',type=Path)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--level',type=int,default=15)
    parser.add_argument('--seed',type=int,default=1000)
    parser.add_argument('--trials',type=int,default=3)
    parser.add_argument('--seconds',type=float,default=20)
    parser.add_argument('--sample',action='store_true')
    options=parser.parse_args()
    import pygame
    import config
    from learning.policy import RecurrentPolicy
    from learning.adapters.wallcrawler import SPEC
    from learning.replay import open_environment
    from rendering.fonts import get_font
    options.out.mkdir(parents=True,exist_ok=True)
    checkpoint=options.run/'best.npz'
    policy=RecurrentPolicy.load(checkpoint,SPEC)
    pygame.init();screen=pygame.display.set_mode((1352,878))
    pygame.display.set_caption('Astrovoid — neural Wallcrawler teams')
    driver=pygame.display.get_driver()
    clock=pygame.time.Clock();font=get_font(18)
    env=open_environment(options.run);env.horizon=options.seconds
    encoder=None
    if shutil.which('ffmpeg'):
        encoder=subprocess.Popen(['ffmpeg','-y','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24',
            '-s','1352x878','-r','30','-i','-','-an','-c:v','libx264','-preset','veryfast',
            '-crf','23','-pix_fmt','yuv420p',str(options.out/'neural-teams.mp4')],stdin=subprocess.PIPE)
    captured=set();counts=dict(voluntary_hops=0,attachments=0,nonzero_messages=0,walking_decisions=0)
    metrics=[];decisions={};trial=0;frame=0
    previous_pose={};max_flight_turn=0.;minimum_forward_cosine=1.
    def draw(scene):
        nonlocal frame,max_flight_turn
        for event in pygame.event.get():
            if event.type==pygame.QUIT or (event.type==pygame.KEYDOWN and event.key==pygame.K_ESCAPE):
                raise KeyboardInterrupt
        screen.fill(config.COLOR_BACKGROUND);scene.world.maze.draw(screen)
        scene.world.roster.draw(screen);scene.world.ship.draw(screen)
        for shot in scene.world.projectiles:shot.draw(screen)
        for c in scene.team.members():
            previous=previous_pose.get(c.agent_id)
            if previous and previous[0]=='returning' and c.wall_state=='returning':
                max_flight_turn=max(max_flight_turn,abs((c.angle-previous[1]+180)%360-180))
            previous_pose[c.agent_id]=(c.wall_state,c.angle)
            inbox=scene.team.inbox(c)
            for other in scene.team.members():
                if inbox.get(other.agent_id,0):
                    pygame.draw.line(screen,(65,95,105),c.get_pos(),other.get_pos(),1)
            symbol=getattr(c,'wall_message',0)
            text=f'{c.agent_id}  [{symbol}] {c.wall_state}'
            label=font.render(text,True,(250,225,150));screen.blit(label,(c.x+12,c.y-18))
        mode='sampled' if options.sample else 'greedy'
        lines=[f'NEURAL TEAM / {mode} policy / trial {trial+1} / arena {options.level}',
               f'{scene.frames/60:.1f}s   accepted hits {scene.hits}   messages are learned symbols [0–7]',
               f'Voluntary hops {counts["voluntary_hops"]}   reattachments {counts["attachments"]}']
        panel=pygame.Surface((850,86),pygame.SRCALPHA);panel.fill((12,16,25,220));screen.blit(panel,(0,0))
        for i,line in enumerate(lines):screen.blit(font.render(line,True,(240,235,215)),(10,8+25*i))
        pygame.display.flip()
        frame+=1
        if encoder and frame%2==0:encoder.stdin.write(pygame.image.tostring(screen,'RGB'))
        states={c.wall_state for c in scene.team.members()}
        if frame>30:
            for state in states-captured:
                pygame.image.save(screen,str(options.out/(state+'.png')));captured.add(state)
        clock.tick(60)
    env.render_frames=draw
    try:
        for trial in range(options.trials):
            seed=options.seed+trial
            snap=env.reset(seed,level=options.level,team_size=6)
            previous_pose.clear()
            states={i:policy.initial_state() for i in snap.observations}
            rngs={i:np.random.default_rng(np.random.SeedSequence([seed,i])) for i in states}
            while True:
                decisions={}
                before={c.agent_id:(c.wall_state,c.get_pos(),c.wall_attach_cooldown) for c in env.team.members()}
                for c in env.team.members():
                    for site in env._sites[c.agent_id]:
                        if site is not None:
                            dx,dy=site.position[0]-c.x,site.position[1]-c.y
                            cosine=(dx*math.cos(math.radians(c.angle))+dy*math.sin(math.radians(c.angle)))/math.hypot(dx,dy)
                            minimum_forward_cosine=min(minimum_forward_cosine,cosine)
                for i,x in snap.observations.items():
                    decisions[i],states[i]=policy.choose(x,states[i],snap.masks[i],not options.sample,rngs[i])
                result=env.step(decisions)
                for c in env.team.members():
                    previous=before[c.agent_id]
                    a=decisions[c.agent_id]
                    counts['nonzero_messages']+=int(a[-1]!=0)
                    counts['walking_decisions']+=int(previous[0]=='attached' and a[0]!=1)
                    counts['voluntary_hops']+=int(previous[0]=='attached' and previous[2]<=0 and a[3] and c.wall_state=='returning')
                    counts['attachments']+=int(previous[0]!='attached' and c.wall_state=='attached')
                snap=result.snapshot
                if result.terminated or result.truncated:
                    metrics.append(dict(seed=seed,**result.events));break
    except KeyboardInterrupt:
        pass
    finally:
        env.close();pygame.quit()
        if encoder:
            encoder.stdin.close();encoder.wait(timeout=60)
        (options.out/'demonstration.json').write_text(json.dumps(dict(
            display_driver=driver,
            checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
            mode='sampled' if options.sample else 'greedy',counts=counts,episodes=metrics,
            max_return_turn_degrees_per_frame=max_flight_turn,minimum_candidate_forward_cosine=minimum_forward_cosine),indent=2))


if __name__=='__main__':main()
