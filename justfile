# The full pre-push gate (what CI runs), one command. Ruff is pinned
# by the root ruff.toml; the uvx calls honor the pin regardless of
# the system ruff version.

gate: rust python
    @echo "gate: all green"

rust:
    cargo fmt --all --check
    cargo clippy --workspace --all-targets -- -D warnings
    cargo test --workspace

python:
    uvx ruff@0.15.20 check tools ds1-patch
    uvx ruff@0.15.20 format --check tools ds1-patch
    python3 -m compileall -q tools ds1-patch
    python3 tools/ovr-map/ovr-map.py --selftest
    python3 tools/exe-patch/exe-patch.py --selftest
    python3 tools/repro/repro.py --selftest
    python3 ds1-patch/scripts/apply.py --selftest
    python3 tools/gpl-disasm/scripts/global-state-sweep.py --selftest
    python3 tools/gpl-disasm/scripts/dead-trigger-sweep.py --selftest
    python3 tools/verify-install/verify-install.py --selftest
