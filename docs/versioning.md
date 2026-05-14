# OpenDS Versioning

Every shippable item in OpenDS has its own version, tracked
independently. The umbrella repository itself is not versioned;
nothing ships from the repo root.

## Items that get versions

1. **Tools** under `tools/<name>/`. Each utility ships
   independently. Tag format: `<tool>-vMAJOR.MINOR.PATCH`.
2. **Patches** under `ds1-patch/` and `ds2-patch/`. Each ships
   independently. Tag formats:
   `darkfix-ds1-vMAJOR.MINOR.PATCH`,
   `darkfix-ds2-vMAJOR.MINOR.PATCH`.

## On-disk

Each item's directory contains a plain-text `VERSION` file:

- One line, no leading `v`.
- Single source of truth for that item's version.

```
tools/verify-install/VERSION   →  0.1.0
tools/gff-edit/VERSION         →  0.1.0
ds1-patch/VERSION              →  0.1.0
ds2-patch/VERSION              →  0.1.0
```

The git tag for a release of that item is `<item>-v<contents-of-VERSION>`.

## Build-system sync

Build descriptors must read from `VERSION`, not duplicate it:

- **Rust tools**: `Cargo.toml`'s `version =` must match the
  `VERSION` file. Today this is verified manually on each bump;
  a pre-commit check can be added if drift becomes a problem.
- **Python single-file tools**: import `VERSION` at runtime
  from the script's own directory:

  ```python
  from pathlib import Path
  VERSION = (Path(__file__).parent / "VERSION").read_text().strip()
  ```

- **Python packaged tools** (with a `pyproject.toml`): the
  packaging tool reads `VERSION` (for example, hatchling's
  `version = { source = "regex", path = "VERSION" }` or
  equivalent), so the file remains the single source of truth.
- **Patches**: `manifest.toml` reads from the patch directory's
  `VERSION`.

## Semver rules (per item)

Each item versions independently. Bumping one tool does not bump
another.

- **MAJOR** — breaking change to the item's public interface.
  For tools, this means CLI flags or output format changed in a
  non-additive way, or the library API broke. For patches, this
  means a hash target or fix-id changed in a way that
  invalidates older user state.
- **MINOR** — backward-compatible feature addition. For tools,
  new flags or new subcommands. For patches, new fixes added.
- **PATCH** — backward-compatible fixes. For tools, bugfixes
  with no interface change. For patches, fixes-to-fixes.

## Pre-1.0

All items start at `0.1.0`. The semantic difference between
0.x.y and 1.0.0:

- **0.x.y** — the interface may still change between minor
  bumps. No strict back-compat promise.
- **1.0.0** — maintainer commits to back-compat under semver
  rules. We do not promise this lightly. Tools graduate to 1.0
  when they are stable enough that a downstream project can
  depend on them.

## What does NOT get a version

- The umbrella repo root. Nothing ships from `opends/` directly.
- Documentation under `docs/`. Tracked by git, not versioned.
- Source-hash manifests under `docs/source-hashes/`. The
  manifest's `[meta].schema_version` covers format evolution;
  the manifest's content is identified by the install it
  describes (e.g. `ds1-gog-1.10`).
