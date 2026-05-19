# Cookbook

End-to-end modding walkthroughs. Each entry is a real, runnable
workflow against the OpenDS toolkit — concrete commands,
expected output, roll-back instructions.

## Current entries

| Entry                                       | What it does                                        |
|---------------------------------------------|-----------------------------------------------------|
| [`edit-pc-hp.md`](edit-pc-hp.md)            | Edit a DS2 PC's HP / stats / XP via `save-inspect edit-pc` (CHARSAVE-based; works for DS2 active party + DS1 inactive char templates). |
| [`bootstrap-items.md`](bootstrap-items.md)  | Discover what an item id represents by tagging your CHARSAVE save and observing in DOSBox. Builds `syms/items.toml`. |
| [`edit-ds1-party.md`](edit-ds1-party.md)    | Edit your **DS1 active party** (HP / stats / weapon damage) via `ds1-party-edit.py` (DARKRUN-based; the right altitude for DS1). |

## Workflow conventions across entries

- Always preview with `--dry-run` before applying.
- Every edit takes an automatic `.bak.<...>` snapshot so roll
  back is a copy.
- Every entry's "Roll back" section shows the explicit command.
- The cookbook references the **`docs/file-formats.md`** entry
  that documents the on-disk layout the edit touches, and the
  **`docs/engine-quirks.md`** entry that flags any "obvious
  thing that doesn't work the obvious way."

## What's missing

These would be useful cookbook entries but aren't written yet:

- **`add-inventory-slot.md`** — using `save-inspect give-item`
  to extend a PC's inventory beyond its existing slot count.
  Discovery loop for items.toml when no `find-empty-slots` slot
  is suitable.
- **`replace-sprite.md`** — extract a sprite via `image-extract`,
  edit the PNG, pack via `image-pack`, replace via
  `gff-cat replace`. Covers the v0.4.0 round-trip.
- **`patch-gpl-bytecode.md`** — author a `gpl-asm --patch` TOML
  to fix a specific GPL chunk bug. End-to-end demonstration of
  the eventual darkfix authoring flow.
- **`build-region-atlas.md`** — drive `tools/atlas/atlas.py
  build` to produce the full game's static HTML browser, then
  pick out a region to mod.
- **`set-up-repro-fixture.md`** — author a new
  `tools/repro/bugs/<id>/bug.toml` fixture so a known bug can
  be re-triggered deterministically.

Tracking these as next-cookbook candidates rather than open
issues. If you hit one of these workflows and write it up while
doing it, the entry slots in cleanly.
