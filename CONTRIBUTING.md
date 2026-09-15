# Contributing to OpenDS

Read this before your first PR. It is short on purpose; the
detail lives in the docs it points at.

## The ground rules

1. **Game data is never committed or redistributed.** You need a
   legitimate copy of one or both games (GOG recommended).
   Installs live under `.games/` (gitignored). `DSUN.EXE` zeroes
   `DARKRUN.GFF` on a writable install, so every DOSBox run must
   overlay-mount; `tools/repro/` enforces the pattern.
2. **Python tools are stdlib-only, Python 3.11+** (`tomllib`).
   Adding a dependency is a spec violation (spec.md §7a): ask
   before importing anything outside the standard library.
3. **Rust deps** live in the workspace `Cargo.toml` shared set
   (`clap`, `anyhow`, `thiserror`, `serde`, `serde_json`,
   `toml`, `png`); anything new needs per-tool justification in
   the PR.
4. **Never break the install.** The applier refuses fingerprint
   drift, length changes, wrong installs, and two enabled fixes
   on one target; EXE patches are in-place only. Any change to
   the applier or the patch format has to preserve those
   guarantees.
5. **Tests are not optional.** Rust tools carry unit + corpus
   tests; Python tools ship a `--selftest` flag that runs
   synthetic fixtures and refusal paths everywhere (corpus parts
   skip when `.games/` is absent). A change without a test does
   not land.

## Getting set up

[`docs/build-environment.md`](docs/build-environment.md) walks
the whole thing (innoextract, DOSBox-Staging, toolchains, the
Python gate). Short version:

```sh
git clone https://github.com/VirInvictus/opends
cd opends
cargo test --workspace     # the Rust gate; corpus tests skip
                           # cleanly without the games
just gate                  # everything: fmt, clippy, tests, ruff,
                           # compileall, all seven selftests
```

Ruff is pinned by the root `ruff.toml`; if your system ruff is a
different version, run the Python checks through
`uvx ruff@0.15.20`.

## What to work on

- [`roadmap.md`](roadmap.md) is the worklist; anything unticked
  is fair game to ask about.
- [`docs/known-bugs.md`](docs/known-bugs.md) is the bug census;
  new bugs get recorded there before (or instead of) getting
  fixed.
- Fix authoring follows
  [`docs/patch-workflow.md`](docs/patch-workflow.md), with worked
  examples in
  [`docs/cookbook/author-first-darkfix.md`](docs/cookbook/author-first-darkfix.md)
  and the rest of the [cookbook](docs/cookbook/).
- The applier contract is
  [`docs/fix-format.md`](docs/fix-format.md); the security
  guarantees it makes are in
  [SECURITY.md](.github/SECURITY.md).

## House conventions

- **The docs set travels with every change**: README, CLAUDE.md,
  spec.md, roadmap.md, patchnotes.md. Version bumps follow the
  full cadence in [`docs/versioning.md`](docs/versioning.md):
  per-tool `VERSION` + its manifest + a patchnotes entry + a
  `<tool>-vX.Y.Z` tag whose message is that patchnotes entry,
  verbatim.
- **No em-dashes in prose** anywhere a human reads it (docs,
  commit messages, tag messages). Use periods, colons,
  semicolons, commas, or parentheses; find-replace to " - " is
  not a recast.
- **Attribute everything.** Logic ported from upstream projects
  gets a code comment naming the file/function AND a
  [`CREDITS.md`](CREDITS.md) row. The `.dso-online/` checkout is
  AGPL: symbol names and addresses are facts we may cite, its
  code never moves into this repo.
- **Syms are hand-curated.** `ovr-map`'s symbol proposals are
  machine-made and never auto-committed; rows are curated by
  hand into `tools/ovr-map/syms/<game>.toml`.
- **License**: MIT for the tools and the patches (spec.md §14);
  game data remains the property of its holders and ships from
  this repo under no circumstance.
