#!/usr/bin/env bash
# Thin wrapper around repro.py. Lets people invoke
#   ./tools/repro/repro.sh ds1-smoke
# without typing `python3`. The Python script does all the work.
set -euo pipefail
exec python3 "$(dirname "$0")/repro.py" "$@"
