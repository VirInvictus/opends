# Fix Format

The one specification of a darkfix patch artifact: what a fix
consists of, what the applier actually runs, and which authoring
formats feed it. This document absorbs the earlier competing
sketches (`binary-patching.md` §3.4's TOML applier, which never had
an implementation, and the `gff-tool` routing in
[`patch-workflow.md`](patch-workflow.md) §4.2, which predates the
toolkit).

## Two layers

**Authoring layer** (per surface, tool-supported):

- *GPL data fixes*: `gpl-asm --patch` applies a TOML script of
  `[[edit]]` records to one chunk (see below), addressing by
  disassembler label or curated name instead of hand-counted
  offsets.
- *EXE fixes*: authored by hand against `ndisasm -b 16` output and
  `ovr-map`'s addressing (`ovr:seg+off`, `--verify`, the
  `syms/<game>.toml` names). Phase 5.7 will give EXE edits the same
  named, fingerprint-checked surface GPL edits have; until then the
  byte offsets come from the fix's site report.

**Distribution layer** (one format, the only one `apply.py` runs):
the **darkfix fix script**, below.

## The darkfix fix script (canonical)

One Python file per fix, at `dsN-patch/fixes/NNN-<short-id>.py`,
plus a markdown writeup beside it (`NNN-<short-id>.md`: symptom,
root cause, the fix, evidence). Python 3, stdlib-only. Live
example: [`ds1-patch/fixes/000-noop.py`](../ds1-patch/fixes/000-noop.py).

```python
"""fix.ds1.<short-id>: one-line summary"""

from darkfix.patcher import apply_bytes, apply_gff_chunk

ID = "fix.ds1.<short-id>"
TARGET = "DSUN.EXE"              # or "GPLDATA.GFF", "RESOURCE.GFF", ...
SOURCE_SHA256 = "<canonical install hash of TARGET>"

EDITS = [
    # binary fix: exact-length in-place byte replacement
    {"offset": 0x1234, "expect": b"\x74\x0a", "replace": b"\x75\x0a"},
]

def apply(source_path, dest_path):
    apply_bytes(source_path, dest_path, EDITS)
```

Contract:

- `ID` matches `fix.dsN.<short-id>` and the `[[fixes]]` entry in
  the package's `manifest.toml` (spec.md §4).
- `SOURCE_SHA256` documents the canonical hash the fix targets;
  the umbrella applier (`ds1-patch/scripts/apply.py`) verifies the
  install against `manifest.toml`'s hashes before running any fix.
  The per-edit fingerprints are the second, byte-level gate.
- `EDITS` entries are `{"offset", "expect", "replace"}`: seek,
  verify `expect` byte-for-byte (refuse on mismatch:
  `FingerprintMismatch`), write `replace`. Lengths must be equal;
  **EXE edits are in-place only**; an inserted byte shifts every
  later overlay payload into garbage.
- GPL chunk fixes use `apply_gff_chunk` (chunk replacement,
  in-place if the new bytes fit, append otherwise, per the
  `gff-edit` writer policy).
- The script is journal-gated: the applier's journal
  (`darkfix-applied.json`) plus `AlreadyApplied` /
  `NotApplied` bookkeeping make re-runs and `--unapply` exact.
- The `darkfix.patcher` exception taxonomy a fix author codes
  against: `PatchError`, `HashMismatch`, `FingerprintMismatch`,
  `AlreadyApplied`, `NotApplied` (plus `ManifestError` at the
  umbrella layer).

## The authoring TOML (`gpl-asm --patch`)

Chunk-scoped, authoring-time; its output is what you paste into a
fix script's `EDITS` (offsets resolved to numbers, fingerprints
carried over):

```toml
[[edit]]
at = "label_0x0042 + 3"      # or: at = "iniya_first_meeting + 3"
bytes_old = "3a"             # fingerprint check, mandatory
bytes_new = "3b"
reason = "retarget the immediate after the label"
```

- `at` takes `"<base>"` or `"<base> + N"`; the base is a
  `label_0xNNNN` / `entry_0xNNNN` block leader or a name from
  `gpl-disasm`'s `syms/functions.toml`. The resolver requires the
  base to be a real block leader in the target chunk, so a patch
  cannot silently address the wrong chunk.
- `at_offset` (chunk-relative absolute) is the non-symbolic form;
  exactly one of `at` / `at_offset` per edit.
- `--dry-run` previews; `bytes_old` mismatch refuses the edit.

## Superseded formats

- `binary-patching.md` §3.4's TOML (`[[patch]]` with
  `offset`/`expect`/`replace` and a per-file `target_sha256`)
  described an applier that was never written; its *semantics*
  (fingerprint-gated in-place edits) are preserved exactly in the
  fix-script `EDITS` above. That section now points here.
- [`patch-workflow.md`](patch-workflow.md) §4.2's skeleton is the
  same contract; its older prose about routing GPL fixes through
  `gff-tool` (the dsun_music Java tool) is historical: GPL fixes
  use `gff-edit` + `gpl-asm`, per spec §7a.
