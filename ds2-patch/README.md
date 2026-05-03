# darkfix — Dark Sun: Wake of the Ravager

Bugfix patch for *Dark Sun: Wake of the Ravager* (1994). Targets
the GOG release (engine version 1.10).

This is the headline patch — *Wake of the Ravager* shipped with
game-breaking bugs that even SSI's 1.02 and 1.10 patches did not
fully resolve. There has never been a public unofficial patch.
This will be the first.

Status: pre-release. No fixes shipped yet. See
[`../roadmap.md`](../roadmap.md). Headline target:
**the mines elevator freeze** ([`../docs/known-bugs.md`](../docs/known-bugs.md)
section 2.1).

## Layout

- `manifest.toml` — patch manifest (target hashes, fix list,
  version). Created when the first fix lands.
- `fixes/` — one markdown writeup + one applier script per fix.
  Each fix has a stable identifier (`fix.ds2.<short-name>`).
- `scripts/apply.py` — the umbrella applier.

## Player install (forthcoming)

Once v0.1 ships:

```sh
unzip darkfix-ds2-v0.1.zip
cd darkfix-ds2-v0.1
python3 apply.py /path/to/GOG/Dark\ Sun\ 2\ Wake\ of\ the\ Ravager
```

The script verifies your install hash, applies fixes, and
backs up touched files to `darkfix-backup/` next to them. To
revert: `python3 apply.py --unapply`.

## Notes specific to DS2

- The GOG release ships music as `MUSIC/Track02.ogg` ... `Track41.ogg`.
  We do not touch these.
- The CD image at `game.gog` is a Mode 2/2352 data track. We do
  not touch this either; the original game files we patch live
  outside it in the installer's filesystem.
- `*.FLI` cinematics are Autodesk Animator FLIC. We do not touch
  these.
- The bugfix surfaces are: `DSUN.EXE`, `GPLDATA.GFF`,
  `RESOURCE.GFF`, `OBJEX.GFF`, and the `RGN*.GFF` family.

## Authoring a new fix

See [`../docs/patch-workflow.md`](../docs/patch-workflow.md).
