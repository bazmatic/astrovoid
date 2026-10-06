#!/bin/bash
set -euo pipefail

# Navigate to script directory
cd "$(dirname "$0")"

# An explicitly supplied environment key takes precedence over local setup.
# Read the key as data, not as executable shell configuration.
key_file=".astrovoid-local/typesafe-api-key"
if [[ -z "${TYPESAFE_API_KEY:-}" && -f "$key_file" ]]; then
    IFS= read -r TYPESAFE_API_KEY < "$key_file"
    export TYPESAFE_API_KEY
fi

exec venv/bin/python main.py "$@"
