# darkfix — Dark Sun: Shattered Lands

Bugfix patch for *Dark Sun: Shattered Lands* (1993). Targets the
GOG release (engine version 1.10).

Part of the [OpenDS](../README.md) community toolkit. The patch
ships as `darkfix-ds1` releases; the rest of OpenDS provides the
tools used to author them.

Status: pre-release. No fixes shipped yet. See
[`../roadmap.md`](../roadmap.md).

## Layout

- `manifest.toml` — patch manifest (target hashes, fix list,
  version). Created when the first fix lands.
- `fixes/` — one markdown writeup + one applier script per fix.
  Each fix has a stable identifier
  (`fix.ds1.<short-name>`).
- `scripts/apply.py` — the umbrella applier. Reads the manifest,
  applies enabled fixes, writes a backup.

## Player install (forthcoming)

Once v0.1.0 ships:

```sh
unzip darkfix-ds1-v0.1.0.zip
cd darkfix-ds1-v0.1.0
python3 apply.py /path/to/GOG/Dark\ Sun\ Shattered\ Lands
```

The script verifies your install hash, applies fixes, and
backs up touched files to `darkfix-backup/` next to them. To
revert: `python3 apply.py --unapply`.

## Authoring a new fix

See [`../docs/patch-workflow.md`](../docs/patch-workflow.md).
