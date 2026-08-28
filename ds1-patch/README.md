# darkfix — Dark Sun: Shattered Lands

Bugfix patch for *Dark Sun: Shattered Lands* (1993). Targets the
GOG release (engine version 1.10).

Part of the [OpenDS](../README.md) community toolkit. The patch
ships as `darkfix-ds1` releases; the rest of OpenDS provides the
tools used to author them.

Status: pre-release. The distribution format and applier are
built and proven (`v0.0.1`); no bug fixes shipped yet. See
[`../roadmap.md`](../roadmap.md).

## Layout

- `VERSION` — patch version (docs/versioning.md; read at runtime
  by the applier).
- `manifest.toml` — schema v1 (spec.md §4): target game, the
  canonical hashes of every file a fix touches, and the ordered
  fix list with on/off state.
- `fixes/` — one markdown writeup + one applier script per fix.
  Each fix has a stable identifier (`fix.ds1.<short-name>`).
- `scripts/apply.py` — the umbrella applier.
- `scripts/darkfix/` — the engine the applier and fix scripts
  share: byte edits, GFF chunk replacement, backup, journal.

## Player install (once v0.1.0 ships)

```sh
unzip darkfix-ds1-v0.1.0.zip
cd darkfix-ds1-v0.1.0
python3 apply.py /path/to/GOG/Dark\ Sun\ Shattered\ Lands
```

The applier refuses to run unless every touched file matches the
canonical GOG 1.10 hash, backs up originals to `darkfix-backup/`
next to them, applies the enabled fixes, and writes
`darkfix-applied.json`. To revert:
`python3 apply.py --unapply`.

Also available: `--verify` (check a patched install against its
journal), `--status`, and `--check-all` (authoring-time full
install check against `docs/source-hashes/ds1-gog-1.10.toml`).

## Testing

```sh
python3 scripts/apply.py --selftest
```

Exercises the full apply/verify/unapply cycle in temp dirs: a
synthetic byte edit, both refusal paths (tampered target, wrong
site fingerprint), and, when `.games/ds1/` is present, the
no-op fix round-tripping a copy of the real `DSUN.EXE`
byte-identically. Never touches the canonical install.

## Authoring a new fix

See [`../docs/patch-workflow.md`](../docs/patch-workflow.md).
A fix script is a small Python module next to its writeup:

```python
from darkfix.patcher import apply_bytes

# matches manifest.toml
ID = "fix.ds1.<short-name>"
# relative to the install root
TARGET = "GPLDATA.GFF"
# canonical GOG 1.10 hash
SOURCE_SHA256 = "..."
# in-place byte edits; fingerprint-checked
EDITS = [
    {"offset": 0x1234, "expect": b"\x74\x0a", "replace": b"\x75\x0a"},
]


def apply(source_path, dest_path):
    apply_bytes(source_path, dest_path, EDITS)
```

Then add the fix to `manifest.toml` under `[[fixes]]`.
Byte edits are strictly in-place (same length); chunk-level GFF
fixes go through `darkfix.patcher.apply_gff_chunk` (shells to
`gff-cat replace`).
