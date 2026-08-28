# fix.ds1.noop

**Bug**: none. This is the pipeline-proof no-op fix.

**Repro**: n/a; the fix edits zero bytes.

**Cause**: n/a.

**Fix**: applies `EDITS = []` to `DSUN.EXE` and nothing else. Its
job is to prove the darkfix package shape end to end: install hash
verification, backup, `darkfix-applied.json` journal, `--verify`,
and a byte-identical `--unapply` round-trip. Roadmap Phase 6:
"prove the package shape with a no-op fix that applies and
unapplies cleanly before any real fix ships."

**Surface**: DSUN.EXE (no bytes changed)

**Verified on**: GOG 1.10 (DS1)

**Default**: on

## Details

`apply.py --selftest` exercises this fix's shape (an empty EDITS
list over a copy of the real `DSUN.EXE`, when `.games/ds1/` is
present) plus a synthetic byte-edit cycle and both refusal paths:
a tampered target (install-hash mismatch) and a wrong site
fingerprint. Every path must leave the target byte-identical or
refuse before writing.
