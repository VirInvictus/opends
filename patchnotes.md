# Patchnotes

Released versions appear here, newest first.

## Unreleased

- **`tools/save-inspect/` v0.5.0** locks the DS2 character
  sub-block schema (66 bytes). v0.4.0 fully decoded DS2 combat
  but still emitted the character sub-block as opaque hex;
  v0.5.0 closes that. Every CHAR record in DS2 GOG 1.10's
  `CHARSAVE.GFF` (all 19) now decodes with full XP / HP / PSP
  / id / alignment / stats / real_class / level / AC / move /
  magic_resistance / num_blows / num_attacks / num_dice /
  num_sides / num_bonuses / saving_throw / allegiance / size /
  spell_group / high_level / sound_fx / attack_sound /
  psi_group / palette fields.
  - **Layout**. DS2 is DS1's 72-byte `ds_character_t` minus 6
    bytes: drops `_data2` (4) and two of
    `(race, gender, alignment)` (2). The single remaining
    pre-stats byte at offset 20 pattern-matches DS1's
    `alignment` (last pre-stats field; all observed values
    inside the documented 0..8 alignment range and decode
    through `ALIGNMENT_NAMES`). The trailing 17 bytes after
    `num_bonuses` match DS1's layout one-for-one
    (saving_throw[5], allegiance, size, spell_group,
    high_level[3], sound_fx, attack_sound, psi_group,
    palette).
  - **Validation**. All 19 DS2 CHAR records decode with stats
    in the 3..25 D&D 2e range, HP/PSP matching the combat
    sub-block, XP non-negative, alignment enum-resolvable. The
    existing DS1 path is untouched (the dispatch only triggers
    for `len == 66`).
  - **Output**. `_format` is `ds2_character`. Fields use the
    same names as the DS1 decoder where the layout matches,
    so consumers can program against both decoders with the
    same shape (just check `_format` or feature-detect on the
    missing `race` / `gender` / `_data2`).
  - **Out of scope (queued for v0.6.0)**: DS2 **item**
    sub-blocks. The DS1 schema in `_decode_item` is libgff's
    `ds1_item_t`; DS2 item ships at 23 bytes (DS1 at 21) and
    libgff's struct computes to 23, so DS2 items may already
    be fully decoded by the existing path; needs corpus
    validation.
  - **`roadmap.md` Phase 4 §save-inspect**: DS2 character row
    ticked; DS2 item row is the new tail.
  - **VERSION**: 0.4.0 -> 0.5.0.

- **`docs/dsun-exe-re.md` §4.4 / §4.5 correction**. The cycle-
  table identification in the prior §4 commit was wrong; the
  loop at `0x23067` is the region GMAP / entity-render walker,
  not the palette cycle routine. The byte signature that drove
  the misidentification (`66 ee` interpreted as a 32-bit
  `out dx, eax`) parses as `f7 66 ee` = `mul word ptr
  [bp-0x12]` in 16-bit mode, which is what the surrounding
  segment actually is.
  - **§4.4 retracted**. The loop walks a far-pointer table at
    `[0x6690]` with 8-byte records, counted by `[0x57c8]`,
    filtered against `[0x5746]` / `[0x574a]`. The work block
    at `0x23095` reads a 128-wide tile grid, masks 5 bits per
    cell as an entity-index, looks up a 4-byte
    `(x_offset, y_offset, sprite_id)` record at
    `[0x574c + 4 * (idx-1)]`, and far-calls a draw routine.
    That's the region entity-render path, not palette cycling.
  - **§4.5 (new)**. Lists the three productive next directions
    for finding the actual cycle routine: caller search
    against `write_palette_range` (`0x288a4`), tick-handler
    trace through the engine main loop, or shape-matching DS2
    against DSO's `VGAColorCycle` if a function-table dump
    surfaces.
  - **§4.6**: DSO symbol table preserved (the names remain
    valid anchors); the wrong "this maps to `0x23067`" claim
    is removed.
  - **§5 (open items)**: row 3 (animated palette colours)
    revised to point at §4.5's next-step list instead of the
    retracted decode path.
  - **`region-render` stays at v0.5.0**. No `--animate` flag
    in v0.6.0; would need the actual cycle routine.

- **`tools/image-extract/` v0.2.1** root-causes the single
  remaining `FrameOutOfBounds` failure from v0.2.0's 99.95%
  decode rate and pins it in the corpus regression test. The
  decoder is unchanged.
  - **The chunk**: DS1 `RESOURCE.GFF` `ICON / 0x7f9`. 734
    bytes, header declares 3 frames at offsets
    `0x12 / 0x17 / 0x2d9` (18, 23, 729). Frames 0 + 1 decode
    cleanly as 90 x 7 Ds1Rle. Frame 2's declared offset (729)
    leaves only 5 bytes for the 9-byte frame header. **The
    chunk is malformed in the GOG ship** (3 frames declared,
    space for ~2.5). The engine almost certainly never
    references frame 2, or it would crash; the dead frame
    survived into the 1.10 build.
  - **Decoder behaviour**: correct as-is. Frames 0 and 1
    decode; frame 2 returns `ImageError::FrameOutOfBounds`.
    No panic, no silent garbage.
  - **`tests/corpus_smoke.rs` strengthening**: the test now
    carries an `EXPECTED_FAILURES` list of exactly one entry
    (`ds1/RESOURCE.GFF/ICON/0x7f9/frame 2`). New decoder
    regressions that introduce additional failures break the
    test; a future decoder improvement that decodes this
    chunk also breaks the test (forcing the patchnote to
    demote the limitation). Either way it's a load-bearing
    invariant now, not a silently-tolerated count.
  - **README** has a new "Known limitation" subsection
    explaining the malformed chunk; first place to look if
    someone wonders why the v0.2.x corpus stat reads 1,975 /
    1,976 instead of 1,976 / 1,976.
  - **VERSION**: 0.2.0 -> 0.2.1.

- **`tools/repro/` v0.2.0** adds the DS2 path and quality-of-life
  on top of the v0.1.0 harness pattern. No new shape (input
  automation, video, differential capture all still v0.3.0+);
  v0.2.0 is the breadth-and-polish release.
  - **`ds2-smoke` fixture** mirroring `ds1-smoke`: factory
    saves auto-staged into the C: overlay, a `sound_ds`-
    generated `SOUND.CFG` (DS2 ships MEL 2.2.7 with the same
    DSP Detect Fail story as DS1's MEL 2.0.9b; the captured
    file gets the engine through detect), `DSUN -W0 -L`
    trigger per RAVAGER.BAT. PASS end-to-end against a clean
    `.games/ds2/` GOG 1.10 install.
  - **DOSBox stderr captured to `<scratch>/dosbox.log`**. Every
    run now has a DOSBox-side log artifact (CONFIG / SDL /
    MOUNT / MAPPER / RENDER / CAPTURE lines etc.); first
    place to look when a fixture fails for non-MEL reasons.
  - **`repro.py --list`** enumerates fixtures with target
    game + one-line description.
  - **DSUN.LOG preview on early-exit FAIL**. When DOSBox quits
    on its own before the budget, the harness prints the first
    three lines of `<scratch>/d/DSUN.LOG`. MEL Fatal Errors
    land in your face instead of behind a `--keep-scratch`.
  - **`tools/repro/bugs/README.md`** catalogue indexing
    fixtures (cross-links to `docs/known-bugs.md` open until
    real-bug fixtures ship).
  - **Clearer FAIL line**: "DOSBox quit on its own (game
    exited or never launched)" vs "SIGTERM after timeout
    (game was still running)" instead of the old neutral
    "exit on its own" / "SIGTERM after timeout".
  - **`roadmap.md` Phase 2**: DOSBox-configured row already
    ticked; save-state library row remains partial (smoke
    fixtures only; real-bug fixtures need input automation in
    v0.3.0). Recording-wrapper row stays unticked; queued for
    v0.3.0 alongside input automation, since both solve the
    same "non-interactive bug repros" problem.
  - **VERSION**: 0.1.0 -> 0.2.0.

- **`tools/save-inspect/` v0.4.0** locks the full DS2 combat
  sub-block layout. v0.3.0 had a `_likely_stats` /
  `_likely_name` heuristic that worked but advertised
  itself as unverified; v0.4.0 ships first-class `stats` +
  `name` fields backed by a layout that's empirically
  consistent across every CHAR record in DS2 GOG 1.10's
  `CHARSAVE.GFF`.
  - **Schema**. The 49-byte DS2 combat sub-block is the DS1
    24-byte shared prefix (hp / psp / char_index / id /
    ready_item_index / weapon_index / pack_index /
    data_block[8] / special_attack / special_defense), then
    `_reserved_0` (1 byte, always 0x00), `stats` (6 bytes),
    `_slot_31` (1 byte, low range 0..6), `_reserved_1` (1
    byte, always 0x00), and `name[16]` (NUL-padded). DS2
    saves 9 bytes vs DS1 by dropping `icon` (2), `ac` (1),
    3-of-4 of `move/status/allegiance/data`, and trimming
    `name` from 18 to 16 characters.
  - **JSON output**. `_format` flips from
    `ds2_partial_combat` to `ds2_combat`; the heuristic
    `_likely_stats` and `_likely_name` keys are gone,
    replaced by structured `stats` + `name` fields. Three
    positions (24, 31, 32) still ship with placeholder names
    (`_reserved_0`, `_slot_31`, `_reserved_1`) because their
    semantics aren't pinned to DSUN.EXE source yet; surfacing
    them as raw bytes is more honest than guessing.
  - **Out of scope (queued for v0.5.0)**: DS2 character
    sub-block (66 bytes). Still emitted as opaque hex. The
    DSO symbol table names the writer (`SaveCharRec` at DSO
    offset `0x0002C45F`); locating the DS2 DSUN.EXE
    counterpart by call-graph shape against the CHARSAVE.GFF
    string is the next step.
  - **`roadmap.md` Phase 4 §save-inspect**: DS2 combat full
    schema row ticked; full DS2 schemas (character + item
    sub-blocks) remain queued.
  - **VERSION**: 0.3.0 -> 0.4.0.

- **`docs/dsun-exe-re.md`** gains a new §4 catalogueing the DS1
  palette I/O surface and partially decoding the animated-
  palette cycle routine. Pre-committed scope correction: with
  the cycle table's field-level semantics still open, this
  ships as docs-only; `region-render --animate` is not in this
  pass.
  - **Palette helper cluster at `0x1168c..0x116f3`**: four
    adjacent 16-bit far-call routines (`set_color`,
    `read_color_far`, `read_color_near`, plus a brightness /
    fade lookup at `0x116f4`). The lookup at `0x116f4` reads
    an 8-row × 256-word table in `cs:0x4..0xfff`; not a
    palette write directly but tied to colour state.
  - **Bulk routines**: `0x144dc` is `load_full_palette(buf)`
    with the canonical `>> 2` shift converting 8-bit to 6-bit
    DAC values. `0x288a4` is `write_palette_range(start,
    count, *buf)`, no shift, tight `lodsb / out` loop. `0x288c4`
    is the inverse `read_palette_range`. These are the obvious
    consumers of CMAT/CPAL (§3) and of the per-tick cycle
    update (§4.4).
  - **Cycle-table walker at `0x23075`** (partial decode).
    Identified the lone 32-bit `out dx, eax` site as part of a
    walker over an 8-byte-record table. Table base lives at
    `es:[0x6690]`, count at `[0x57c8]`, filter window
    `[0x5746]` / `[0x574a]`. The walker's match-handler at
    `0x23095` is the next pass: it's where palette rotation
    actually happens. Six of the eight bytes per record are
    still unidentified.
  - **DSO symbol cross-reference**: the cycle path maps onto
    five DSO symbols (`VGASetCycle`, `VGAResetCycle`,
    `VGAColorCycle`, `cycleshow`, `gCycleColor`). Table 4.6
    aligns them with the DSUN.EXE counterparts the §4.4
    findings expose.
  - **Why docs-only**. §4.4 surfaces the table shape but stops
    short of the record-field layout. Shipping a
    `region-render --animate` that guesses at the record
    fields would render plausibly wrong animations (correct
    palette indices, wrong period); shipping the doc with the
    honest "next step" pointer is the more useful artifact
    for now. `region-render v0.6.0` is reserved for when the
    record layout is fully decoded.
  - **`roadmap.md` Phase 4 §region-render animated colours**:
    still unchecked. The doc now points at the concrete next
    step rather than the open-ended "needs DSUN.EXE RE".

- **`tools/gpl-asm/` v0.5.0** ships the **author safety net**:
  better diagnostics when an authored listing is wrong, plus a
  static validator that catches whole classes of mistakes
  before the encoder bites. Default mode runs the validator
  before every encode; a failed validation aborts the run
  without writing output, so broken bytecode never reaches
  disk.
  - **Caret-style parse errors**. New public helpers in
    `gpl_asm::parse`: `format_with_caret(err, source)`,
    `error_line(err)`, `error_span(err, source)`. The binary
    wires `format_with_caret` into its text-mode parse path so
    a typo lands with a rustc-shaped pointer:
    ```
    parse error: line 12: bad opcode "ZZ"
      --> input:12:7
      |
    12 | 0024  ZZ  gpl_immed
      |       ^^
    ```
    `BadExpression` (the most common authoring failure) finds
    the offending token in the line and underlines it.
  - **Static `validate()` pass**. New module
    `gpl_asm::validate`. Three checks for v0.5.0:
    - **Branch target bounds**: `gpl jump` / `gpl local sub` /
      `gpl if` / `gpl while` / `gpl else` / `gpl wend` /
      `gpl ifcompare` whose literal target falls outside
      `[0, total_bytes)`. `gpl global sub` is skipped
      (cross-chunk by design).
    - **`Immediate14` overflow**. The on-the-wire encoding is
      actually 15 bits (`(cop & 0x7F) << 8 | b`), ceiling
      32767; the v0.5.0 work confirmed this against the corpus
      (real chunks carry values up to 32767). Anything beyond
      that is flagged.
    - **`RetVal` nesting depth**. Capped at
      `gpl_disasm::MAX_RETVAL_DEPTH` (= 4); deeper hand-built
      trees are guaranteed unencodable.
    `ValidationReport` returns all errors in one pass so the
    author sees the full picture, not the first-encountered
    issue.
  - **CLI surface**. Two new flags on the existing binary:
    `--validate-only` (parse + validate + exit, no encoding)
    and `--no-validate` (skip the default pre-encode check).
    Default mode validates first; on failure prints each error
    and aborts before writing output.
  - **Corpus**: 600 / 600 chunks across DS1+DS2 GPLDATA
    validate clean with zero false positives. The round-trip
    test still passes 600 / 600 byte-identical. New
    `tests/validate_smoke.rs` makes the no-false-positive
    invariant a regression test.
  - **`roadmap.md` Phase 5 §gpl-asm**: author-conveniences
    box ticked for the diagnostic + validator half; the
    macro / forward-reference / search-composition row rolls
    to v0.6.0+.
  - **VERSION**: 0.4.0 -> 0.5.0.

- **`tools/repro/` v0.1.0** ships the Phase 2 DOSBox-Staging
  repro harness, the prerequisite for every darkfix patch
  authoring + validation cycle from Phase 6 onward. The bar for
  v0.1.0 is **the harness pattern, not coverage**: one fixture,
  one game, plumbing other versions extend.
  - **Schema**. `bugs/<id>/bug.toml` holds the per-bug
    contract: `target_game`, optional `[setup].copy_files`,
    `[trigger].commands` (DOSBox `-c` lines), and `[expected]`
    pass criteria (`timeout_seconds`, `min_runtime_seconds`,
    `require_files`, `forbid_files`). Stdlib `tomllib` parses
    it; no third-party deps.
  - **Overlay discipline**. The harness mounts the game install
    as C: read-fall-through, then layers a per-run scratch
    `c-overlay/` on top. Every engine write (DSUN.EXE truncates
    `DARKRUN.GFF` on boot; the overlay catches it) lands in
    `/tmp/repro-<id>-XXXX/c-overlay/` and the `.games/` tree
    stays byte-identical. `verify-install` is the canary.
  - **Factory saves staged automatically**. DSUN.EXE expects
    `DARKSAVE.GFF` / `CHARSAVE.GFF` / `BACKSAVE.GFF` at C:\\;
    GOG ships them under `__support/save/`. The driver copies
    them into the overlay before launch so every fixture
    inherits a clean baseline; per-fixture `copy_files`
    overrides shadow factory copies on name collision.
  - **DOSBox driver**. `repro.py` builds the dosbox-staging
    command line (mounts, optional `imgmount` for DS2 CD audio,
    one `-c` per trigger command, `--exit`), enforces the
    wall-clock budget with `subprocess.wait(timeout=N)` and a
    SIGTERM-then-SIGKILL fallback, and evaluates pass criteria
    against globs under the D: scratch drive only.
  - **MEL audio gotcha documented**. With the factory
    `SOUND.CFG`, MEL aborts on `MIDI Detect Fail` / `DSP Detect
    Fail` and DSUN.EXE exits in <1 s (the same error family as
    `docs/known-bugs.md` §2.6). Running `sound_ds.exe` once
    writes a `SOUND.CFG` that gets MEL through detect; the
    `ds1-smoke` fixture ships that file as a 59-byte asset (no
    game IP, just driver-id + integer settings) and stages it
    via `[setup].copy_files`. The README has the recipe for
    cribbing it into new fixtures.
  - **Local-first**. DOSBox-Staging probes OpenGL at init, so
    `SDL_VIDEODRIVER=dummy` is unsupported; the harness is a
    real interactive tool that opens a window on the user's
    Wayland / X session. No CI / headless mode; not in scope
    for v0.1.0.
  - **`ds1-smoke` fixture**. DS1 boots into the main menu and
    survives 25+ s without DOSBox crashing on its own; the
    harness SIGTERMs at the 30 s budget. **PASS** end-to-end
    against a clean `.games/ds1/` GOG 1.10 install.
  - **DS2 path wired but not yet validated**. `configs/ds2.conf`
    issues `imgmount e <game-dir>/game.ins -t iso` for the CD
    cue sheet. No `ds2-smoke` fixture in v0.1.0 (needs a
    captured DS2 `SOUND.CFG`); queued for v0.2.0.
  - **Out of scope (intentional)**. Input automation, video
    capture (`scratch/<bug-id>/repro.mp4`), differential capture
    (run-with-patch vs without), CI / headless mode, DOSBox-X
    support, cross-platform. The roadmap's Phase 2 tickboxes
    are updated to reflect this: harness done, bug-trigger
    automation rolls into v0.2.0+.
  - **`roadmap.md` Phase 2**: 1 box ticked (DOSBox configured),
    1 partial (`save-state library` ships the schema +
    `ds1-smoke`), 2 remaining (recording wrapper, differential
    capture).
  - **Unlocks**. With the harness in place, future darkfix
    patch fixes get a one-command regression test from day one.

- **`tools/region-render/` v0.5.0** lands the DSUN.EXE RE pass
  for DS1 per-region palette selection and adjusts the default
  fallback to match what the engine actually does. The full
  write-up lives in [`docs/dsun-exe-re.md`](docs/dsun-exe-re.md).
  - **DSUN.EXE finding (DS1)**: located the per-region palette
    routine at file offset `0x56ad3..0x56b00`. The engine calls
    a single `load_resource(fourcc, id, far *buf)` helper twice
    in sequence: `CMAT[id]` first (a colour remap delta), then
    `CPAL[id]` as a fallback (a full 768-byte palette). The
    same `si` register supplies the id to both calls; `si` is
    a region-derived family id that resolves to 200 or 300 in
    `RESOURCE.GFF`. `PAL :1000` (the v0.4.x default) is not in
    the engine's region-render path; it's the menu / title
    palette.
  - **DSUN.EXE finding (DS2)**: zero CMAT or CPAL FOURCC
    pushes anywhere in DS2's `DSUN.EXE`. DS2 reverted to plain
    `PAL` lookups for region work; the engine uses a different
    `load_resource` entry point (`0128:04ab` vs. DS1's
    `0001:04a4`).
  - **Default-fallback change**: when no palette flag is set
    and the region GFF has no inline palette (i.e. the DS1
    case), v0.4.x fell back to `RESOURCE.GFF:PAL :1000` (which
    renders off-camera void as pink). v0.5.0 tries
    `RESOURCE.GFF:CPAL:200` first, falling back to `PAL :1000`
    only if `CPAL:200` isn't present. The CLI emits a one-line
    stderr note explaining which fallback resolved and how to
    override (`--palette-preset ds1-pink` brings back the
    v0.4.x look). DS2 regions are unaffected; their inline
    palette still wins before the fallback ladder runs.
  - **What's still open**: tracing the caller of the CMAT/CPAL
    load site back to where `si` is set would give us the
    per-region (not per-family) palette map. Animated palette
    colours (`VGAColorCycle` in the DSO symbol table) still
    need a separate RE pass. Both queued for a future release;
    docs/dsun-exe-re.md §4 lists the open items in priority
    order.
  - **New doc**: `docs/dsun-exe-re.md`, the maintainer's index
    into the engine binary. Covers binary layout, the shared
    `load_resource` calling convention, the CMAT/CPAL routine,
    and a reproducible recipe for the byte-pattern search that
    yielded the findings.
  - **VERSION**: 0.4.0 -> 0.5.0.

- **`tools/region-render/` v0.4.0** adds a `--palette-preset`
  flag for one-knob DS1 palette switching and documents the
  per-region-palette + animated-palette gaps honestly.
  - **New CLI flag** `--palette-preset <name>` resolves to a
    sibling `RESOURCE.GFF` chunk:
    - `ds1-pink` -> `PAL :1000` (v0.1.0 default, bright pink
      off-camera void)
    - `ds1-rust` -> `CPAL:200` (rusty-red Athasian look)
    - `ds1-deep-red` -> `CPAL:300` (darker variant)
    The preset takes precedence over `--palette` /
    `--palette-file` so modders reaching for "make my DS1
    region look right" have the obvious knob.
  - **Negative-result survey for per-region DS1 palette
    selection**: checked `RESOURCE.GFF`'s 2 `CMAT` chunks
    (undocumented in libgff; sizes 41,368 + 21,643 bytes,
    suggest substantial remap tables but no consumer code),
    `DARKRUN.GFF` (credits only), region GFFs themselves (no
    palette chunks), `dsun_music/region-tool` (expects
    explicit `--pal`), and `dso-online`'s symbol table (no
    obvious selection routine). Conclusion: per-region DS1
    palette selection needs `DSUN.EXE` reverse-engineering
    that's beyond v0.4.0; queued. README v0.4.0 section
    documents the trail.
  - **Animated palette colours** also need DSUN.EXE RE (the
    `dsun_music/region-tool` Java source carries a TODO at
    line 180); queued for v0.5.0+.
  - **VERSION**: 0.3.0 -> 0.4.0.

- **`tools/region-render/` v0.3.0** adds the **entity sprite
  layer**. ETAB records (8 bytes each) place sprites at
  `(x - ojff.x_offset, y - ojff.y_offset - y_offset)` with
  optional horizontal mirroring; each record's `ojff_number`
  resolves through `OJFF` to a `BMP ` chunk. Entities
  composite on top of walls + tiles; palette-index-0 pixels
  stay transparent.
  - **Per-game source files**: DS1 entity art lives in
    `SEGOBJEX.GFF` (2,775 OJFF + 2,419 BMP). DS2 entity art
    lives in `OBJEX.GFF` (4,479 OJFF + 3,727 BMP). CLI auto-
    detects the sibling file by name.
  - **New CLI flags**: `--entities-from <path>` (explicit
    source), `--no-entities` (skip the entity pass).
  - **New API**: `RegionMap::with_entities_from(&mut self,
    &Gff)`, `RegionMap::entity_sprite_count()`. New public
    fields: `entities: Vec<EntityRecord>`, `missing_entity_ids`,
    `entity_decode_failures`. New struct `EntityRecord { x, y,
    y_offset, mirrored, ojff_number }`.
  - **WallSprite gains `x_offset` / `y_offset` fields** to
    carry OJFF anchor metadata (walls leave both at 0; entity
    sprites use them to position correctly).
  - **`overlay_sprite_mirrored`** helper: flips the sprite
    horizontally during compositing for `byte5 & 0x80` records,
    per `RegionTool.java:346`.
  - **Corpus result** (GOG 1.10): 53 regions render with the
    full entity layer; **26,587 ETAB records, 8,223 distinct
    entity sprites loaded, 0 missing-entity ids, 0 OJFF/BMP
    decode failures**. With image-extract v0.2.0 at 99.95%
    bitmap coverage, region screenshots now match what a
    player sees in-game.
  - **Visual spot-check**: DS2 RGN001 renders the starting
    village with trees, mushrooms, stone arches, ruined
    castle, vegetable garden, hut interiors, all in correct
    position. DS1 RGN02 renders a desert biome with cacti,
    plants, NPC silhouettes, and a campfire structure.
  - **Out of scope**: animated palette colours (v0.4.0);
    per-region DS1 palette discovery (needs DSUN.EXE RE).
  - **VERSION**: 0.2.0 -> 0.3.0.

- **`tools/save-inspect/` v0.3.0** ships DS2 combat partial-
  decode upgrades and a new `diff` subcommand for comparing two
  CHARSAVE.GFFs. Full DS2 schema RE rolls to v0.4.0.
  - **DS2 combat partial decode**: v0.2.0 surfaced only the
    character name + raw hex. v0.3.0 decodes the DS1-shared
    prefix (the first 24 bytes — HP, PSP, char_index, id,
    ready/weapon/pack item indices, data_block,
    special_attack, special_defense) since hex inspection
    confirms those fields match DS1 byte-for-byte on the GOG
    1.10 corpus. The 6-byte stats block is heuristically
    located 8 bytes before the character-name field; the
    candidate is accepted only when all six bytes fall in the
    1..30 D&D 2e stat range. Empirical: this anchor matches
    every DS2 CHARSAVE record tested (HP 81, PSP 144, stats
    20/21/19/20/20/17 for Anathea, etc.).
  - **New `diff` subcommand**: `save-inspect.py diff a.GFF
    b.GFF` produces a structured JSON diff. Each change record
    carries a `path` (list of keys / indices through the
    summary), a `kind` (`value_changed`, `chunk_added`,
    `chunk_removed`, `type_changed`, `list_length_changed`,
    `added`, `removed`), and the before/after values. Goes
    through the existing `summarise` pipeline so DS1's full
    decoded fields show field-level diffs and DS2's partial-
    decode fields show the same partial surface.
  - **CLI restructure**: the binary still defaults to the
    v0.1.x `inspect` behaviour when called with a single file
    argument. The `diff` subcommand is dispatched explicitly
    by manual argv inspection (argparse subparsers couldn't
    coexist with the positional `file` argument cleanly).
    Both flows take `-o <path>` for file output and `--pretty`
    for indented JSON.
  - **New helpers**: `_diff_dict`, `_short`, `diff_summaries`,
    `_build_inspect_parser`, `_build_diff_parser`. Stdlib-only
    Python; no dependencies added.
  - **Out of scope**: full DS2 schema RE for the 66-byte
    character record + the remaining 7-byte tail on the
    49-byte combat record. Needs cross-reference saves.
    Tracked for v0.4.0.
  - **VERSION**: 0.2.0 -> 0.3.0.

- **`tools/region-render/` v0.2.0** ships the **wall layer**.
  `GMAP`'s low 5 bits per tile-byte are a wall-sprite index;
  each non-zero index looks up a `WALL` chunk at id
  `region_number * 100 + wall_index - 1` (per
  `RegionTool.java:274`). Walls composite on top of the
  background tile layer, bottom-aligned and horizontally
  centered, with palette-index-0 treated as transparent.
  - **WALL chunks live in `GPLDATA.GFF` on DS1** (664 chunks
    at ids 100..4509; corpus confirmed). The CLI default
    auto-detects the sibling `GPLDATA.GFF` next to the input
    region GFF and reads walls from there. `--walls-from
    <path>` overrides; `--no-walls` skips the layer entirely.
  - **DS2 wall story is TBD**: no `WALL` chunks observed in
    any DS2 GFF as of the GOG 1.10 corpus. The decoder runs as
    a no-op there; v0.2.x will revisit when the storage
    location surfaces.
  - **New API**: `RegionMap::with_walls_from(&mut self, &Gff)`
    indexes the WALL chunks referenced by this region's GMAP.
    `RegionMap::wall_sprite_count()` reports the count. New
    public fields: `gmap`, `region_number`, `missing_wall_ids`,
    `wall_decode_failures`. New const `GMAP_WALL_INDEX_MASK =
    0x1F`.
  - **Corpus**: 53 regions render with walls (35 DS1 + 18 DS2);
    350 distinct DS1 wall sprites loaded; 3 missing-wall ids
    (edge cases, harmless); 0 WALL decode failures.
  - **Out of scope for v0.2.0**: `ETAB` entity sprites,
    animated palette colours, per-region DS1 palette
    discovery, DS2 wall discovery.
  - **VERSION**: 0.1.0 -> 0.2.0.

- **`tools/image-extract/` v0.2.0** adds PLAN frame support and
  fixes PLNR's cross-byte bit-chomp. Corpus coverage jumps from
  67% (1,328 / 1,976 frames) to **99.95% (1,975 / 1,976)** —
  the lone non-decoded frame is a malformed chunk that fails
  header parsing.
  - **PLAN decoder**: bit-packed dictionary, no RLE.
    `bits_per_symbol`-bit symbols read big-endian from the
    post-dictionary stream; each symbol indexes the dictionary;
    dictionary value 0 means "transparent" (palette index 0
    in the output buffer). Format spec ported from
    `dsun_music`'s `ImageReading.readPlanarImageFrame`
    (MIT, attributed in code), originally RE'd from DSUN.EXE
    file offset 0x1A1B0.
  - **PLNR fix**: v0.1.0 used libgff's 4-bit-rotated chomp
    (`bit_offset = 4 - (bits_read % 8)`) which silently rejects
    boundary-crossing reads. 410 of 855 corpus PLNR frames hit
    this case; v0.1.0 reported them as `PlnrSplitBits` errors.
    v0.2.0 routes PLNR through the same standard big-endian
    bit chomper PLAN uses; every previously-skipped frame
    decodes cleanly. The RLE-state machine on top of the
    chomper is unchanged.
  - **New private helper**: `BigEndianBitChomper` reads `n`
    bits MSB-first across byte boundaries. Mirrors
    `dsun_music.BitChomper` with `ByteOrder.BIG_ENDIAN`.
    Reusable for any future bit-stream decode (e.g. when a
    different frame format shows up that doesn't bake in the
    libgff rotation).
  - **No CLI changes**. Existing `image-extract --kind ... --id
    ... -o frame.png` and `--all --output dir` invocations
    behave identically; they just decode more frames.
  - **Tests**: 5 unit + 1 corpus smoke (unchanged in shape);
    the corpus smoke's stat-printing now breaks down errors
    by kind so future regressions are visible. Decoded-frame
    count asserted in the new headline: 1,975 / 1,976.
  - **VERSION**: 0.1.0 -> 0.2.0.

- **`tools/gpl-asm/` v0.4.0** ships the label-relative `Editor`
  API and arbitrary user-chosen label names in the text parser.
  Together they make `gpl-asm` author-friendly: modders can
  reason about positions by name rather than raw byte offset.
  - **Editor extensions**:
    - `Editor::from_result` seeds a `name -> offset` map from
      `result.cfg.labels` (with the v0.4.6
      function-name decoration stripped). Persists through
      edits.
    - New methods: `label_offset(name)`, `labels()`,
      `add_label(name, at_offset)`,
      `insert_before_label(name, instr)`,
      `delete_at_label(name)`,
      `replace_at_label(name, with)`.
    - `EditError::NoLabel { name }` is the new error variant
      for missing labels.
    - Every edit operation shifts the label map by the same
      delta it applies to instruction offsets and branch
      targets; labels at the deleted offset are removed.
  - **Parser extensions**:
    - `collect_labels` accepts any ASCII identifier (letter or
      underscore head + alphanumerics / underscores) as a
      label declaration. User-chosen labels resolve to the
      offset of the instruction line that follows them.
    - `try_parse_label_ref` resolves any identifier present in
      the labels map, not just the `label_0x` / `entry_0x`
      prefixes. Variable parsing (`SHORT[id]`) runs first so a
      `GNUM[1]` token can never be confused with a label
      called `GNUM`.
    - `is_valid_label_ident` rejects names colliding with
      operator words (`and`, `or`), keyword tokens (`NAME`,
      `RETVAL`, `COMPLEX`, `INTRODUCE`, etc.), and variable
      shorts (`GNUM`, `LSTR`, ...). These would shadow real
      tokens during param parsing.
  - **Tests**: 3 new editor unit tests
    (`editor_seeds_labels_from_cfg`,
    `insert_before_label_shifts_label_offsets`,
    `user_chosen_label_resolves_via_add_label`) and 3 new
    parser unit tests (`user_chosen_label_in_branch_param`,
    `user_label_with_underscore_and_digits`,
    `parser_rejects_label_named_after_variable_short`).
    gpl-asm tests: 23 unit (was 17) + 2 corpus integration.
    Workspace total: 97 -> 103.
  - **Out of scope for v0.4.0**: macros / forward-reference
    syntax beyond `label:`; `gpl_search` raw_tail composition
    sugar in user-authored text. Queued for v0.5.0.
  - **VERSION**: 0.3.0 -> 0.4.0.

- **`tools/gpl-asm/` v0.3.0** ships **structural edits**. New
  `Editor` API wraps a `DisasmResult` and exposes
  `insert_instruction(before_offset, instr)`,
  `delete_instruction(at_offset)`, and
  `replace_instruction(at_offset, with)`. Branch targets and
  subsequent instruction offsets shift automatically.
  - **Module**: `tools/gpl-asm/src/edit.rs`. Exported as
    `gpl_asm::edit::{Editor, EditError, retarget_branches,
    can_edit_opcode}`.
  - **Branch retargeting**: works on the seven branch opcodes
    (`gpl jump` 0x12, `gpl local sub` 0x13, `gpl ifcompare`
    0x27 — param[1] only, `gpl if` 0x3E, `gpl else` 0x3F,
    `gpl while` 0x63, `gpl wend` 0x64). Targets `>=
    cutoff_offset` shift by `delta`; targets below are left
    alone. `gpl global sub` (0x14) intentionally not retargeted
    (its target offset is in a different chunk).
  - **Length recompute via the encoder**: `Editor` calls
    `encode_instruction` on the newly-built instruction to count
    its bytes, so the user doesn't manually compute lengths.
  - **`Editor::make_instruction(opcode, params, raw_tail)`**
    and **`make_simple(opcode)`** are convenience builders that
    set `mnemonic` / `offset` / `length` correctly.
  - **Order-of-operations**: replace swaps the new instruction
    in BEFORE retargeting, so the new instruction's own branch
    params participate in the shift (matters when a patch
    inserts a forward-jump whose target shifts with the insert).
  - **Tests**: 6 new unit tests
    (`insert_endif_at_start_shifts_following`,
    `insert_shifts_branch_target_after_insertion_point`,
    `delete_shifts_branch_target_down`,
    `replace_with_same_length_keeps_offsets`,
    `replace_with_longer_shifts_following_and_branches`,
    `missing_offset_errors`). gpl-asm tests: 17 unit (was 11)
    + 2 corpus integration. Workspace total: 91 -> 97.
  - **Out of scope**: label-relative inserts; constructing
    Search-shaped instructions with raw_tail bytes. Both queued
    for v0.4.0.
  - **VERSION**: 0.2.1 -> 0.3.0.

- **`tools/gpl-asm/` v0.2.1 + `tools/gpl-disasm/` v0.4.6** close
  the labelled-text round-trip to **600 / 600 byte-identical**.
  v0.2.0 hit 456/456 of the `--no-labels` form; v0.2.1 handles
  the default (labelled) form including Search chunks.
  - **`gpl-disasm v0.4.6` changes**:
    - `render_text(&DisasmResult, labels_on: bool) -> String`
      moves into the library (was in the binary).
    - Branch params strip the `" (function_name)"` decoration
      from label names. Declaration lines keep the full
      decorated form. Modders still see the function name on
      the label declaration; the param stays a clean
      identifier the parser can round-trip.
    - `target_aliases`-redirected branches (pointing at a
      `gpl else` opcode) render as raw integers in the param.
      The labelled form was lossy for those cases; the
      integer is the round-trippable byte-level source of
      truth. The label declaration still appears at the post-
      else continuation offset.
    - `Instruction::Display` and `render_text` emit a
      `; raw_tail=HEX` trailer when the instruction has a
      `raw_tail` (top-level `gpl_search`).
    - `Expression::RetVal::Display` emits a `raw_tail=HEX`
      sentinel inside `RETVAL(...)` when `inner_raw_tail` is
      set (nested-Search case).
  - **`gpl-asm v0.2.1` changes**:
    - Pre-scan pass for `label_0xNNNN:` /
      `entry_0xNNNN[ (function_name)]:` declarations, building
      a `name -> offset` map. Function-name decoration is
      stripped (matching the v0.4.6 renderer).
    - Branch params that name a label resolve to
      `Immediate14 { value: offset }` via the map.
    - `; raw_tail=HEX` trailers parse into
      `Instruction.raw_tail`.
    - `raw_tail=HEX` sentinels inside `RETVAL(...)` parse
      into `Expression::RetVal::inner_raw_tail`.
    - Sign-vs-operator heuristic for `-` is now state-aware:
      `-DIGIT` is a sign on a signed integer literal only at
      the start of an expression sequence (or after an
      open-paren / operator). After a value-producing token
      (close-bracket, close-paren, end of a variable
      identifier, end of an integer literal), `-DIGIT` is an
      op followed by a positive value. This is needed for the
      unspaced RetVal rendering: `GNAME[33]-2i8` is three
      tokens (`Variable`, `Op::Minus`, `ImmediateByte`), not
      a `Variable` followed by a signed literal.
  - **Corpus test**: `tests/text_roundtrip.rs` no longer skips
    Search-containing chunks and uses the labelled form
    (`render_text(&result, true)`). **600 / 600** byte-identical
    round-trip. The existing JSON-mode corpus test
    (`tests/corpus_roundtrip.rs`) still passes 600/600.
  - VERSIONs: `gpl-disasm` 0.4.5 -> 0.4.6; `gpl-asm` 0.2.0 ->
    0.2.1. Workspace tests: 91 (unchanged).

- **`tools/gpl-asm/` v0.2.0** adds a **text-listing parser**.
  Modders can edit `gpl-disasm`'s human-readable output and
  reassemble. Same encoder, new front-end.
  - **`gpl_asm::parse(&str) -> Result<DisasmResult, ParseError>`**
    is the new entry point. Accepts the exact format
    `Instruction::Display` produces with `--no-labels`:
    `OOOO  HH  MNEMONIC               <params>  ; trailer`,
    one instruction per line. Comments (`;`-prefixed) and label
    declaration lines (`label_0x...:`, `entry_0x...:`) are
    ignored; v0.2.x will resolve labels.
  - **Expression parser**: every Display form is invertible.
    Integer literals (`5`, `5i8`, `5i32`, `-5i8`), strings
    (`"escaped"` / `INTRODUCE` / `UNCOMPRESSED`), variables
    (`GNUM[1]`, `GNUM+[300]`, ...), `NAME(-5)`, `RETVAL(mnem
    args)`, `COMPLEX(0xtag, ctx, depth=N, [elements])`, parens,
    and the 15 binary operators (longest-match: `&~` beats `&`,
    `>=` beats `>`, etc.). Sign vs operator on `-`: `-DIGIT` is
    a sign (no surrounding spaces); ` - ` is the op (the
    renderer always wraps top-level ops in spaces). `+` is
    always an operator (i8/i32 literals never render with an
    explicit `+`).
  - **CLI**: input format is auto-detected from the file
    extension (`.json` -> JSON, anything else -> text);
    `--json` / `--text` force a mode. `--all-from <dir>` reads
    both `.json` and `.asm`/`.txt` files per-entry, encoding
    each to a matching `.bin`.
  - **Text-roundtrip corpus** (GOG 1.10 DS1+DS2 GPLDATA, 600
    aligned chunks): `bytes -> disassemble -> render text ->
    parse -> encode` is byte-identical for **456 / 456**
    non-Search chunks. The 144 Search-containing chunks are
    skipped — same reason as v0.1.0 had to skip them in JSON
    mode before v0.1.1: their `raw_tail` side bytes aren't in
    the text format. v0.2.x adds a `; raw_tail=hex...` trailer
    annotation to close that gap.
  - **Encoder relaxation**: dropped a `LengthMismatch`
    sanity-check in `encode`. The parser can only estimate
    `DisasmResult.total_bytes` by re-doing the encoder's work;
    the corpus round-trip already catches real encoder bugs by
    comparing against the source bytes, so the redundant check
    was making the encoder over-strict on parsed input. A
    `debug_assert_eq!` still fires in debug builds when the
    field disagrees with the encoded length.
  - **Tests**: new `tests/text_roundtrip.rs` (1 test, 456
    chunks asserted byte-identical). Existing JSON-mode corpus
    round-trip (`tests/corpus_roundtrip.rs`) still passes
    600/600.
  - **VERSION**: 0.1.1 -> 0.2.0.

- **`tools/gpl-asm/` v0.1.1 + `tools/gpl-disasm/` v0.4.5** close
  the corpus round-trip to **600 / 600 byte-identical**. v0.1.0
  shipped at 456/600 because `gpl_search` (0x33) has side bytes
  (a 2-byte range argument plus per-iteration field / type / 0x53
  markers) that the disasm IR didn't capture. v0.4.5 adds two
  optional preservation fields and v0.1.1 consumes them.
  - **New `gpl-disasm` fields** (both `#[serde(default,
    skip_serializing_if = "Option::is_none")]` so JSON for
    non-Search instructions is byte-identical to v0.4.4):
    - `Instruction.raw_tail: Option<Vec<u8>>` — top-level Search.
    - `Expression::RetVal::inner_raw_tail: Option<Vec<u8>>` —
      Search nested inside `GPL_RETVAL` (143 of 144 cases).
    Captured by `read_instruction_params_with_depth` from the
    bytes consumed past the first expression. `params[1..]`
    still gets the trailing expressions populated for
    downstream text/dialog consumers; the reassembler uses
    `params[0] + raw_tail` exclusively.
  - **Encoder logic** in `gpl-asm`: when handling
    `ParamSpec::Search` (either top-level or via the `RetVal`
    branch's inner-Search case), write `opcode +
    encode(params[0]) + raw_tail`. If `raw_tail` is None — i.e.
    the JSON came from a pre-v0.4.5 disassembler — the encoder
    errors with a clear "needs gpl-disasm v0.4.5+" message
    rather than silently emitting wrong bytes.
  - **Corpus test** in `tests/corpus_roundtrip.rs`: no more
    Search skip-list. Asserts every aligned GPL/MAS chunk in
    DS1+DS2 GPLDATA round-trips byte-identical. **600 / 600.**
  - **Breaking API change** (additive on data, additive on
    pattern surface): `Expression::RetVal` pattern matches need
    a `..` rest pattern or to name `inner_raw_tail`. Internal
    `gpl-disasm` Display impl and tests updated; external
    consumers in this workspace (`dialog-extract`,
    `region-render`, `image-extract`) don't pattern-match
    `RetVal` so they're unaffected.
  - VERSIONs: `gpl-disasm` 0.4.4 -> 0.4.5; `gpl-asm` 0.1.0 ->
    0.1.1.

- **`tools/gpl-asm/` v0.1.0** ships (new Rust crate; Phase 5
  first deliverable). Round-trip reassembler that takes the
  `gpl-disasm --json` output and emits byte-identical bytecode.
  The other half of the GPL loop with `gpl-disasm`.
  - **Corpus** (GOG 1.10 DS1+DS2 GPLDATA, 600 GPL/MAS chunks):
    **456 chunks round-trip byte-identical**; 144 are skipped
    because they contain `gpl_search` (0x33), whose side bytes
    aren't captured in `gpl-disasm`'s v0.4.4 IR. 0 mismatches,
    0 encode failures on the non-skipped set.
  - **`encode(&DisasmResult) -> Vec<u8>`** is the load-bearing
    API. `encode_instruction` and `encode_expression` cover
    piecewise use; `pack_compressed_string` packs the 7-bit
    bitstream that complements gpl-disasm v0.4.3's lossless
    decoder. `EncodeError` enumerates the rejection cases
    (`BestEffortInstruction`, `UnsupportedOpcode`,
    `BadParamShape`, `UnknownToken`, `LengthMismatch`).
  - **Special-shape opcode handlers**:
    - `gpl_load_variable` (0x16, 27,394 occurrences across
      DS1+DS2): re-emit the datatype byte from
      `Variable.var_kind`/`extended` or from `ComplexAccess.tag`.
    - `gpl_menu` (0x48, 1,314 occurrences): emit the name
      expression + 3-expression entries + the 0x4A terminator.
    - `gpl_setrecord` (0x40, 139 occurrences): emit the
      access-complex body raw + one trailing expression.
    - `gpl_log` (0x2C, 0 occurrences): emit one packed-string
      payload. Encoder present for completeness.
    - `gpl_search` (0x33, 2 top-level + 143 RETVAL-nested):
      rejected. v0.1.x adds preservation.
  - **CLI**: `gpl-asm chunk.json -o chunk.bin` for single
    chunks; `gpl-asm --all-from disasm/ -o asm/` for bulk
    re-encoding of every `*.json` in a directory. Matches the
    `--all` shape used by `gpl-disasm` and `image-extract`.
  - **Tests**: 11 unit (per-Expression-variant round-trips,
    7-bit packed-string round-trip including a `\t`-preserving
    case, `Op::to_byte` and `VarKind::to_tag` inverses) + 1
    corpus round-trip (`tests/corpus_roundtrip.rs`). The
    corpus test runs through every aligned GPL/MAS chunk in
    `.games/ds1/GPLDATA.GFF` and `.games/ds2/GPLDATA.GFF`,
    skips `gpl_search`-containing chunks, and asserts
    byte-identical against the source on the rest.
  - **VERSION**: 0.1.0. Workspace test count: 78 + 11 + 1 =
    **90**.

- **`tools/gpl-disasm/` v0.4.4** adds `Deserialize` impls on
  every public Serialize-able type so the new `gpl-asm` crate
  can consume the same JSON output. Mechanical addition across
  `DisasmResult`, `Instruction`, `Expression`, `Cfg`,
  `BasicBlock`, `Edge`, `TerminatorKind`, `EdgeKind`,
  `CrossChunkCall`, `UnresolvedEdge`, `GlobalCfg`, `ChunkNode`,
  `CrossEdge`, plus leaf enums `VarKind`, `Op`, `StringSubType`.
  - **Two side-effect type changes** (both for
    deserialisability of the static-string fields):
    - `Expression::RetVal::inner_mnemonic`:
      `Option<&'static str>` -> `Option<Cow<'static, str>>`.
      Mirrors the v0.4.2 outer-mnemonic change. JSON output is
      unchanged.
    - `UnresolvedEdge.reason`: `&'static str` ->
      `Cow<'static, str>`. Internal constructors use
      `Cow::Borrowed`. JSON output unchanged.
  - **Public API additions**: `VarKind::from_tag` and
    `Op::from_byte` are now `pub` (were crate-private). New
    `VarKind::to_tag(self) -> u8` and `Op::to_byte(self) -> u8`
    methods round out the inverse pair, used by `gpl-asm`'s
    encoder.
  - **VERSION**: 0.4.3 -> 0.4.4.

- **`tools/gpl-disasm/` v0.4.3** makes the 7-bit packed-string
  decoder lossless. Prerequisite for `gpl-asm` v0.1.0's
  byte-identical round-trip reassembler.
  - **Behaviour change**: `decode_compressed` used to map every
    7-bit value outside `0x20..=0x7E` to `0x20` (space) for
    display safety. v0.4.3 emits every byte verbatim. The
    original chunks ship real formatting codes (TAB, line feed)
    inside packed-string payloads; the lossy mapping made
    byte-identical re-encoding impossible.
  - **Corpus impact**: 19 strings across DS1+DS2 GPLDATA (0.05%)
    now decode to their original byte sequence rather than to
    a sequence of spaces. The visible glyph for a TAB or LF
    when rendered as text is still close to a space, so
    consumers may not notice the difference; JSON consumers see
    `\u00XX` escapes for those bytes.
  - **Spike methodology**: a standalone Python encoder
    prototype (see commit's pre-implementation work for
    gpl-asm v0.1.0) round-tripped 36,700 / 36,719 (99.95%) of
    corpus `ImmediateString` payloads byte-identical before this
    change; the 19 misses were exactly the lossy-decode cases.
    After v0.4.3 the encoder algorithm has the correct byte
    sequence to reproduce on every string; the formal corpus
    round-trip test lands with gpl-asm v0.1.0's
    `tests/corpus_roundtrip.rs`.
  - **Tests**: 1 new unit test
    (`read_text_compressed_preserves_non_printable_bytes`)
    pinning the lossless contract on a payload that encodes
    `\x09` (TAB). gpl-disasm test count: 45 unit + 2
    integration (was 44 + 2).
  - **VERSION**: 0.4.2 -> 0.4.3. Cargo.toml synced.

- **`tools/dialog-extract/` v0.4.0** resolves LSTRING references
  and expands `gpl global sub` calls inline. Combined effect on
  the corpus: **893 unresolved LSTRING refs (v0.3.0) drop to 32
  unresolved (v0.4.0), a 96.4% reduction**. DS1: 475 -> 25
  (94.7%); DS2: 418 -> 7 (98.3%).
  - **LSTR-slot resolution (path-aware)**: scripts populate one
    of 10 runtime `LSTR` slots (`MAXLSTRINGS = 10` per libgff
    `include/gff/str.h`) via `gpl_string_copy` (0x0A) writes;
    `gpl_menu` / `gpl_print_string` reads then pull the slot's
    contents. v0.4.0 tracks slot writes path-by-path inside
    `_walk_tree` alongside the existing `speaker_state`. Each
    block node gains a `lstr_state_entry` snapshot. Source
    kinds recorded:
    - `inline`: param[1] was an immediate literal. Direct
      resolution.
    - `gstring`: param[1] was a `GSTRING[id]` variable; recurses
      through `--text-source`.
    - `lstring`: param[1] was another LSTR slot; chained
      resolution with cycle protection.
    - `computed`: anything else (accumulator math, complex
      record access). Read resolves to `None` so the slot
      doesn't silently fall back to a stale value.
  - **Linear-scan baseline** for the flat `strings` list: a
    single forward pass over each chunk's instructions builds a
    chunk-level snapshot. Less accurate than path-aware (~80%
    vs ~96%) but needs no CFG context, so it works for non-tree
    consumers.
  - **LSTR over-count bug fix**: v0.3.0 emitted the `LSTR`
    *destination* of every `gpl_string_copy` as a bogus
    "unresolved LSTRING ref". v0.4.0 skips param[0] for that
    opcode. Flat-list size shrinks by exactly the LSTR-write
    count (220 DS1, 319 DS2).
  - **Inter-chunk dialog tree walking**: `gpl global sub`
    (0x14) call sites now expand inline as `cross_chunk_call`
    subtrees under the calling block's `children`. v0.4.0
    builds an in-memory chunks index keyed on `(kind, id)`,
    walks the callee from `target_offset` with the caller's
    `speaker_state` and `lstr_state` flowed through (shallow
    copies), and recurses with a `cross_chunk_visited` set to
    break cycles. Modifications inside the callee do NOT
    propagate back to the caller's continuation: dialog-extract
    is not a runtime simulator.
    - Resolved expansions: 666 (DS1) + 806 (DS2) inlined call
      trees.
    - Cycle markers: 223 (DS1) + 192 (DS2) recursive references
      properly halted.
    - Other unresolved: 4 + 14 `target_offset_not_a_block_leader`
      (mid-function calls), 2 `callee_not_loaded` (cross-GFF
      calls), 0 `depth_cut` on the corpus.
  - **New types in the JSON output**:
    - Per `block` node: `lstr_state_entry: dict[int, dict]`
      snapshot.
    - Per `block` node `children`: optional
      `{kind: "cross_chunk_call", at, target_chunk,
      target_offset, target_file_id, target_label, subtree, ...}`
      with `unresolved: true` + `reason` when the callee can't
      be expanded.
  - **Headline corpus** (GOG 1.10): 600 / 600 chunks build a
    tree; DS1 17,699 string records (was 17,926); DS2 28,354
    (was 28,685). The drop is the v0.4.0 over-count fix
    removing 220 + 319 = 539 phantom unresolved entries.
  - Stdlib-only Python; no new dependencies. Reuses gpl-disasm's
    per-chunk `cross_chunk_calls` metadata (indexed since
    gpl-disasm v0.3.0) for the inter-chunk walker.
  - Roadmap Phase 4 dialog-extract v0.4.0 box ticked.

- **`tools/region-render/` v0.1.0** ships (new Rust crate; closes
  Phase 4). Renders a region GFF's background tile layer
  (`RMAP` for DS1 or `MAP ` for DS2) as a 2048 x 1568
  palette-indexed PNG. Walls (`GMAP` lower 5 bits + `WALL`
  chunks), entities (`ETAB` + `OJFF`), animated colours, and
  GMAP flag visualisation are all v0.2+ work.
  - **Ports from `JohnGlassmyer/dsun_music`** (MIT,
    `region-tool/RegionTool.java`):
    - Region geometry constants (128 x 98 tiles, 16 x 16 px).
    - `RMAP` / `MAP ` layout (row-major byte grid, each byte =
      TILE resource id).
    - Palette discovery rule (inline first, explicit `--pal`
      override second).
  - **Reuses `image-extract`**: `Palette::from_bytes` for the
    768-byte `PAL `/`CPAL` chunks; `Bitmap::from_bytes` +
    `decode_frame(0)` for each `TILE`. v0.1 expects 16 x 16
    frames and treats anything else as a soft decode failure.
  - **Soft-decode of malformed TILEs**: DS2 region GFFs ship a
    15-byte sentinel `TILE` id `0` that can't be parsed as a
    bitmap. v0.1 records these as `TileDecodeFailure` rows
    rather than hard-failing; the sentinel isn't referenced by
    `MAP ` so it has no visible effect.
  - **CLI**: `region-render <RGN.GFF> -o out.png` with optional
    `--palette <gff>:<KIND>:<id>` or `--palette-file <raw>`. The
    DS1 default fallback is `RESOURCE.GFF:PAL :1000` in the same
    directory as the input.
  - **Library**: `RegionMap::from_gff(&Gff, Palette)`,
    `RegionMap::render_indexed() -> Vec<u8>`,
    `RegionMap::write_png(path)`, plus `inline_palette(&Gff) ->
    Option<Palette>` for callers building their own resolution.
  - **Tests**: 6 unit + 1 corpus smoke. The corpus test renders
    every `RGN*.GFF` in DS1+DS2 and asserts the rendered buffer
    is exactly `REGION_PIXEL_WIDTH * REGION_PIXEL_HEIGHT` bytes;
    no panics required.
  - **Corpus results** (GOG 1.10): 53 regions rendered (35 DS1 +
    18 DS2). **0 missing-tile bytes** across the whole corpus
    (every RMAP / MAP byte resolved to a present TILE chunk in
    the same GFF). 18 soft TILE decode failures, one per DS2
    region (the sentinel id 0 case).
  - **DS1 palette caveat surfaced**: DS1 stores only four
    palettes in `RESOURCE.GFF` and none are keyed on region
    number. v0.1 defaults to `PAL :1000`; the rendered output is
    structurally correct but the "off-camera" tile cells use the
    palette's high-index colours (visibly pink/magenta). The
    interior playable area renders with plausible terrain
    colours. Per-region palette discovery is queued for v0.2+.
  - **Docs**: `docs/file-formats.md` expanded with a "Region
    geometry" subsection covering RMAP/MAP/GMAP/TILE/PAL/ETAB
    layouts (deferred sections are flagged for v0.2+).
  - Roadmap Phase 4 region-render bullet ticked; Phase 4 is now
    done.

- **`tools/gpl-disasm/` v0.4.2** wires opcode-mnemonic overrides
  through to text and JSON output. The `syms/opcodes.toml`
  catalogue loaded since v0.4.0 is now applied: a row of the form
  `[opcodes."0xNN"] name = "..."` replaces the libgff default
  mnemonic for that opcode byte everywhere the disassembler
  emits a mnemonic. Defaults remain for any byte without an
  entry. No new CLI flags; existing `--syms` / `--no-syms` still
  control catalogue loading.
  - **Internal change**: `Instruction.mnemonic` is now
    `Option<Cow<'static, str>>` (was `Option<&'static str>`).
    Default path is zero-allocation (`Cow::Borrowed` from the
    static `OPCODES` table); `Cow::Owned` after an override
    applies. JSON shape is unchanged (serde serializes Cow as a
    string). The inner-mnemonic field inside `Expression::RetVal`
    stays `&'static str` for v0.4.2; extending overrides there
    is a follow-up if curation needs it.
  - **New API**: `Symbols::apply_to_mnemonics(&mut DisasmResult)`
    iterates instructions, looks up `format!("0x{:02x}", opcode)`
    in `self.opcodes`, and rewrites the mnemonic on hit. The
    binary calls it right after `apply_to_labels` in all three
    paths (`single-chunk`, `--all`, `--global-cfg`).
  - **`syms/opcodes.toml` ships empty by design.** The file
    header now documents the curation rule explicitly: a row
    lands only when the libgff mnemonic is unambiguously wrong
    (cross-checked against in-game behavior or DSO debug-symbol
    context), or when the alternate name is materially clearer
    and still accurate. Cosmetic aliases (e.g. `gpl tport` →
    `gpl teleport`) do not meet the bar. Honest finding from
    this release: libgff's `gpl_commands` and soloscuro-archive's
    `gpl_lua_operations[]` are character-identical, and the DSO
    v1.0 symbol table names callbacks (`ExecuteGpl`,
    `GplTileCheck`), not opcode-byte handlers. The plumbing
    lands without seed rows; the unit tests prove the override
    pipe works.
  - **Tests**: 4 new unit tests
    (`symbols_apply_to_mnemonics_overrides_known_opcode`,
    `_leaves_unrelated_alone`,
    `_preserves_none_for_unknown_byte`,
    `symbols_load_opcodes_from_toml`). gpl-disasm test count: 44
    unit + 2 integration (was 40 + 2).
  - **VERSION file**: bumped from `0.2.1` to `0.4.2`. The
    `VERSION` file silently fell behind `Cargo.toml` between
    v0.3.0 and v0.4.1; per `docs/versioning.md` it is the single
    source of truth, so this release catches it back up. No
    behavioural change.
  - Roadmap Phase 3 opcode-mnemonic-override bullet ticked.

- **`tools/gpl-disasm/` v0.4.1** adds inter-chunk control-flow
  analysis. New `--global-cfg <path>` flag emits a whole-file
  callgraph where nodes are GPL/MAS chunks and edges are the
  `gpl global sub` (0x14) cross-chunk call sites we've been
  indexing since v0.3.0. Output is DOT by default or JSON with
  `--json`; `-` writes to stdout. Mutually exclusive with the
  single-chunk path.
  - **New types** (`lib.rs`): `GlobalCfg` (source, nodes, edges),
    `ChunkNode` (kind, chunk_id, entry/block/in/out counts),
    `CrossEdge` (from_kind, from_chunk, from_offset, to_chunk,
    to_offset, optional from/to function names), `ChunkSummary`
    (per-chunk input to the builder).
  - **Symbol propagation**: when the caller's `from_offset`
    falls inside an entry-point range whose `functions.toml`
    row exists, that name is set as `from_function_name`. When
    the callee's `to_offset` matches an entry point in the
    destination chunk and a symbol exists, `to_function_name`
    is set. JSON consumers see the resolved names directly.
  - **Corpus** (GOG 1.10):
    - DS1 GPLDATA: 250 chunks, 587 inter-chunk edges.
    - DS2 GPLDATA: 350 chunks, 797 inter-chunk edges.
    - Combined: 1,384 edges — exactly the figure the v0.3.0
      corpus soundness test has been reporting since the cross-
      chunk indexing landed.
  - **Most-called chunk in DS1**: GPL-74 with 169 inbound
    calls and 2 outbound. The shape suggests it's a heavily-
    shared utility worth naming first in the curation backlog.
  - **Tests**: 2 new unit tests
    (`global_cfg_aggregates_inbound_outbound_counts`,
    `global_cfg_annotates_edges_with_symbols`). gpl-disasm
    test count: 40 unit + 2 integration.
  - **DOT renderer**: self-loops (a chunk calling itself via
    `global sub` — we observe a few of these, e.g. GPL-106 /
    GPL-107 in DS1) get a dashed-gray style to distinguish them
    from inter-chunk edges. Each chunk node carries inbound /
    outbound counts in its label.
  - Roadmap Phase 3 inter-chunk-CFG bullet ticked.

- **`tools/gpl-disasm/` v0.4.0** ships symbol-import plumbing.
  Hand-curated TOML catalogues at `tools/gpl-disasm/syms/`
  decorate function-entry labels in both text and JSON output.
  When a `functions.toml` row matches a chunk's entry point,
  the rendered label becomes `entry_0xNNNN (function_name)`.
  Downstream consumers (`dialog-extract` in particular) inherit
  the enriched labels through the JSON without code changes.
  - **Schema**: `syms/functions.toml` is a list of `[[function]]`
    tables with `file` (GFF basename, case-insensitive),
    `kind` (4-char FOURCC), `chunk_id`, `offset`, `name`, and
    optional `notes`. `syms/opcodes.toml` reserves the opcode-
    override slot for v0.4.1+; the loader reads it but the
    renderer does not yet rewrite mnemonics.
  - **CLI**: new `--syms <dir>` flag (explicit catalogue path)
    and `--no-syms` flag (disable lookup entirely). Default
    resolves `tools/gpl-disasm/syms/` next to the binary by
    walking up the workspace tree.
  - **Starter catalogue**: 2 verified entries for DS1 GPLDATA
    chunk 1 (`iniya_first_meeting` at 0x0001 and
    `iniya_dialog_menu` at 0x0095), seeded from the
    unambiguous "Free! Finally free!" cross-reference. The
    catalogue grows over time as more function purposes are
    cross-checked.
  - **New types** (`lib.rs`): `Symbols`, `OpcodeSymbol`,
    `FunctionSymbol`, `SymbolsLoadError`, plus
    `Symbols::load_from_dir`, `Symbols::function_name`, and
    `Symbols::apply_to_labels` for mutating a `Cfg` in place.
  - **Tests**: 2 new unit tests
    (`symbols_apply_to_entry_labels_only`,
    `symbols_case_insensitive_file_match`); gpl-disasm test
    count: 38 unit + 2 integration.
  - **Workspace**: adds `toml = "0.8"` as a workspace dep
    (pre-approved per spec §7a as format I/O).
  - Roadmap Phase 3 v0.4.0 symbol-import bullet ticked.

- **`tools/dialog-extract/` v0.3.0** adds a CFG-aware
  `dialog_tree` field per chunk alongside the existing flat
  `strings` list. Built on top of `gpl-disasm v0.3.1`'s CFG. The
  tree is a recursive structure of `block`, `if`, `ifcompare`,
  `loop`, `goto`, `revisit`, and `depth_cut` nodes mirroring the
  chunk's control flow.
  - **Block nodes** carry `lines` (the same string records v0.2.0
    emits, now also tagged with a `speaker_state` snapshot),
    `gpl_refs` (`local sub` / `global sub` call sites with
    `at` / `target` / `target_label` / `file_id`), a
    `speaker_state_entry` snapshot, and `children` for the
    block's terminator.
  - **If detection** picks up the if-with-else case by checking
    whether the then-path ends in a `gpl else` terminator;
    when it does, the matching endif (the else's own param
    target) becomes the join offset for an `else` subtree
    walked from the if's not-taken edge.
  - **Ifcompare nodes** surface `gpl ifcompare`'s case-value
    pattern (the comparison literal as a rendered param). The
    chained switch dispatch in DS scripts (e.g. DS1 GPL-199)
    now reads as nested `ifcompare` nodes with `match` and
    `miss` subtrees.
  - **Loop nodes** wrap `gpl while` bodies; the implicit
    backward `gpl wend` edge is not modelled as a child (just
    stops the recursive walk).
  - **Discovered entries**: each chunk's `cfg.entry_points`
    only includes the chunk start and locally-observed
    `gpl local sub` targets. Most block leaders are reached
    instead by `gpl global sub` from another chunk; the v0.3.0
    walker discovers these as additional top-level entries
    after the declared walks finish, so every block leader's
    dialog is visible. (Full inter-chunk CFG walking is
    `gpl-disasm v0.4.1` work.)
  - **Speaker-state tracking** is deliberately heuristic:
    only `gpl setother` (0x41) and `gpl setthing` (0x49) are
    tracked. We do NOT claim a line is spoken by anyone; the
    snapshot just surfaces the engine context (which NPC was
    last set) at the time of each line.
  - **Corpus** (GOG 1.10): 600 / 600 chunks build a tree.
    46,611 lines total across 4,229 declared + 15,027
    discovered entry-point walks (exact match to v0.2.0's
    flat-strings count, confirming the tree captures every
    line). 7,438 `revisit` cuts (shared sub-paths between
    entries). 0 invariant violations (every line / gpl_ref
    offset resolves to a chunk instruction).
  - **Back-compat**: the existing `strings` per-chunk field
    stays byte-identical. v0.2.0 consumers parse the new JSON
    unchanged; the `dialog_tree` field is additive.
  - Stdlib-only Python; no new dependencies. The walker is in
    `tools/dialog-extract/dialog-extract.py` as `build_dialog_tree`
    and `_walk_tree`. Tested via inline corpus validation
    (run-once script in the README's empirical-results notes;
    no formal test framework — matches the other Python tools
    in this repo).
  - Roadmap Phase 4 dialog-extract v0.3.0 box ticked.

- **`tools/gpl-disasm/` v0.3.1** fixes the `gpl else` (0x3F)
  control-flow edge. v0.3.0's CFG treated the else opcode's
  offset as a first-class block leader and routed `gpl if` /
  `gpl ifcompare` / `gpl while` not-taken edges directly to it.
  In the real runtime the else opcode is dual-mode: when reached
  by jump (the if-false path), it behaves as a no-op and
  control continues past the opcode bytes into the else-body;
  when reached by fall-through (from the matching then-block),
  it executes an unconditional jump to its param (the matching
  endif). v0.3.0's model missed the entire else-body on the
  false path.
  - **Scope of impact**: 5,471 of 20,281 conditional branches
    in the DS1+DS2 corpus (27%) landed on a `gpl else` opcode
    and were affected. dialog-extract v0.2.0's flat-string
    output was unaffected (no CFG dependency yet);
    dialog-extract v0.3.0+ depends on this fix.
  - **CFG model**: a new `redirect_past_else` helper rewrites
    any branch target whose offset equals a `gpl else` opcode
    to `else_offset + else_length`. The else opcode is no
    longer a block leader; it becomes the terminator
    instruction of its preceding block (with
    `TerminatorKind::UnconditionalElse` → param). Applied to
    leader collection AND to `successors_for` edge wiring so
    both views stay consistent.
  - **Rendering**: a new `Cfg.target_aliases` map preserves the
    "raw branch param → labeled name" lookup. `gpl if 80` (when
    80 is the offset of a `gpl else`) renders as
    `gpl if label_0x0053` (the else-body offset). The else
    opcode itself does NOT get a spurious `label_*:` line
    prepended; only true block leaders do.
  - **Corpus**: 600 / 600 chunks remain aligned; 66,028
    successor edges now resolve to instruction boundaries (was
    71,403; the difference is the ~5,400 Fallthrough edges that
    formerly entered the else-as-its-own-block and are now
    absorbed into the preceding block's terminator). Still 0
    computed-target edges and 1,384 cross-chunk `global sub`
    call sites recorded.
  - **Tests**: 1 new unit test
    (`cfg_redirects_if_target_past_else_opcode`) covers the
    redirect, the suppressed leader, and the `target_aliases`
    population. Total gpl-disasm test count: 36 unit + 2
    integration.

- **`tools/gpl-disasm/` v0.3.0** ships control-flow analysis.
  Each disassembled chunk now carries a `Cfg` of basic blocks,
  entry points, and labeled successors. The text listing
  renders `gpl if label_0x0020` instead of `gpl if 32`, with
  `label_*:` / `entry_*:` lines preceding every block leader.
  - **Pre-implementation spike** verified the load-bearing
    assumption against three independent sources
    (soloscuro-archive's Lua emitter, libgff's parser, and a
    hand-trace of two DS1 GPLDATA chunks): the first parameter
    of every branch opcode is the absolute byte offset of the
    target instruction within the same chunk. The semantics
    table and the trace evidence land in
    [`docs/gpl-bytecode.md` §5a](docs/gpl-bytecode.md). The
    spike caught one wrinkle worth surfacing: `gpl ifcompare`
    (0x27) takes 2 parameters where the *second* param is the
    target offset (param[0] is the comparison value); this is
    different from the single-param branches (`if`, `else`,
    `while`, `wend`, `jump`, `local sub`).
  - **Branch classification** for the CFG covers `gpl jump`
    (0x12), `gpl local sub` (0x13), `gpl global sub` (0x14),
    `gpl local ret` (0x15), `gpl global ret` (0x19), `gpl
    ifcompare` (0x27), `gpl exit gpl` (0x31), `gpl if` (0x3E),
    `gpl else` (0x3F), `gpl while` (0x63), `gpl wend` (0x64),
    plus `gpl zero` / EXIT_GPL (0x00) and the
    `endif`/`cmpend` markers (0x67/0x61).
  - **Entry points** = chunk start (offset 0), offset 1 when a
    real instruction lives there (every chunk we have begins
    with the `gpl global ret` epilogue placeholder at offset 0),
    plus every observed `gpl local sub` target inside the same
    chunk. `gpl global sub` cross-chunk targets are recorded in
    a new `cross_chunk_calls` list for v0.4.0+ inter-chunk work
    but are not added as CFG edges in v0.3.0.
  - **New CLI flags**: `--entries` (list discovered entry
    points, one offset per line), `--cfg <path>` (Graphviz DOT
    of the per-chunk CFG; supports `-` for stdout in
    single-chunk mode; writes `<kind>-<id>.dot` files in
    `--all` mode), `--no-labels` (revert to integer targets in
    the text listing for diff-friendly output).
  - **JSON output** gains an additive `cfg` field
    (entry_points, blocks, labels, unresolved) plus a top-level
    `cross_chunk_calls` list. Existing consumers
    (`dialog-extract` v0.2.0) parse the new shape without
    modification.
  - **Corpus verification**: 600 / 600 DS1+DS2 GPL/MAS chunks
    build a CFG where every one of the 71,403 successor edges
    resolves to a known instruction boundary. 0 computed-target
    edges, 1,384 `global sub` cross-chunk call sites recorded.
    A new integration test
    (`every_cfg_successor_resolves_to_instruction_boundary` in
    `tests/corpus_smoke.rs`) enforces this invariant.
  - **Tests**: 10 new unit tests in `src/lib.rs` cover each
    branch classification, entry-point promotion via `local
    sub`, cross-chunk call recording, label formatting, and the
    `cfg = None` fallback for misaligned disassembly. Total
    gpl-disasm test count: 35 unit + 2 integration.
  - Ported from `.dsoageofheroes/soloscuro-archive/src/gpl/gpl-lua.c`
    (MIT, attributed) and `.dsoageofheroes/libgff/src/gpl/parse.c`
    (MIT, attributed). No new third-party crate deps; the DOT
    writer uses `std::io::Write` only.
  - Roadmap Phase 3 "Identify entry points and basic-block
    boundaries" box ticked.

- **`tools/image-extract/` v0.1.0** ships (new Rust crate;
  Phase 4 Goal-1 deliverable, the first **visual** modder tool
  in the toolkit). Extracts Dark Sun bitmap chunks (`BMP `,
  `PORT`, `ICON`, `BMAP`, `OMAP`, `TILE`) as palette-indexed
  PNG.
  - **Ports from `dsoageofheroes/libgff` (MIT, attributed)**:
    - **Palette** (`PAL ` / `CPAL` chunks): 768 bytes = 256 × RGB
      6-bit, scaled to 8-bit by libgff's `intensity_multiplier = 4`.
    - **Bitmap header**: 6-byte preamble + u16 `frame_count` at
      +4 + u32 per-frame offset table at +6; per-frame `u16 width`
      + `u16 height` + 1 unknown byte + 4-byte frame_type tag
      ("PLNR" / "PLAN" / DS1 RLE).
    - **DS1 RLE pixel decoder**: per-row spans with even/odd
      code split (even = direct palette indices, odd =
      repeat-single). Image stored bottom-up; rows flipped to
      PNG top-down on output.
    - **PLNR bit-packed dictionary decoder**: per-symbol
      bit-packed indices into a chunk-local dictionary; 4-bit
      rotated bit-extraction order.
  - **PNG output** via the `png` crate (MIT/Apache 2.0; new
    workspace dep `png = "0.17"`, pre-approved per spec §7a as
    format I/O). PNGs are 8-bit palette-indexed, preserving the
    source format's compact representation.
  - **CLI**: `image-extract <file> --kind PORT --id N -o out.png`
    for single-frame; `--frame N` for multi-frame chunks;
    `--all -o <dir>` for bulk dump; `--palette N --palette-kind
    PAL` for explicit palette selection (default: lowest-id
    `PAL `, falling back to lowest-id `CPAL`).
  - **Library**: `Palette::from_bytes`, `Bitmap::from_bytes`,
    `Bitmap::decode_frame -> Frame`, `write_png(path, frame,
    palette)`.
  - **Empirical** (GOG 1.10): DS1 GPLDATA.GFF's 112 `PORT`
    frames extract cleanly (100%). Combined DS1+DS2 corpus:
    1,334 bitmap chunks, 1,976 frames, **1,328 decoded (67%)**:
    883 DS1 RLE + 445 PLNR. The 648 skipped frames are mostly
    PLAN (libgff itself doesn't implement it) and other
    variants pending RE.
  - **Tests**: 5 unit tests covering palette scaling, bitmap
    header parsing, DS1 RLE direct + repeat. Corpus smoke test
    iterates all bitmap chunks across DS1+DS2 GPLDATA.GFF and
    RESOURCE.GFF without panicking, verifies pixel counts match
    width × height, and reports decoded percentages per type.
  - Roadmap Phase 4 image-extract v0.1.0 added and ticked.
- **`tools/save-inspect/` v0.2.0** ships CHAR record body
  decoding. v0.1.0 emitted an opaque hex preview of every
  CHAR's data; v0.2.0 walks the RDFF sub-blocks and decodes
  combat / character / item records to structured JSON.
  - **CHAR body shape** (per libsoloscuro `src/entity.c`
    `sol_entity_load_from_gff`, MIT): a sequence of
    RDFF-headed sub-blocks in positional order: `sub[0]` is
    combat, `sub[1]` is the character record, `sub[2..N-1]` are
    item slots, optionally followed by an `RDFF_END` terminator
    (`load_action == -1`, `len == 0`). The first sub-block's
    `blocknum` field gives the total count.
  - **DS1 schemas**: `ds1_combat_t` (58 bytes; hp / psp / AC /
    THAC0 / stats / 18-char name), `ds_character_t` (71 bytes;
    XP / HP / PSP / race / gender / alignment / stats / class /
    level / saves / sound IDs), `ds1_item_t` (21 bytes; slot /
    item_index / quantity / value / charges / bonus). Ported
    from `libgff` `include/gff/object.h` + `item.h` (MIT;
    annotated `Not confirmed at all` for the item struct by
    upstream).
  - **DS2 schemas differ** (combat 49 bytes, character 66 bytes,
    item 23 bytes). v0.2.0 decodes DS2 items fully and surfaces
    DS2 character names via an ASCII-run heuristic
    (`_likely_name`), but emits combat and character bodies as
    raw hex with `_format: "ds2_or_unknown_..._layout"` rather
    than producing wrong-looking field values. Full DS2 schemas
    are v0.3.0 work.
  - **Enum lookups** added: `gff_race_e` (MONSTER / HUMAN /
    DWARF / ELF / HALFELF / HALFGIANT / HALFLING / MUL /
    THRIKREEN), gender, alignment (9-cell D&D 2e), item slot
    (ARM / AMMO / MISSILE / HAND0..HAND1 / FINGER0..FINGER1 /
    WAIST / LEGS / HEAD / NECK / CHEST / CLOAK / FOOT). Each
    field renders as `{ "value": N, "name": "ENUM" }`.
  - **Back-compat**: the existing `rdff_header`,
    `body_length`, `body_hex_preview` keys still appear on
    every CHAR chunk. The new `body` key is additive.
  - **Empirical** (GOG 1.10): DS1 CHARSAVE.GFF decodes 5/5
    CHARs cleanly (Garn, Aticus, Seneca, Deestan, plus PC).
    DS2 CHARSAVE.GFF decodes 19 CHARs with full item slots;
    DS2 character names surface ("Caron the Unsur", "Anathea",
    "Cermak", "Frin'kal", ...) via the heuristic.
  - Stdlib-only Python; no new dependencies.
  - Roadmap Phase 4 save-inspect v0.2.0 box ticked.
- **`tools/gpl-disasm/` v0.2.1** closes every case v0.2.0
  deferred. The 600 DS1+DS2 GPL/MAS chunks now disassemble at
  **100% alignment** (was 10.7% in v0.2.0).
  - **`gpl_access_complex` ported** (libgff `parse.c` 235-288):
    word `obj_name` + byte `depth` + `depth` bytes of element
    data. `obj_name >= 0x8000` keyword set (POV / ACTIVE /
    PASSIVE / OTHER / OTHER1 / THING) rendered by name.
  - **`GPL_COMPLEX_*` range (`0xB0..=0xBF`)** decodes as
    `Expression::ComplexAccess { tag, obj_name, depth,
    elements }`. The `0xb3` special case is now just one entry
    in that range.
  - **`GPL_RETVAL | 0x80` (`0x8C`)** recursively dispatches the
    inner opcode's parameter shape, using a 21-entry safe-subset
    matching libgff's `gpl_retval` switch
    (`parse.c` 1791-1826). Inner params land in
    `Expression::RetVal { inner_opcode, inner_mnemonic,
    inner_params }`. Recursion bounded by `MAX_RETVAL_DEPTH = 4`.
  - **`gpl_setrecord` (0x40)** promoted from `ParamSpec::Custom`
    to `ParamSpec::SetRecord`: `access_complex + read_number`
    per all three branches of libgff's handler.
  - **`gpl_load_variable` (0x16)** complex-write path now
    decodes via `access_complex` instead of bailing.
  - **Display impl**: ComplexAccess renders as
    `COMPLEX(0x31, POV, depth=2, [4,7])`; RetVal as
    `RETVAL(gpl rand 5)`.
  - **Tests**: 25 unit tests (4 new in v0.2.1 for the new
    cases). Corpus smoke test reports `600/600 aligned`.
  - **Downstream**: `dialog-extract` v0.2.0 picks up 1,194 more
    strings (DS1 17,560 → 17,926; DS2 27,857 → 28,685;
    combined 45,417 → **46,611**). Every dialog-bearing chunk
    now reports `aligned: true`.
  - The factoring also extracted `read_instruction_params_with_depth`
    as a helper shared between the top-level `disassemble()` and
    the RETVAL recursion path.
- **`tools/dialog-extract/` v0.2.0** ships an instruction-aware
  rewrite that consumes `gpl-disasm --json` (gpl-disasm v0.2.0+).
  The heuristic byte-scan from v0.1.0 is retired; byte boundaries
  are now real, eliminating false positives, and text-id
  references resolve via a new `--text-source <RESOURCE.GFF>`
  flag.
  - **New surface**: `GSTRING[id]` references in
    `gpl print string`, `gpl menu`, etc. now resolve to the
    corresponding TEXT chunk in the sibling GFF. NPC names
    ("Garn", "Dag", "Halton", "Sarthana") and dialog snippets
    that lived in `RESOURCE.GFF` rather than inline now surface
    in the JSON.
  - **Surfaced opcodes**: `0x2C gpl log`, `0x42 gpl input string`,
    `0x48 gpl menu`, `0x4F gpl print string`,
    `0x5A gpl string compare`, `0x0A gpl string copy`.
  - **`LSTRING[id]` refs** are captured with `text_id` but
    emitted as `unresolved: true`; resolving them needs a
    per-region / per-script text source that v0.3.0+ will add.
  - **Output shape** gains `source` (`"inline"` /
    `"text:gstring"` / `"text:lstring"`), `text_id` (for refs),
    `unresolved` (true when a ref couldn't be resolved),
    `opcode` and `opcode_name` (the consuming opcode), and
    per-chunk `aligned` (mirrors gpl-disasm's `aligned` flag so
    consumers can filter on best-effort chunks).
  - **Empirical**: DS1 GPLDATA = 17,560 strings (up from
    13,938); DS2 GPLDATA = 27,857 (up from 22,431). Combined
    **45,417** (up from 36,369). The v0.1 inline count was
    slightly higher than v0.2's inline count because v0.1's
    heuristic accepted misaligned-byte garbage decodes; v0.2
    drops those while picking up far more legitimate strings
    via GSTRING resolution.
  - Stdlib-only Python. Shells out to `gpl-disasm --all -o
    <tmpdir> --json` to produce per-chunk JSON files, and to
    `gff-cat extract --all` (only when `--text-source` is used)
    to load the TEXT chunks.
  - CLI: `dialog-extract <file> [--pretty] [-o <out>]
    [--grep <regex>] [--text-source <gff>] [--gpl-disasm <path>]
    [--gff-cat <path>]`. Renamed `--gff-cat` semantics: it's now
    a fallback locator for the text-source workflow, no longer
    the primary extractor.
  - Roadmap Phase 4 dialog-extract v0.2.0 box ticked.
- **`.dso-online/` reference checkout** lands.
  [`greg-kennedy/DarkSunOnline`](https://github.com/greg-kennedy/DarkSunOnline)
  cloned at depth 1 (~2.3 MB) to `.dso-online/` (gitignored).
  License is AGPL-3.0, so this is a research-only mirror; we
  cite individual symbol names from
  `tools/symbols.txt` (3,530 functions, 2,247 globals/labels;
  extracted by Greg from the DSO v1.0 client's Watcom debug
  symbols) as facts, not source code we port. The symbols
  cover most of the engine internals shared between DSO and
  WotR: `ExecuteGpl`, the `Gpl{Tile,Talk,Door,Pickup,Attack,
  Look,Use,UseWith}Check` trigger family, `GplChangeRegion`
  (relevant to the DS2 mines-elevator bug),
  `GplUpdatePsionics`, and the `Gff*` API. **[`docs/dso-symbols.md`](docs/dso-symbols.md)**
  lands as the curation surface: how the symbols were
  extracted, the format, the highest-value candidates for
  `gpl-disasm v0.4.0+` symbol import, and a hand-verified
  catalogue table that grows as we cross-check each name
  against `DSUN.EXE`. Memory note `dso_online_reference` saved.
  Cited from `CREDITS.md` and `docs/upstream-projects.md` §3.
- **`tools/gpl-disasm/` v0.2.0** ships parameter decoding.
  Output is now **one row per instruction** (was one row per
  byte) with formatted parameters: `gpl print string  115,
  "Free! Finally free! I will destroy you all!..."`,
  `gpl load accum  GNUM[1] == 0i8`, `gpl tport  NAME(-22), 255,
  99i8, 99i8, 0i8`. Decoded inline strings now surface
  directly in the disassembly without the v0.1.0 ASCII-run
  heuristic.
  - **Ports** from `dsoageofheroes/libgff` (MIT, attributed
    inline and in `CREDITS.md`):
    - `gpl_read_number` (the variable-length expression
      decoder): 14-bit immediates, `GPL_IMMED_BYTE` / `BIGNUM` /
      `NAME` / `STRING`, variable references with
      `EXTENDED_VAR`, infix operators (`0xD1..=0xDF`), and
      parens. Mirrors libgff's `do_next` operator-loop semantics.
    - `gpl_read_simple_num_var` (variable reference id, 1 or 2
      bytes per `EXTENDED_VAR`).
    - Per-opcode parameter-count table `PARAM_COUNTS[0x81]`,
      derived by reading every handler body in
      `parse.c`.
  - **Port** from `dsoageofheroes/soloscuro-archive` (MIT,
    same author): the 7-bit packed string decoder
    (`read_compressed`) so `GPL_IMMED_STRING` payloads decode
    directly. Same algorithm as the existing Python port in
    `tools/dialog-extract/`.
  - **Structural handlers**: `gpl_load_variable` (0x16, simple
    path; complex-write deferred), `gpl_menu` (0x48, three-
    expression entries terminated by 0x4A), `gpl_search` (0x33,
    SEARCH_QUAL loop), `gpl_log` (0x2C, packed-string only).
  - **Deferred to v0.2.1** (decoded as opaque, marked
    `best_effort`): nested `GPL_RETVAL | 0x80`,
    `GPL_COMPLEX_*` (`0xB0..0xBF`), `gpl_setrecord` (uses
    `access_complex`), and the `0xb3` "passive flag" special
    case. The decoder records the dispatch byte and continues
    best-effort; subsequent instructions inside the same chunk
    may misalign past the deferred case.
  - **New types** (all `serde::Serialize`-derived):
    `DisasmResult` (`{ instructions, bytes_consumed, total_bytes,
    aligned }`), `Instruction` (`{ offset, length, opcode,
    mnemonic, params, best_effort, string_run }`), `Expression`
    (a token in one `gpl_read_number` result), plus `VarKind`,
    `Op`, `StringSubType`, `ParamSpec`.
  - **CLI `--json` flag** emits structured output for downstream
    tools (`dialog-extract` v0.2.0 will consume it).
  - **Workspace**: `serde` and `serde_json` added to
    `tools/gpl-disasm/Cargo.toml` (both already in
    `workspace.dependencies` per spec §7a).
  - **Tests**: 21 unit tests (each Expression case, helpers,
    end-to-end small programs). Corpus integration test now
    tracks two metrics: `bytes_consumed` (every byte must be
    accounted for; asserted equal to `chunk_bytes.len()`) and
    `aligned` percentage (fraction of chunks where no
    `best_effort` was hit and the whole chunk parses cleanly).
    Current corpus: **600 GPL/MAS chunks**, 2.37 M input bytes
    decode into **198,744 instructions** (vs. v0.1.0's 2.37 M
    annotation rows). 10.7% of chunks parse fully aligned;
    the rest hit at least one deferred case (mostly nested
    RETVAL on `gpl_search` / `gpl_clone` / `gpl_request`, or
    a `GPL_COMPLEX_*` record-field access). v0.2.1 closes the
    gap.
  - `docs/gpl-opcodes.md` adds a per-opcode `Params` column
    backed by the new `PARAM_COUNTS` table.
  - `docs/gpl-bytecode.md` §5: v0.2.0 description updated
    (parameter decoding shipped); v0.2.1 carries the deferred
    cases.
  - Roadmap Phase 3 v0.2.0 box ticked.
  - `pick-it-up.md` retired (transient handoff primer).
- **[`CREDITS.md`](CREDITS.md)** lands as a per-feature
  attribution manifest. Each OpenDS feature (FileHeader, TOC
  layout, segmented chunk resolution, writer policy, chunk-type
  catalogue, GPL opcode catalogue, GPL_* constants, 7-bit
  packed-string decoder, RDFF header, PSIN/PSST structs)
  maps to the specific upstream file or function it was
  ported from in `dsoageofheroes/libgff`,
  `dsoageofheroes/soloscuro-archive`, or
  `JohnGlassmyer/dsun_music`. README.md Credits section
  expanded to point at CREDITS.md. Inline citations added
  alongside save-inspect's PSIN / PSST / RDFF-header
  decoders. Existing inline citations in gff-edit, gpl-disasm,
  and dialog-extract verified.
- **`tools/dialog-extract/` v0.1.0** ships (new Python tool;
  Phase 4 Goal-1 deliverable). Pulls inline NPC dialog strings
  from `GPL ` and `MAS ` chunks as JSON.
  - **The headline find from the dsoageofheroes research**:
    GPL inline strings are *not* plain ASCII; they use a
    1-byte type marker (`0x01` INTRODUCE / `0x02` UNCOMPRESSED
    / `0x05` COMPRESSED) followed by a 7-bit packed payload
    terminated by `0x03`. Decoder ported from
    `dsoageofheroes/soloscuro-archive`
    `src/gpl/gpl-string.c` `read_compressed`
    (MIT, Paul E. West et al.; attributed in the script's
    comments). That's why v0.1 byte-mode ASCII-run detection
    didn't surface the dialog text on its own.
  - **v0.1.0 is heuristic**: scans GPL/MAS chunk bytes for
    `GPL_IMMED_STRING | 0x80` (`0x92`) followed by a known
    type byte, then decodes. False positives possible (param
    byte that happens to equal `0x92`); false negatives
    possible (strings referenced via `gpl_get_gstr(id)` from
    external `TEXT` chunks are not yet resolved). README
    documents the limitations.
  - **v0.2.0 plan**: replace the heuristic with
    `gpl-disasm --json` consumption once gpl-disasm v0.2.0
    ships proper instruction-boundary decoding; the 7-bit
    string decoder itself stays.
  - Stdlib-only Python. Shells out to `gff-cat extract --all`
    to handle segmented GPL/MAS chunks rather than
    re-implementing segmented chunk resolution.
  - CLI: `dialog-extract <file> [--pretty] [-o <out>]
    [--grep <regex>] [--gff-cat <path>]`.
  - **Empirical results**: DS1 `GPLDATA.GFF` yields 215
    chunks / **13,938 dialog strings**; DS2 `GPLDATA.GFF`
    yields 316 chunks / **22,431 strings**. Total across both
    games: **36,369 NPC dialog strings**, fully readable
    today. Sample DS1 strings: "Free! Finally free! I will
    destroy you all!", "By the lost gods of Athas, set me
    free!", "I am A'Poss, master of this temple."
- **`.dsoageofheroes/` reference checkout** lands. All 7 repos
  from the dsoageofheroes GitHub org cloned at depth 1
  (~8.7 MB total): `libgff`, `libsoloscuro`, `soloscuro`,
  `soloscuro-archive`, `soloscuro-oldgo`, `soloscuro-orx`,
  `the-dark-lens`. Mostly MIT-licensed. The 7-bit packed
  string format was discovered in soloscuro-archive's
  `gpl-string.c` during this research pass. Memory note
  `dsoageofheroes_reference` saved for future sessions.
  `.gitignore` updated.
- Roadmap Phase 4: dialog-extract v0.1.0 boxes ticked
  (inline strings + `--grep`); text-id reference resolution
  and structured dialog trees roll forward to v0.2.0 and
  v0.3.0.
- **`tools/save-inspect/` v0.1.0** ships (new Python tool;
  Phase 4 Goal-1 deliverable). Dumps a `CHARSAVE.GFF` as JSON
  with per-chunk decoding:
  - `PSIN` chunks decode as a 7-element `types[]` array
    (psionic discipline byte codes; per libgff
    `include/gff/psionic.h` `gff_psin_t`).
  - `PSST` chunks decode as a 34-element `psionics[]` array
    (psionic mastery; per `gff_psionic_list_t`).
  - `TEXT` chunks decode as plain text (CRLF normalised to
    `\n` in JSON output).
  - `CHAR` chunks decode the leading 10-byte
    `gff_rdff_header_t` (load_action, blocknum, type, index,
    from, len) and emit the remaining body as an opaque hex
    preview. Full record schema decoding is per-game (DS1 vs
    DS2 byte layouts differ per `docs/file-formats.md` §2)
    and lands in save-inspect v0.2.0.
  - `SPST`, `CACT`, `PREF`, `GREQ` (DS2-only) chunks emit
    hex previews until their layouts are documented.
  - Stdlib-only Python (no dependency on `gff-cat`
    subprocess). Embedded GFF parser handles indexed chunks
    only; `CHARSAVE.GFF` never uses segmented types, so the
    simplification is sound for this tool.
  - CLI: `save-inspect <file> [-o out.json] [--pretty]`.
    JSON to stdout by default.
  - Verified against DS1 (4.4 KB, 42 chunks, 8 character
    slots) and DS2 (11.7 KB, 98 chunks, 19 character slots);
    "Caron the Unsur..." surfaces as plain bytes in the first
    DS2 CHAR body, confirming the underlying record format is
    a mix of fixed fields and ASCII names.
- Roadmap Phase 4: save-inspect v0.1.0 box ticked; the
  per-game CHAR decoding work and save diffing roll forward
  to v0.2.0 and v0.3.0.
- **`tools/gpl-disasm/` v0.1.0** ships (new Rust crate, the
  Phase 3 keystone). Byte-annotation pass: each byte of a GPL
  or MAS chunk gets a row tagged with libgff's opcode name.
  Parameter decoding is deferred to v0.2.0 (the v0.1.0 output
  treats every byte as a potential opcode, so instruction
  boundaries are not yet aligned with the real program flow).
  CLI subcommands: single-chunk to stdout/file, `--all` bulk
  dump to a directory as `<kind>-<id>.asm`, and `--opcodes` to
  print the embedded catalogue.
  - Opcode catalogue: 129 entries covering bytes `0x00`..`0x80`,
    sourced verbatim from libgff's `gpl_commands` table
    (`dsoageofheroes/libgff` `src/gpl/parse.c` lines
    1554-1684, MIT-licensed, attributed in code).
  - Inline ASCII detection: runs of ≥4 printable bytes get
    a `; "..."` comment annotation on the row that starts them.
  - SIGPIPE-safe (`gpl-disasm ... | head` exits cleanly).
  - 6 unit tests; new corpus integration test
    `tests/corpus_smoke.rs` disassembles every `GPL ` and
    `MAS ` chunk in DS1+DS2 `GPLDATA.GFF` (600 chunks; 2.37M
    input bytes -> 2.37M annotation rows) without panics.
- **`docs/gpl-opcodes.md`** lands: the catalogue table with
  source citation. "Safe in RETVAL context" annotations
  preserved from libgff `gpl_retval` switch (parse.c lines
  1791-1826).
- **`docs/gpl-bytecode.md`** refreshed: Rust (was Python),
  depends on `gff-edit` library (was `gff-tool` JVM jar),
  per-version scope documented (v0.1 byte-annotation → v0.2
  parameter decoding → v0.3 control flow → v0.4 symbols).
- Workspace gains `tools/gpl-disasm` as a member crate;
  depends on `gff-edit` via local path. tools/README.md
  "Shipped" table extended; "Planned" entry for gpl-disasm
  removed.
- Roadmap Phase 3: v0.1.0 boxes ticked (GFF integration,
  annotation, string detection, opcode catalogue, README).
  Parameter decoding and control flow annotated as v0.2.0 /
  v0.3.0 followups.
- **`tools/gff-edit/` v0.4.0**: modder readability layer.
  - `gff-cat extract --all -o <dir>` bulk-dumps every chunk as
    `<kind>-<id>.bin` under a directory.
  - `gff-cat info --json` / `list --json` emit machine-readable
    output. `FourCC`, `FileHeader`, `ChunkRef`, `TypeInfo`,
    `SegmentedInfo`, and `SegEntry` derive (or implement)
    `serde::Serialize`. `ChunkRef::meta_offset` is excluded
    from the JSON surface via `#[serde(skip)]`.
  - `gff-cat dump-text <file> -o <dir>` writes each
    TEXT/ETME/MERR/NAME/SPIN chunk as `<kind>-<id>.txt`. Bytes
    are verbatim (DOS CRLF preserved on disk; modders can edit
    in any editor that handles CRLF, which is most).
  - `gff-cat pack-text <file> <dir> -o <out>` reads every
    `<kind>-<id>.txt` in `<dir>` and re-injects matching chunks
    into the source GFF via `Gff::replace_chunk`.
    Demonstrated end-to-end: dump-text on RESOURCE.GFF
    produces 271 .txt files; pack-text on those files produces
    a GFF byte-identical to the original. Across the full
    corpus, 17/17 text-bearing GFFs round-trip byte-identical.
  - `gff-cat kind <FOURCC>` looks up an embedded catalogue
    sourced from [`docs/file-formats.md`](docs/file-formats.md).
    `gff-cat kind --list` dumps the whole catalogue.
  - Workspace gains `serde` and `serde_json` as pre-approved
    deps per [`spec.md`](spec.md) §7a (format I/O).
  - 16 unit tests (2 new for JSON shape). All Phase 1 tests
    (incl. the byte-identical no-op replace corpus integration
    test) continue to pass.
- **Project priority pivot**: the modding toolkit is now
  framed explicitly as Goal 1, with darkfix patches as Goal 2.
  [`spec.md`](spec.md) §1 reordered to put the toolkit first;
  §1b's tools-first paragraph reframed to say the toolkit
  serves *any* mod author and that our own patch authoring is
  one consumer among many. Memory updated to match. The
  underlying tools-first ordering of the roadmap is unchanged;
  this is a framing pass, not a re-plan.
- **`tools/gff-edit/` v0.3.0**: writer lands. `Gff::replace_chunk`
  in the library; `gff-cat replace <file> <kind> <id>
  <bytes-file> -o <out>` in the CLI. Replacement policy matches
  dsun_music's `GffFile.replaceResource`: in-place if the new
  bytes fit, append at end-of-file otherwise. The chunk's
  `(location, length)` record is rewritten wherever it lives,
  TOC for indexed chunks or the secondary table inside the
  `GFFI` chunk for segmented chunks. `ChunkRef` carries a new
  `meta_offset` field tracking that location during parse. New
  error variants: `ChunkNotFound`, `ChunkTooLarge`. 14 unit
  tests passing (up from 8): in-place same-size, in-place
  shrink, append-grow, segmented replace, no-op-is-identity,
  not-found error. Corpus integration test
  (`tests/corpus_roundtrip.rs`) verifies no-op replace is
  byte-identical on all 128 GFFs in DS1+DS2 (pristine
  innoextract + deployed Wine installs).
- [`docs/file-formats.md`](docs/file-formats.md) §1: documents
  the writer policy (in-place vs append) and how the writer
  uses each chunk's metadata file offset.
- **Phase 1 closed**: the GFF foundation is read-and-write
  complete. Toolkit gains `verify-install` (Python) and
  `gff-edit` (Rust); patches start at Phase 6 or are deferred
  in favour of Phase 4's modder-facing tools per Goal 1.
- **`tools/gff-edit/` v0.2.0**: segmented chunks fully resolved.
  The parser now reads each segmented type's secondary table
  inside the GFFI chunk, reconstructs resource ids from the
  type's segment runs, and appends the resolved `ChunkRef`s to
  `Gff::chunks()` in TOC declaration order. `Gff::find()` and
  `Gff::read()` work for both indexed and segmented chunks
  with no API change. New CLI subcommand: `gff-cat extract
  <file> <kind> <id> [-o <out>]` writes chunk bytes to stdout
  or a file. v0.1's "segmented not listed" caveat removed from
  `gff-cat list`. SIGPIPE-safe (`gff-cat list | head` no
  longer panics). Smoke-tested against 128 GFFs in DS1 and DS2
  with 63,080 chunks resolved; integrity spot-checked against
  manual `dd` slices. New error variants: `MissingGffiType`,
  `SegLocIdOutOfRange`, `SecondaryTableOutOfBounds`,
  `SecondaryTableMismatch`. `dsun_music` and `libgff` cited as
  the format references for segmented resolution.
- `docs/file-formats.md` §1 expanded: documents segmented chunk
  resolution (primary GFFI table, secondary table layout,
  resource-id reconstruction from segment runs). §5 open
  question on segmented chunk layout struck through; resolved.
- **Reference checkout**: `JohnGlassmyer/dsun_music` cloned to
  `.dsun_music/` (gitignored). MIT-licensed Java/Maven project
  with four CLI tools (gff/image/region/xmi) and a shared
  `common` library. Its `GffFile.replaceResource` is the
  source-of-truth reference for our writer's in-place-or-append
  policy; its `PrimaryGffiTable` + `SecondaryGffiTable` confirm
  the segmented chunk resolution layout. Future reference for
  Phase 4 region-view and image extraction work too.
- **`tools/gff-edit/` v0.1.0** ships (Rust crate + `gff-cat`
  binary). Read-only first pass: parses the 28-byte GFF file
  header and the full TOC, including both indexed and segmented
  chunk lists. Library exposes `Gff::open`, `Gff::types`,
  `Gff::chunks`, `Gff::find`, `Gff::read`. CLI subcommands:
  `gff-cat info <file>` (header + TOC summary), `gff-cat list
  <file>` (indexed chunks). Smoke-tested clean against every
  GFF in both pristine innoextract trees (61/61) and both
  deployed Wine installs including save files (67/67).
  Resolving segmented-chunk locations (requires `GFFI`
  cross-reference) and the writer roll forward to v0.2.0 and
  v0.3.0; see [`tools/gff-edit/README.md`](tools/gff-edit/README.md)
  for the crate-level roadmap.
- **Cargo workspace** lands at the repo root. `Cargo.toml`
  declares `tools/gff-edit` as the first member, plus shared
  edition / license / repo metadata and a minimal
  `[workspace.dependencies]` block (clap, anyhow, thiserror).
  Per [`docs/versioning.md`](docs/versioning.md), tools version
  independently; the workspace does **not** carry a shared
  `version.workspace`.
- [`docs/file-formats.md`](docs/file-formats.md) §1 fills in the
  authoritative GFF layout: 7-field file header, TOC header,
  num_types + chunk_list_header + (indexed entry | segmented
  entry) pattern, segmented-flag mask `0x80000000` on
  `chunk_count` (not `chunk_type`). Cross-checked against
  libgff's `gff_open()` loader. §5 open questions updated to
  carry only the genuinely-unresolved items (segmented chunk
  resolution, non-empty free-list layout, `file_flags`/`data0`
  semantics, internal compression).
- **`tools/verify-install/` v0.1.0** ships. Stdlib-only Python.
  Default mode verifies an install against the canonical
  per-game hash manifest; `--capture` mode regenerates the
  manifest from a pristine source.
- Canonical source-hash manifests captured at
  `docs/source-hashes/ds1-gog-1.10.toml` (60 files) and
  `docs/source-hashes/ds2-gog-1.10.toml` (238 files). Captured
  from innoextract of the GOG 1.10 installer RARs in `.games/`.
  Each manifest's `[runtime_state]` block covers saves, audio
  config, DOSBox redistributable, GOG client artifacts, and the
  cloud-saves directory. `[runtime_state]` patterns can override
  `[files]` entries so runtime-mutated files (e.g.
  `DARKRUN.GFF`, `SOUND.CFG`) carry pristine hashes for
  reference without failing verification on a played install.
- [`docs/versioning.md`](docs/versioning.md) lands. Each tool
  and patch carries its own `VERSION` file; tag format
  `<item>-vMAJOR.MINOR.PATCH`. Build descriptors
  (`Cargo.toml` / `pyproject.toml` / `manifest.toml`) read from
  `VERSION`; nothing duplicates it. Items start at 0.1.0; 1.0.0
  is a back-compat commitment, not an automatic milestone.
- [`tools/README.md`](tools/README.md) lands as the toolkit
  index. One line per tool: language, version, purpose.
- Implementation-language policy formalised in
  [`spec.md`](spec.md) §7a: Rust for foundation libraries and
  heavy-lifting tools (`gff-edit`, `gpl-disasm`, `gpl-asm`,
  `region-view`); Python for CLI utilities, patch authoring
  scripts, and the applier. Single-language alternatives were
  considered and rejected. Python target 3.11+, Rust edition
  2024.
- Roadmap annotated per-tool with implementation language and
  full-semver tag format (`v0.1.0`, not `v0.1`).
- Spec §10 and §4 zip / directory examples normalised to
  full-semver tag format.
- `tools/extract.sh` deferred out of Phase 0: developers who
  run the GOG installer already produce the same extracted file
  tree, so the script is not blocking. Reinstated if a
  contributor needs from-installer extraction without running
  the installer.
- Spec §13 / §14 numbering bug fixed (two §13 sections; "Open
  questions" renumbered to §14).
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
