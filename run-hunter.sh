#!/bin/bash
set -euo pipefail

# Level 4 is the first with the Jev hunter (game.hunterFirstLevel).
# A START_LEVEL given on the command line wins.
export START_LEVEL="${START_LEVEL:-4}"
exec "$(dirname "$0")/run.sh" "$@"
