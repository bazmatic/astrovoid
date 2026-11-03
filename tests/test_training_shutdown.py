"""Headless rollout workers must remain terminable after SDL initialization."""
import os
import subprocess
import sys
import pytest


@pytest.mark.skipif(sys.platform=='win32',reason='POSIX signal handling')
def test_rollout_worker_exits_on_sigterm_after_pygame_initializes():
    code='''
from learning.run import _worker_init
_worker_init()
import pygame,time
pygame.init()
print('ready',flush=True)
while True: time.sleep(.1)
'''
    env=dict(os.environ,PYGAME_HIDE_SUPPORT_PROMPT='1')
    env.pop('SDL_NO_SIGNAL_HANDLERS',None)
    child=subprocess.Popen([sys.executable,'-c',code],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
    try:
        assert child.stdout.readline().strip()=='ready'
        child.terminate()
        try:
            child.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pytest.fail('SDL swallowed SIGTERM: rollout worker did not exit')
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=5)
