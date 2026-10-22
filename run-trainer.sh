#!/bin/bash
set -euo pipefail

# The training manager: no command opens it in the browser; status, runs, start, stop, pause and resume
# work from here too (./run-trainer.sh --help).
cd "$(dirname "$0")"
exec ./venv/bin/python -m tools.trainer "$@"
