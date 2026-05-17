% next-versions: sprint plan

The 10-tool upgrade sprint. Refreshed after the
gpl-asm v0.6.0 / dialog-extract v0.5.0 / repro v0.3.0 /
opcode-fuzz v0.2.0 / docs §4.5 sprint (commits e4e5f58 ..
6b6c464). The prior sprint's plan is preserved in git
history at commit `a782b4b` for archival comparison.

Same per-tool layout as before: scope (in / out),
implementation steps, test plan, risks, effort estimate.
Background research at the bottom; dependency graph
documents which ships unblock which.

## Current state (start-of-sprint)

| Tool             | Version | Last shipped what |
|------------------|---------|-------------------|
| `verify-install` | 0.1.0   | hash-check against canonical manifest |
| `gff-edit`       | 0.4.0   | read / write / extract / bulk / text-codec / JSON / catalogue |
| `gpl-disasm`     | 0.4.6   | 100% corpus alignment, CFG, symbols, raw_tail |
| `gpl-asm`        | 0.6.0   | encoder + validator + caret + preprocessor (`%define`, `%search-tail`) |
| `dialog-extract` | 0.5.0   | 91% exact LSTR + callgraph-narrowed `possible_writers` |
| `save-inspect`   | 0.6.0   | DS1+DS2 schemas + `SAVE0N.SAV == DARKRUN.GFF` discovery |
| `image-extract`  | 0.2.1   | 99.95% corpus, 1 malformed chunk pinned |
| `region-render`  | 0.5.0   | tiles + walls + entity sprites; cycle table un-RE'd |
| `repro`          | 0.3.0   | harness + ds1/ds2-smoke + `--play --session` continuity |
| `opcode-fuzz`    | 0.2.0   | chunk-patchwork + `run` (DARKRUN diff) |

## Sprint order

Sequenced by ROI / dependency:

1. **`verify-install v0.2.0`**: repair mode + JSON output. No
   deps; quick safety-net upgrade.
2. **`gff-edit v0.5.0`**: GFF builder API. Unblocks
   opcode-fuzz recipe synthesis (single-chunk synthetic GFFs).
3. **`image-extract v0.3.0`**: multi-frame sprite export.
   Self-contained; deferred from v0.2.0.
4. **`region-render v0.6.0`**: animated entity sprites.
   Depends on (3). Pivots away from the cycle-table wall;
   uses ETAB `frame_count > 1` for visible animation
   instead.
5. **`dialog-extract v0.6.0`**: CFG-distance-ordered
   `possible_writers`. Self-contained.
6. **`gpl-disasm v0.5.0`**: variable naming from a curated
   `gbyte.toml` / `gnum.toml` / etc. Self-contained; benefits
   every consumer (gpl-asm, dialog-extract, opcode-fuzz).
7. **`gpl-asm v0.7.0`**: parameterised macros + `@include`.
   Self-contained; benefits opcode-fuzz recipes.
8. **`save-inspect v0.7.0`**: `SAVE` chunk decode.
   Self-contained RE thread.
9. **`repro v0.4.0`**: ydotool input automation + video
   capture. Gated on dep approvals (ydotool +
   gnome-screen-recorder or equivalent).
10. **`opcode-fuzz v0.3.0`**: recipe library + structured
    diff (via save-inspect v0.7.0) + boot-chunk
    identification. Depends on (8), benefits from (2) (7) (9).

The cycle-table thread (region-render `--animate`) stays
parked. The third pass (§4.5 deepening commit `6b6c464`)
documented the DOS/4GW runtime ABI wall; cracking it requires
either a DOS/4GW ABI doc dive or a DSO function-table dump
from the community, neither of which we control. Document
the wall and move on. The `--animate` work, if it ever ships,
sits behind opcode-fuzz's dynamic analysis path.

---

## `verify-install v0.2.0`: repair mode + JSON output

The Phase 0 tool. v0.1.0 hash-checks and reports
`matched / mismatched / missing / extras / skipped`; v0.2.0
adds *repair* and *machine-readable output*.

### Scope (in)

- **`--json`** output mode. Emits the report shape the
  v0.1.0 CLI already prints, as a top-level JSON object.
  Useful for tooling (CI checks, dashboards, the repro
  harness's pre-run sanity check).
- **`--repair <gog-installer.exe>`** mode. For every
  `mismatched` or `missing` file in the manifest, re-extract
  the canonical bytes from the GOG installer via
  `innoextract` and write them back into the install
  directory. Stages a backup of any overwritten file to
  `<install>/__verify-install-backup/` so the change is
  reversible.
- **`--dry-run`** flag pairs with `--repair`: report what
  WOULD be repaired without writing anything.

### Scope (out)

- **Repair from any source other than the GOG installer**.
  CD-ROM / non-GOG installs aren't supported in v0.2.0.
- **Multi-game-at-once**. Always one game per invocation.
- **Re-hash on the fly**. The manifest stays canonical;
  v0.2.0 doesn't add `--capture-fresh` rebuilds (already in
  v0.1.0's `--capture` mode).

### Implementation steps

1. Add `--json` argparse; refactor the existing print path
   to build a dict and either `json.dumps` or pretty-print.
2. Add `--repair <installer.exe>` + `--dry-run` flags.
3. Shell to `innoextract -e --output-dir <tmp> <installer>`
   to stage the canonical tree; copy the needed files into
   the install dir on top of backups.
4. Stretch: detect when the `__verify-install-backup/` dir
   exists and offer `--rollback`.

### Test plan

- Manual: corrupt a file in `.games/ds1/`, run
  `--json`, confirm structured `mismatched` entry. Then run
  `--repair --dry-run`, confirm it lists the file. Then
  `--repair`, confirm install matches manifest again.
- The `__verify-install-backup/` dir contains the corrupted
  original after repair (rollback-safe).

### Why this exists (the DARKRUN.GFF lesson)

The v0.1.0 repro work zeroed `DARKRUN.GFF` in `.games/ds1/`
the first time we ran a DOSBox session without the overlay-
mount discipline. We recovered manually via `innoextract` and
a one-off `cp` from `DARKSAVE.GFF`. `--repair` makes that
recovery a one-command operation, not a five-minute
session-derailing detour.

### Effort estimate

One session.

---

## `gff-edit v0.5.0`: GFF builder API

The Phase 1 foundation. v0.1..0.4 ships read / write /
extract / replace / bulk / text-codec / JSON. v0.5.0 adds
**construction from scratch**: a builder API that synthesises
a new GFF from a sequence of `(kind, id, bytes)` records.
Library-only; no new CLI surface in v0.5.0 (the existing
`gff-cat` subcommands don't need a builder yet).

### Scope (in)

- **`GffBuilder` type** with methods:
  - `new()` returns a builder with an empty TOC.
  - `with_data0(v: u32)` sets the per-file sentinel.
  - `add_chunk(kind: FourCC, id: i32, bytes: &[u8])` appends
    an indexed chunk.
  - `build()` returns `Vec<u8>` (the GFF bytes).
- **Round-trip property test**: every GFF in the corpus that
  consists only of indexed chunks can be deconstructed
  (`Gff::from_bytes` → `(kind, id, bytes)` records) and
  rebuilt (`GffBuilder::add_chunk` → `build`) to a
  byte-identical (or at worst structurally-equivalent) GFF.
- **Documentation** of the v0.1.0 GFF on-disk layout from
  `docs/file-formats.md` §1 mirrored in module-level
  rustdoc.

### Scope (out)

- **Segmented chunks** (the `0x80000000` flag path).
  Building a segmented chunk list requires the secondary-
  table dance (`GFFI` chunk + cross-reference). Defer to
  v0.6.0; v0.5.0 supports indexed-only.
- **Free-list management**. v0.5.0 emits a zero-length free
  list (matches what most GFFs ship with). Free-list aware
  building is a v0.6.0+ feature.
- **CLI `gff-cat build`**. The builder is a library API for
  opcode-fuzz and future tools; no CLI in v0.5.0.

### Implementation steps

1. Add `tools/gff-edit/src/builder.rs` with `GffBuilder`.
2. Re-export from `lib.rs`.
3. Property test: `tests/builder_corpus.rs` round-trips every
   GFF that has zero segmented chunks (most of them, per
   v0.2.0's segmented stats).
4. Add a tiny unit test that builds a hand-crafted 2-chunk
   GFF and `Gff::from_bytes` reads it correctly.

### Test plan

- New property test in `tests/builder_corpus.rs`. Skip
  silently when `.games/` is absent.
- Unit tests in `builder.rs`.

### Risks

- **TOC byte layout drift**. The v0.1.0 reader is permissive
  about types-list ordering / free-list shape; the builder
  must pick a *canonical* shape that round-trips through
  the reader. The corpus test will surface any divergence.

### Effort estimate

Two sessions: one for the builder, one for the property
test against the corpus.

---

## `image-extract v0.3.0`: multi-frame sprite export

Deferred from v0.2.0. BMP chunks with `frame_count > 1` are
animations (NPC walk cycles, water tile shimmer, fire
flicker); v0.2.1 still decoded only frame 0. v0.3.0 ships the
multi-frame export.

### Scope (in)

- **`image-extract --frames all`** flag. For multi-frame
  chunks, emits `<name>-frame-<N>.png` per frame instead of
  the single `<name>.png` v0.2.0 produces.
- **`image-extract --spritesheet`** flag. Composite every
  frame into a horizontal strip and emit a single
  `<name>-spritesheet.png`. Preserves palette indexing.
- **Animated-PNG output** via the `png` crate's APNG support
  if the existing dependency offers it; otherwise emit a
  numbered PNG sequence and document GIF conversion via
  `ffmpeg`.
- **CLI default** stays "frame 0 only" for backwards
  compatibility; `--frames all` is opt-in.

### Scope (out)

- **GIF output**. GIF requires either a new dep (`gif`
  crate) or hand-rolling the LZW encoder; defer.
- **Sprite-animation metadata** (per-frame delay, loop
  count). The DS engines hold animation timing elsewhere
  (probably in the ETAB or OJFF chunk metadata); decoding
  that's a separate RE thread.
- **The one malformed chunk** (DS1 `RESOURCE.GFF:ICON/0x7f9`
  frame 2). Pinned in `EXPECTED_FAILURES`; stays pinned.

### Implementation steps

1. Add `Bitmap::decode_all_frames(&self) -> Vec<Result<Frame>>`
   to the library.
2. Wire `--frames all` / `--spritesheet` argparse to the
   binary; the existing per-frame emitter handles each
   frame in isolation.
3. Spritesheet: compute max width × N * max height (or sum
   widths × max height for horizontal strip); composite via
   the existing palette-indexed PNG path.
4. Update `tests/corpus_smoke.rs` to assert multi-frame
   decoding works across the corpus (every frame in every
   chunk decodes; counts logged).

### Test plan

- Corpus stats: total frames decoded across all multi-frame
  chunks. Should be >= the v0.2.0 count of 1,975 (one
  multi-frame chunk's first frame counts once in v0.2.0,
  all N frames count under v0.3.0).
- Visual smoke: pick a known walk-cycle sprite (NPCs in
  DS1 RGN02 villages), emit spritesheet, eyeball.

### Effort estimate

One session.

---

## `region-render v0.6.0`: animated entity sprites

Pivots away from the cycle-table wall (`docs/dsun-exe-re.md`
§4.5 catalogues why DSUN.EXE byte-pattern search has run its
course on that surface). v0.6.0 uses `image-extract v0.3.0`'s
multi-frame sprite work to animate the **entity layer**
(NPCs, props, environmental objects) instead of the palette.

### Scope (in)

- **`region-render --animate-entities`** flag. For each ETAB
  record whose OJFF references a `frame_count > 1` BMP,
  emit N frames of the region with that entity stepping
  through its animation. Output: numbered PNG sequence
  `region-<id>-frame-<N>.png`.
- **Default behaviour unchanged**. No flag = single-frame
  v0.5.0 output.
- **`--frame-count N`** override. Default: render the
  *maximum* frame count among the region's entities. Some
  entities loop at 4 frames, others at 8; rendering at the
  LCM (or just the max) keeps things in sync.

### Scope (out)

- **Palette animation**. Still blocked on the cycle-table
  RE. `--animate` (without `-entities`) stays unimplemented.
- **Per-entity timing**. v0.6.0 advances every entity one
  frame per emitted region-frame; real timing per entity
  is a v0.7.0+ feature.
- **GIF / single-file output**. Same reason as
  image-extract.

### Implementation steps

1. In `region-render/src/lib.rs`, walk ETAB records and
   query each OJFF's BMP `frame_count` via the existing
   image-extract integration.
2. Compute `max_frames = max(frame_count for each entity)`.
3. Render frames 0..max_frames-1, picking the right per-
   entity frame each pass (`frame_idx % entity.frame_count`).
4. Add CLI flags. Output: numbered PNG sequence in the
   `-o` directory (require `-o <dir>` when `--animate-entities`
   is set).

### Test plan

- Visual: render DS1 RGN02 with `--animate-entities --frame-
  count 8`; eyeball the NPC walk cycles.
- Corpus: every region renders at frame 0 byte-identically to
  v0.5.0 output (no regression).

### Effort estimate

Two sessions. The entity layer is already in v0.3.0;
v0.6.0 walks it across frames.

---

## `dialog-extract v0.6.0`: CFG-distance-ordered possible_writers

v0.5.0's `possible_writers` array is unordered. v0.6.0 orders
it by graph distance so the closest writers come first,
making the human-or-tool reader's first guess the most
likely one.

### Scope (in)

- **Per-writer `distance` field**. Distance from the read
  site's chunk to the writer's chunk, measured in
  `gpl global sub` hops on the reverse CFG.
- **`possible_writers` sorted ascending by `distance`**.
  Same-chunk writers (distance = 0) come first; direct
  callers (distance = 1) next; etc.
- **Distance-1 filter on the `--quick-resolve` flag** (new).
  Emits only same-chunk + direct-caller writers; useful for
  the common case where the LSTR is set by the immediate
  caller.

### Scope (out)

- **Symbolic call-path tracing**. The "which caller actually
  fires" question. Static analysis can't answer it without
  a dynamic trace; queued for v0.7.0+ with opcode-fuzz
  integration.
- **`gpl_search` raw_tail-mediated writes**. The search
  opcode can mutate LSTR slots indirectly via the raw_tail
  preserved bytes. Marginal corpus impact; queued.

### Implementation steps

1. In `build_reachable_callers`, extend the BFS to record
   distance per visited node (not just visited-set
   membership).
2. In `attach_possible_writers`, look up each writer's chunk
   distance and store on the writer record.
3. Sort `possible_writers` by distance ascending; break ties
   by chunk id ascending (deterministic).
4. Add `--quick-resolve` flag that filters to distance <= 1.

### Test plan

- A unit test with a hand-crafted call chain: ensure the
  closer writer surfaces first.
- Corpus stats: distribution of distances in the
  unresolved-LSTR set. Probably most are distance 1
  (immediate caller); the tail at distance 2+ is the
  interesting subset.

### Effort estimate

Half a session.

---

## `gpl-disasm v0.5.0`: variable naming

Currently the disasm emits `GBYTE[42]`, `GNUM[3]`, etc., as
raw indices. v0.5.0 lets a curated `syms/gbyte.toml`
attach names to specific slots, decorating output across
the toolkit (every consumer: gpl-asm, dialog-extract,
opcode-fuzz; all see the names automatically because the
disasm output is the universal input format).

### Scope (in)

- **`syms/variables.toml`** schema:

  ```toml
  [[gbyte]]
  id = 42
  name = "POV_FLAGS"
  doc = "Bit flags for the active character."

  [[gnum]]
  id = 3
  name = "PARTY_GOLD"
  doc = "Party-wide gold count."
  ```

  Independent tables per variable kind (`gbyte`, `gnum`,
  `gbignum`, `gflag`, `gname`, `gstring`; locals omitted
  since they're per-chunk).
- **Loaded by default** from `tools/gpl-disasm/syms/`
  alongside the existing `opcodes.toml` / `functions.toml`.
- **Render decoration**: `GBYTE[42]` becomes
  `GBYTE[42 (POV_FLAGS)]` in text output; JSON output
  gains an optional `name` field on each `Expression::Variable`.
- **Backwards compatible**: when `syms/variables.toml` is
  absent or empty, output is byte-identical to v0.4.6.

### Scope (out)

- **Local-variable naming**. Locals are chunk-scoped; per-
  chunk symbol overrides are a v0.6.0 feature.
- **Type-decorated names**. The variable's role (HP / XP /
  flag bitfield / etc.) is documentation, not syntax.
- **Bulk catalog**. The v0.5.0 ship has zero curated
  entries; the catalogue grows organically as the toolkit
  surfaces meaningful slots.

### Implementation steps

1. Extend the `Symbols` loader in `gpl-disasm/src/lib.rs`
   to parse `[[gbyte]]` / `[[gnum]]` / etc. tables.
2. Add an optional `name: Option<Cow<'static, str>>` field
   on `Expression::Variable` (skipped in JSON when None).
3. Wire `Display` for `Expression::Variable` to emit the
   decorated form when name is set.
4. Update `tests/` to assert decorated round-trip.

### Test plan

- Corpus round-trip stays at 600 / 600 (the decoration
  doesn't affect bytecode; only display).
- Unit test: with a single `[[gbyte]] id = 0 name = "FOO"`,
  every `GBYTE[0]` in the corpus output gets `(FOO)`.

### Risks

- **gpl-asm parser** must accept the decorated form when
  consuming text input. Either strip the parenthesised
  name during the parser's pre-scan, or treat it as a
  trailer comment.

### Effort estimate

One session for gpl-disasm + a follow-up half-session for
gpl-asm's text parser to round-trip the decorated form.

---

## `gpl-asm v0.7.0`: parameterised macros + @include

Deferred from v0.6.0. Two real authoring features for the
hand-edit workflow.

### Scope (in)

- **Parameterised macros**: `%define foo(arg1, arg2) <body>`.
  Substitution captures arg-name → substitution-text inside
  the body. Args are simple textual replacement (no type
  checking; same shape as v0.6.0's plain `%define`).
- **`@include "path/file.asm"`**: textual include relative
  to the current file. Circular-include guard.
- **`.const NAME = VALUE`**: integer-only alias of
  `%define`; might be a single-line ergonomic.

### Scope (out)

- **Macro hygiene / scoped names**. Parameter names can
  shadow the global `%define` namespace inside the macro
  body; not a feature, just a side effect of text
  substitution.
- **Conditional `@if` / `@ifdef`** preprocessor blocks.
- **Variadic macros**.

### Implementation steps

1. Extend `preprocess` in `parse.rs` to recognise
   parameterised `%define name(args...)`. Store as
   `Dict[name, ParameterisedMacro]` separately from the
   plain define table.
2. At expansion time, match `name(actual1, actual2)` at
   identifier positions; substitute args into the body
   then run the body through the rest of the preprocessor.
3. `@include`: scan input, recursively preprocess included
   files with a depth limit / circular guard.
4. Tests covering both features + interaction (a macro
   that references a constant; an `@include`d file that
   defines a macro).

### Effort estimate

One to two sessions.

---

## `save-inspect v0.7.0`: SAVE chunk decode

The big un-decoded surface left in save-inspect. Each `SAVE`
chunk in `DARKRUN.GFF` (~60 per save) holds per-region
world state: entity positions, NPC activity, trigger flags,
quest progression. Decoding them gives modders end-to-end
visibility into a playthrough.

### Scope (in)

- **`SaveChunk` decoder** in `save-inspect.py`. Identifies
  the chunk's region (probably from the chunk's id), then
  walks the body via the schema we recover.
- **Field-by-field empirical decode** of the SAVE chunk's
  shape, anchored to:
  - libgff's `gfftypes.h` notes (`SAVE` = "save entries",
    nothing more documented).
  - soloscuro-archive's `save-load.c` (a Lua dump format,
    not the original; useful as a reference for *what* the
    engine persists but not *how*).
  - Cross-comparison of `SAVE` chunks across DS1's pristine
    `DARKRUN.GFF` (factory) and the played `ds1-fuck`
    fixture (one walk through character creation + the
    starting region).
- **Per-game schemas**: DS1 and DS2 may differ; ship per-
  game decoders if they diverge.
- **`save-inspect` schema output gains a `save_chunks` array**
  with structured per-region records.

### Scope (out)

- **Full RE of every world-state field**. Anchor what we
  can (entity positions, flag bytes); surface unknowns as
  opaque hex with placeholder names (same hygiene as the
  combat / character `_slot_N` work).
- **DS1 `ETAB` chunk decode**. DS1's entity table inside
  `DARKRUN.GFF` (we have one per save); deferred to a
  future thread.

### Implementation steps

1. Pull DS1 `DARKRUN.GFF` factory vs `ds1-fuck` played save.
2. Diff SAVE chunks per region id. Same regions: byte-by-
   byte diff to identify which fields change with play.
3. Categorise the changing fields (XP values, party
   position, flag bits, ...).
4. Build the decoder in `save-inspect.py` with a per-game
   format tag (`_format: ds1_save_chunk` /
   `ds2_save_chunk`).
5. Validate across both played saves (ds1-fuck and ds2's
   `--play` capture, with the new continuous saves from
   `repro --play --session`).

### Test plan

- Self-consistency: decode + re-encode (or just compare
  with a no-op) every SAVE chunk; field counts stable.
- Cross-save diff: `save-inspect diff factory.gff
  played.gff` highlights only meaningful fields, not
  every byte.

### Effort estimate

Multi-session. RE work; could stall on field semantics.
Treat like the DS2 character schema work: ship what's
locked, mark the rest as opaque placeholders.

---

## `repro v0.4.0`: ydotool input automation + video capture

Deferred from v0.3.0 (priority 2 + 3). Both need dep
approvals first.

### Scope (in, contingent on dep approval)

- **`ydotool` integration** for keystroke automation on
  Wayland. Daemon (`ydotoold`) setup documented in README;
  the harness detects ydotool availability and silently
  no-ops keystrokes when absent.
- **`[trigger.keystrokes]` schema** in `bug.toml`:

  ```toml
  [[trigger.keystrokes]]
  at_seconds = 8
  send = "Return"
  ```

  The harness spawns a Python thread that fires keystrokes
  on schedule after DOSBox starts.
- **Video capture** via the chosen GNOME-Wayland recorder
  (Brandon to pick between `gnome-screen-recorder` D-Bus,
  pipewire + ffmpeg portal, or OBS WebSocket). Output:
  `<session>/repro.webm`.
- **`[expected].record_video`** flag in `bug.toml`.

### Scope (out)

- **Mouse input**. Keyboard only in v0.4.0.
- **Differential capture** (run-with-patch vs without).
  v0.5.0.

### Implementation steps

(All gated on dep decisions; see "What still needs deciding"
below.)

### Risks

- **Wayland window focus** for keystrokes. If the user
  alt-tabs away mid-run, input lands on the wrong window.
  Document; consider a "focus-lock" mode.
- **Daemon setup** for ydotool (uinput access). One-time;
  README covers it.

### Effort estimate

One to two sessions per feature; gated on dep approvals.

---

## `opcode-fuzz v0.3.0`: recipe library + structured diff

Builds on `repro v0.4.0`'s input automation (for
deterministic execution) and `save-inspect v0.7.0`'s SAVE
chunk decode (for structured state diff). v0.3.0 ships the
first **real fuzz capabilities**.

### Scope (in)

- **`tools/opcode-fuzz/recipes/`** directory. Each recipe is
  a `.asm` template (uses `gpl-asm v0.7.0` parameterised
  macros) representing prologue + test-opcode + epilogue.
- **`opcode-fuzz fuzz <opcode>`** subcommand: instantiate
  the recipe with the target opcode, swap into a known
  boot-time chunk, run via `repro --play --session`, capture
  pre/post state.
- **Structured diff** via save-inspect v0.7.0: report
  which globals changed (by name from gpl-disasm v0.5.0's
  variable catalogue), not just byte offsets.
- **Boot-chunk identification helper**: `opcode-fuzz
  boot-chunks <game>` lists chunks the engine invokes
  before user input is required, based on
  `gpl-disasm --global-cfg` analysis + per-chunk shape
  heuristics.

### Scope (out)

- **Automated bisection** of opcode parameters.
  v0.4.0.
- **Bulk fuzz across all unknown opcodes**. v0.4.0 with
  result database.

### Dependencies

- `repro v0.4.0` (input automation for deterministic
  execution).
- `save-inspect v0.7.0` (SAVE chunk decode for structured
  diff).
- `gpl-asm v0.7.0` (parameterised macros for recipe
  templating).
- `gff-edit v0.5.0` (builder API for synthesised test
  chunks).

### Effort estimate

Multi-session; gated on the four dependencies above.

---

## Dependency graph

```
verify-install v0.2.0 ───────────────────────────────────┐
                                                         │
gff-edit v0.5.0 ──── unblocks ──┐                       │
                                ▼                        │
image-extract v0.3.0 ─── unblocks ──┐                   │
                                    ▼                    │
                  region-render v0.6.0                   │
                                                         │
dialog-extract v0.6.0 ──────────────────────────────────┤
                                                         │
gpl-disasm v0.5.0 ─── benefits ──┐                      │
                                  ▼                      │
                  gpl-asm v0.7.0 ─── benefits ──┐       │
                                                ▼        │
save-inspect v0.7.0 ─── benefits ──┐ opcode-fuzz v0.3.0 ◄
                                    ▼
                  opcode-fuzz v0.3.0

repro v0.4.0 ─── unblocks ── opcode-fuzz v0.3.0
```

The convergence point is `opcode-fuzz v0.3.0`, which depends
on four of the other ships (gff-edit, gpl-asm, save-inspect,
repro v0.4.0). The other six tools can ship in any order
without external dependencies.

## What still needs deciding

Two dep-approval questions for `repro v0.4.0`:

1. **`ydotool`** as a Fedora package dep (`dnf install
   ydotool`). It runs as a user-mode daemon with uinput
   access; one-time setup. Approval needed before staging
   in the harness.
2. **Video recorder choice**. Options:
   - `gnome-screen-recorder` (D-Bus into gnome-shell):
     zero new package deps, GNOME-only, smallest blast
     radius.
   - `ffmpeg -f pipewire` via xdg-desktop-portal:
     cross-DE, no new deps (`ffmpeg` already installed),
     fiddly portal setup the first time.
   - OBS Studio + `obs-cli` (WebSocket): heaviest, most
     features.

Until both deps are settled, `repro v0.4.0` is parked and
`opcode-fuzz v0.3.0` waits on it for the input-automation
half.

## Background research

The current sprint's research notes from
`docs/next-versions.md` (preserved at git history commit
`a782b4b`) remain valid. Updates from this planning pass:

- **DSO Emulator scope** (memory [[dso-emulator-scope]]):
  the "DSO Emulator" Brandon's seen mention of is the
  multiplayer Crimson Sands project, **not** the
  singleplayer DS1 / DS2 engines OpenDS targets. Engine-
  level findings from DSO RE might transfer to DS2
  specifically; the protocol / client RE doesn't apply to
  OpenDS at all. Worth watching their *public* drops for
  engine-side findings (DSUN.EXE function offsets, GPL VM
  state addresses, palette cycle logic) that map to DS2.

- **dsoageofheroes org** state as of 2026-05-17: 7 repos,
  no new ones since the original RE pass. `libgff` last
  updated 2025-05-04; `libsoloscuro` 2025-04-15;
  `soloscuro` 2025-04-03. `soloscuro` shows recent
  "client" + "server" + "lua interpreter" commits but
  is still pre-playable. No public release-grade engine
  re-impl has shipped.

- **DSUN.EXE palette-cycle wall** (commit `6b6c464`):
  three time-boxed passes ruled out the byte-pattern
  approaches we have. Next moves require either DOS/4GW
  ABI documentation (the engine doesn't install its own
  DPMI interrupt vectors; the extender's runtime does)
  or a function-table dump from the DSO debug build.
  Neither's in our control. `region-render --animate`
  pivots to entity-frame animation instead.
