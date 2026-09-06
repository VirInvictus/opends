# darkfix — Dark Sun: Wake of the Ravager

Bugfix patch for *Dark Sun: Wake of the Ravager* (1994). Targets
the GOG release (engine version 1.10).

Part of the [OpenDS](../README.md) community toolkit. The patch
ships as `darkfix-ds2` releases; the rest of OpenDS provides the
tools used to author them.

This is the headline patch — *Wake of the Ravager* shipped with
game-breaking bugs that even SSI's 1.02 and 1.10 patches did not
fully resolve. There has never been a public unofficial patch.
This will be the first.

Status: pre-release. No fixes shipped yet. See
[`../roadmap.md`](../roadmap.md). Headline target:
**the mines elevator freeze** ([`../docs/known-bugs.md`](../docs/known-bugs.md)
section 2.1).

The applier machinery is proven on the DS1 side
([`../ds1-patch/`](../ds1-patch/) v0.0.1: manifest schema,
`apply.py`, the `darkfix` engine, no-op round-trip). The scripts
below get populated from that proven shape when Phase 7 starts;
decide then whether `scripts/darkfix/` is promoted to shared
tooling or copied per patch.

## Layout

- `VERSION` — patch version (docs/versioning.md; single source
  for the release tooling). 0.0.1 = pre-release, nothing
  shipped.
- `manifest.toml` — schema v1 (spec.md §4): target game and the
  canonical `DSUN.EXE` hash. The fix list is empty until the
  first fix lands.
- `fixes/` — one markdown writeup + one applier script per fix.
  Each fix has a stable identifier (`fix.ds2.<short-name>`).
- `scripts/apply.py` — the umbrella applier.

## Player install (forthcoming)

The mechanics are identical to
[`darkfix-ds1`](../ds1-patch/README.md); read its full
player-facing install walkthrough (Windows-first `py` steps,
what gets backed up, how to revert and verify). Summary: unzip
the release, run `py apply.py "C:\GOG Games\Dark Sun 2"` from
the unzipped folder, and launch the game normally. The applier
verifies your install hash, backs up touched files to
`darkfix-backup/`, applies the enabled fixes, and journals;
`--unapply` reverts. No fix ships yet, so there is nothing to
install today.

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

See [`../docs/patch-workflow.md`](../docs/patch-workflow.md),
the cookbook
([`../docs/cookbook/author-first-darkfix.md`](../docs/cookbook/author-first-darkfix.md)),
and `tools/exe-patch` for the EXE-surface authoring gate.
