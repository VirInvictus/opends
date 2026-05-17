#!/usr/bin/env bash
# Thin wrapper around opcode-fuzz.py. Lets people invoke
#   ./tools/opcode-fuzz/opcode-fuzz.sh roundtrip <gff>
# without typing `python3`. The Python script does all the
# work.
set -euo pipefail
exec python3 "$(dirname "$0")/opcode-fuzz.py" "$@"
