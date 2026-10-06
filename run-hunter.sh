#!/bin/bash
set -euo pipefail

# Level 1 is configured with the independent Jev hunter.
export START_LEVEL=1
exec "$(dirname "$0")/run.sh" "$@"
