#!/bin/bash
set -euo pipefail

# Level 1 gets the Jev hunter through the default schedule (game.hunterLevelInterval).
# A START_LEVEL given on the command line wins.
export START_LEVEL="${START_LEVEL:-1}"
exec "$(dirname "$0")/run.sh" "$@"
