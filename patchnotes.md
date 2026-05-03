# Patchnotes

Released versions appear here, newest first.

## Unreleased

- Initial project skeleton: README, spec, roadmap, docs, per-game
  patch folders (`ds1-patch/`, `ds2-patch/`), logo.
- Project framed as **OpenDS — a community toolkit**: tools,
  patches, and documentation as three first-class deliverables.
  Patches ship as **darkfix-ds1** and **darkfix-ds2**. The full
  engine reimplementation remains the aspiration encoded in the
  project name; not a roadmap commitment ([`spec.md`](spec.md)
  §12).
- Tools-first ordering established
  ([`spec.md`](spec.md) §1b, [`roadmap.md`](roadmap.md)): every
  digging-tool ships before the patches that depend on it.
  Patches start at Phase 6.
- Engine research dossier compiled from public reverse-engineering work.
- GFF file-format catalog documented.
- GPL bytecode editing strategy documented
  ([`docs/gpl-bytecode.md`](docs/gpl-bytecode.md)).
- DSUN.EXE binary patching strategy documented
  ([`docs/binary-patching.md`](docs/binary-patching.md)).
- End-to-end fix authoring workflow documented
  ([`docs/patch-workflow.md`](docs/patch-workflow.md)).
- GOG installer extraction verified locally on Fedora 43.
