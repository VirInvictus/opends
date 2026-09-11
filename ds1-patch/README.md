# darkfix — Dark Sun: Shattered Lands

Bugfix patch for *Dark Sun: Shattered Lands* (1993). Targets the
GOG release (engine version 1.10).

Part of the [OpenDS](../README.md) community toolkit. The patch
ships as `darkfix-ds1` releases; the rest of OpenDS provides the
tools used to author them.

Status: v0.1.0 ships the first real fix (`fix.ds1.deadtriggers`,
the Darkhold dead-trigger family: enemies in the endgame that
refuse to engage and look text that stops working). The
distribution format and applier were proven in `v0.0.1`. See
[`../roadmap.md`](../roadmap.md) and `fixes/` for per-fix
writeups.

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

## Installing (players)

You need [Python](https://www.python.org/downloads/) 3.11 or newer
(the Windows Store Python or the `py` launcher both work). The patch
never touches anything but the game folder you point it at.

1. Download the `darkfix-ds1-vX.Y.Z.zip` release from the
   [releases page](https://github.com/VirInvictus/opends/releases)
   and unzip it anywhere.
2. Find your game folder (GOG's default is
   `C:\GOG Games\Dark Sun\`).
3. Open a terminal in the unzipped folder and run:

   Windows (cmd/PowerShell):

   ```bat
   py apply.py "C:\GOG Games\Dark Sun"
   ```

   Linux/macOS:

   ```sh
   python3 apply.py "/path/to/GOG Games/Dark Sun"
   ```

4. Launch the game the normal way (the GOG/DOSBox shortcut). No
   launcher changes are needed.

What it does: refuses to run unless every file it touches matches
the canonical GOG 1.10 hash, backs up originals to `darkfix-backup/`
inside the game folder, applies the enabled fixes, and writes
`darkfix-applied.json` recording what was done.

To revert: `py apply.py "C:\GOG Games\Dark Sun" --unapply` restores
the originals from the backups. To re-check a patched install:
`--verify`; to see what is applied: `--status`.

If the applier refuses with a hash mismatch, the folder is not the
GOG 1.10 build this patch targets (wrong engine version, already
patched, or damaged install). Nothing was changed.

Platform proof: the full apply/status/unapply cycle is exercised on
every change by `--selftest`, and was proven 2026-09-06 under
Wine 11.0 with Windows Python 3.12.10 against a scratch copy of the
real install (applied, journaled, unapplied byte-identically). The
applier is pure stdlib; no dependencies to install.

## Testing

```sh
python3 scripts/apply.py --selftest
```

Exercises the full apply/verify/unapply cycle in temp dirs: a
synthetic byte edit, both refusal paths (tampered target, wrong
site fingerprint), and, when `.games/ds1/` is present, the
no-op fix round-tripping a copy of the real `DSUN.EXE`
byte-identically plus the shipped fix set applied to copies of
every file the manifest touches (the deadtriggers cycle pins the
patched `GPLDATA.GFF` hash). Never touches the canonical install.

## Authoring a new fix

See [`../docs/patch-workflow.md`](../docs/patch-workflow.md)
and the cookbook skeleton
[`../docs/cookbook/author-first-darkfix.md`](../docs/cookbook/author-first-darkfix.md).
Authoring-time full-install hash check: `--check-all` (uses
`docs/source-hashes/ds1-gog-1.10.toml`; a distributed zip does not
ship docs/, so players never need it).
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
