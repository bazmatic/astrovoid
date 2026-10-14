#!/usr/bin/env bash
# Install a trained checkpoint as the game's neural pilot (assets/neural/hunter.npz).
#
#   tools/install_pilot.sh            the latest checkpoint of the newest run
#   tools/install_pilot.sh PATH.npz   that checkpoint
#
# While training is running, the newest file may still be being written, so the one before it is used.
# The file must load as a policy before it replaces the pilot; the pilot it replaces is kept in
# .astrovoid-local/neural/hunter.previous.npz. Restart the game afterwards: it reads the pilot at launch.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RL="$ROOT/.astrovoid-local/neural/rl"
TARGET="$ROOT/assets/neural/hunter.npz"
PREVIOUS="$ROOT/.astrovoid-local/neural/hunter.previous.npz"

if [ $# -ge 1 ]; then
    SOURCE="$1"
else
    SOURCE=""
    for run in $(ls -d "$RL"/run*/ 2>/dev/null | sort -V -r); do
        files=( $(ls "$run"iter[0-9]*.npz 2>/dev/null | sort -V) )
        [ ${#files[@]} -eq 0 ] && continue
        if [ ${#files[@]} -ge 2 ] && pgrep -f tools.ppo_neural > /dev/null; then
            SOURCE="${files[${#files[@]}-2]}"      # training is live: skip the newest, it may be mid-write
        else
            SOURCE="${files[${#files[@]}-1]}"
        fi
        break
    done
    [ -n "$SOURCE" ] || { echo "no checkpoints found under $RL" >&2; exit 1; }
fi
[ -f "$SOURCE" ] || { echo "not a file: $SOURCE" >&2; exit 1; }

"$ROOT/venv/bin/python" -c "
import sys
from hunter.neural.policy import NeuralPolicy
NeuralPolicy.load(sys.argv[1])" "$SOURCE" || { echo "$SOURCE does not load as a policy; nothing changed" >&2; exit 1; }

mkdir -p "$(dirname "$PREVIOUS")"
[ -f "$TARGET" ] && cp "$TARGET" "$PREVIOUS"
cp "$SOURCE" "$TARGET"
echo "installed ${SOURCE#"$ROOT"/} -> assets/neural/hunter.npz (previous pilot kept in ${PREVIOUS#"$ROOT"/})"
