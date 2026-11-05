"""Start a built game and check that it stays up: `python tools/smoke_build.py PATH_TO_EXECUTABLE [SECONDS]`.

Runs headless (SDL dummy drivers), so it works on a build machine with no display. A game that crashes on start,
which is what a bundle missing a module does, fails here instead of in a player's hands.
"""
import os
import subprocess
import sys
import time


def main(argv):
    if not 2 <= len(argv) <= 3:
        print(__doc__)
        return 2
    seconds = float(argv[2]) if len(argv) == 3 else 10.
    env = dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
    process = subprocess.Popen([argv[1]], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    deadline = time.monotonic()+seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            print(process.stdout.read())
            print(f'FAILED: the game exited with code {process.returncode} within {seconds:g} s')
            return 1
        time.sleep(.25)
    process.terminate()
    try:
        process.wait(10)
    except subprocess.TimeoutExpired:
        process.kill()
    print(f'OK: the game was still running after {seconds:g} s')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
