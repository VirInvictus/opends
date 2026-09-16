# darkfix for Dark Sun: Wake of the Ravager

Bugfix patch for *Dark Sun: Wake of the Ravager* (1994). Targets
the GOG release (engine version 1.10).

Part of the [OpenDS](../README.md) community toolkit. The patch
ships as `darkfix-ds2` releases; the rest of OpenDS provides the
tools used to author them.

This is the headline patch: *Wake of the Ravager* shipped with
game-breaking bugs that even SSI's 1.02 and 1.10 patches did not
fully resolve. There has never been a public unofficial patch.
This will be the first.

Status: v0.1.0 ships the first fix, `fix.ds2.deadtriggers`
(27 dead-trigger registrations repointed to their objects' working
handlers; see [`fixes/001-deadtriggers.md`](fixes/001-deadtriggers.md)).
The headline target remains **the mines elevator freeze**
([`../docs/known-bugs.md`](../docs/known-bugs.md) section 2.1);
see [`../roadmap.md`](../roadmap.md).

The applier machinery is proven on the DS1 side
([`../ds1-patch/`](../ds1-patch/): the distribution format and
no-op round-trip landed in v0.0.1, and v0.1.0 shipped the first
real fix, `fix.ds1.deadtriggers`, 2026-09-11). Per the 2026-09-15
decision, `scripts/` is a COPY of the proven DS1 applier (adapted
for ds2), not shared tooling: each patch ships isolated, and any
promotion to shared tooling waits for a third consumer.

## Layout

- `LICENSE`: MIT, same as the toolkit (spec 14).
- `VERSION`: patch version (docs/versioning.md; single source
  for the release tooling).
- `manifest.toml`: schema v1 (spec.md §4); target game and the
  canonical hashes of every file an enabled fix touches. The
  applier refuses any other engine build.
- `fixes/`: one markdown writeup + one applier script per fix.
  Each fix has a stable identifier (`fix.ds2.<short-name>`).
- `scripts/apply.py`: the umbrella applier.

## Player install (forthcoming)

The mechanics are identical to
[`darkfix-ds1`](../ds1-patch/README.md); read its full
player-facing install walkthrough (Windows-first `py` steps,
what gets backed up, how to revert and verify). Summary: unzip
the release, run `py apply.py "C:\GOG Games\Dark Sun 2"` from
the unzipped folder, and launch the game normally. The applier
verifies your install hash, backs up touched files to
`darkfix-backup/`, applies the enabled fixes, and journals;
`--unapply` reverts. GOG 1.10 is the only supported base by
policy; a non-canonical install gets a hard refusal
([`../docs/install-variants.md`](../docs/install-variants.md)
section 7).

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
