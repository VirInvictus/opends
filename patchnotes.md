# Patchnotes

Released versions appear here, newest first.

## Unreleased

- **`tools/dialog-extract/` v0.7.1** adds the missing
  `from typing import Any` (six annotation sites used `Any`
  unimported; harmless under deferred annotation evaluation
  until something introspects those annotations at runtime,
  then a `NameError`).

- **`tools/gpl-asm/` v0.8.1** fixes the text parser's byte-length
  accounting, which made `cargo test` fail in debug builds (the
  "known-flaky debug_assert_eq in lib.rs:91" caveat; it was a real
  bug, not flakiness). Three estimate-vs-encoder mismatches in
  `parse.rs`, none of which affected encoded bytes (the corpus
  round-trip was byte-identical throughout), only the
  reconstructed `DisasmResult.total_bytes`:
  - **RetVal + nested `gpl_search`**: `expression_byte_len`
    dropped `inner_raw_tail` and counted params past `[0]` that
    the encoder never writes.
  - **Top-level `gpl_search`**: `instruction_length` counted
    params past `[0]` whose bytes already live inside `raw_tail`
    (double-count).
  - **`gpl_setrecord`**: the encoder writes the access_complex
    body with no leading dispatch byte, but the estimate charged
    one per `ComplexAccess` token.
  - **Test hardening**: `text_roundtrip` now asserts
    `parsed.total_bytes == src.len()` per chunk, so estimate
    drift fails in release builds too (encoded-bytes equality
    cannot catch it, and the `encode()` check is debug-only).
  - Also collapses a nested `if` in `bin/gpl-asm.rs` (clippy).


  helper script). Modder-driven experimentation surface for
  DS1 party edits. Operates directly on
  `~/.wine/.../Dark Sun/DARKRUN.GFF` AND `SAVE01.SAV` together
  (engine loads from SAVE01; both need the same edits to
  survive a reload). Subcommands: `list`, `show <pc>`,
  `edit <pc> --hp / --max-hp / --psp / --max-psp / --xp /
  --str / --dex / --con / --int / --wis / --cha /
  --weapon-dice / --weapon-sides / --weapon-bonus`,
  `restore`. PC resolution by index (0..3) or name substring
  ("Gerakis"). Auto-backup to
  `<file>.bak.ds1-party-edit.<unix_ts>` on every edit.
  `--dry-run` to preview.

- **SAVE-chunk decode discoveries** (v0.7.0 follow-on):
  - **DARKRUN.GFF SAVE-5** = array of DS1 combat sub-blocks
    (58 bytes each), one per party PC in display order.
    Format matches libgff's `ds1_combat_t` exactly: stats at
    record offset 34..39, name at 40..57.
  - **DARKRUN.GFF SAVE-6** = array of DS1 character sub-blocks
    (71-72 bytes each), same order as SAVE-5. Holds the
    engine-authoritative copy of stats, plus the weapon
    damage fields (`num_dice` / `num_sides` / `num_bonuses`)
    the engine uses for combat. Editing stats in SAVE-5 only
    updates the display; the engine's combat math reads
    SAVE-6.
  - **SAVE01.SAV** is byte-identical to DARKRUN.GFF at save
    time. Engine reads SAVE01 on load; DARKRUN tracks live
    state during play. Edits must hit both files to survive
    a reload (the `ds1-party-edit.py` script does this
    automatically).
  - **Stats above the 2e exceptional-strength table**
    (anything > 25 roughly) hit out-of-range in the engine's
    damage-bonus lookup → returns +0 damage bonus. Setting
    STR 99 with cached weapon `1d1` = 1 damage per hit.
    Better godmode path: bump `num_dice` / `num_sides` /
    `num_bonuses` in the character sub-block instead.

- **`tools/save-inspect/` v0.9.4** fixes a DS1 bug in
  `give-item`: chain-continuation items use `from = 1` in DS1
  but `from = 2` in DS2. v0.9.3 hardcoded `from = 2`. Caught
  on smoking against Brandon's actual played DS1 save
  (`~/.wine/.../Dark Sun/CHARSAVE.GFF`; 8 PCs starting with
  T'kir'taap).
  - **Fix**: `give-item` now copies the `from` value from an
    existing chain-continuation item in the same PC, so the
    correct convention falls out per-save. If the PC has NO
    chain-continuation items (every chain is a single head),
    refuses with a clear message (use a PC with multi-item
    chains instead).
  - **Smoke**: Aticus (PC 1) had 5 items; gave him a 6th
    (id -1023 cloned from Lanthazar's loadout); round-trip
    `all_chunks_ok=True, file_bytes_equal=True`; list-items
    shows the new item at slot 5.
  - This makes DS1 the right test bed for `give-item`'s
    real-DOSBox verification — Brandon's
    `~/.wine/.../Dark Sun 2/CHARSAVE.GFF` isn't connected to
    a working DS2 install (his DS2 playthrough used
    `repro.py --play` sessions instead).

- **`tools/save-inspect/` v0.9.3** ships **`give-item`** with
  chain-invariant validation. The append path I deferred in
  v0.9.2 now lands, after empirical RE of the item linked-list
  conventions inside CHAR records. **The save's round-trip
  identity stays intact after the edit** (`roundtrip
  all_chunks_ok=True, file_bytes_equal=True`), which is the
  strongest pre-DOSBox correctness signal we have. Brandon's
  actual test is loading the patched save and confirming the
  new item is visible.
  - **Conventions RE'd from comparing CHAR-29 (5 items) and
    CHAR-30 (27 items) in the DS2 factory CHARSAVE.GFF**:
    - Items form a linked list via
      `rdff_header.index <-> decoded.next`
    - **Chain HEAD**: `load_action = 2`, `blocknum = 0`,
      `from = 16/17/4` (variable; relates to chain semantics
      we haven't isolated)
    - **Chain CONTINUATION**: `load_action = 4`, `from = 2`,
      `type = 1`, `blocknum = sub_block_index - 1`
    - `decoded.next = 9999` terminates a chain
    - `combat.blocknum = total_sub_blocks - 1` (excludes
      terminator)
    - `terminator.blocknum = combat.blocknum`
  - **`give-item <save> --pc N --item-id X --quantity Q
    [--charges C]`** extends the PC's LAST chain by one item:
    1. Allocates a fresh `rdff_header.index` (= max existing
       + 1)
    2. Patches the previous tail's `next` from 9999 to the
       new index
    3. Inserts a new chain-continuation item with `next =
       9999` (becoming the new tail)
    4. Bumps `combat.blocknum` and `terminator.blocknum`
    5. Validates chain invariants (no duplicate indexes,
       every `next` resolves, heads == tails) BEFORE writing
  - **Refuses to apply** when:
    - The PC has no items (no template to copy)
    - The last item's chain isn't terminated at 9999 (chain
      already broken; refuse to make it worse)
    - The index space is exhausted (max = 0xFFFF)
    - Chain validation fails post-edit (invariant-violating
      edit never lands on disk)
  - **`--dry-run`** previews the planned edit + validation.
  - **Smoke**: factory DS2 CHARSAVE → give Anathea
    (PC 1, 27 items) a `--item-id -99 --quantity 5` →
    chain validates, file written, round-trip
    `all_chunks_ok=True, file_bytes_equal=True`, list-items
    shows 28 items with the new one at slot 27.
  - **Bootstrap loop now has two paths**: `edit-item` for
    safe in-place edits (preferred when an empty slot exists)
    and `give-item` for chunk-growth append (when a PC
    genuinely runs out of slots, or for testing the chain-
    append path).

- **`tools/save-inspect/` v0.9.2** ships **`find-empty-slots`**
  + the bootstrap-items cookbook entry. Closes the modder-
  altitude loop for items without needing the riskier
  `give-item` (chunk-growth) path.
  - **`find-empty-slots <save>`**: scans every PC's inventory,
    reports slots with `quantity = 0`. Those are safe `edit-
    item` swap targets — modifying them doesn't displace any
    item the player is actually carrying. Brandon's DS2 played
    save: 87 empty slots across the 19 records, plenty for the
    bootstrap loop.
  - **`docs/cookbook/bootstrap-items.md`** is the second
    cookbook entry. Walks through the full loop: find empty
    slot → set candidate id → load DOSBox → observe → record
    in `items.toml`. Real DS2 commands; real id (`-746`); real
    rollback via the `.bak.<mtime>` snapshot.
  - **Brief on `give-item`'s deferral**: empirically inspecting
    Anathea's 27-item inventory in factory vs played (turns out
    identical; she's a starter NPC) shows items are a
    **linked list** via `rdff_header.index ↔ decoded.next`:

    ```
    Slot 0: header.index=331, next=33
    Slot 1: header.index=33,  next=281    ← chain step
    Slot 2: header.index=281, next=54     ← chain step
    ...
    Slot 7: ..., next=9999                ← terminator
    Slot 8: header.index=313, next=...    ← NEW chain head
    ```

    Multiple chains per PC, probably per slot-kind or per-pack
    (`pack_index` field, mostly `9999` but one Anathea slot
    has `518`). Safe `give-item` requires:
    1. Identify which chain to extend
    2. Allocate a fresh `rdff_header.index` (currently unused)
    3. Patch the chain's previous tail's `next` from 9999 to
       our new index
    4. Insert the new item with `next = 9999`

    Doable but more RE than I want without a corruption
    canary. `find-empty-slots + edit-item` covers the
    bootstrap loop without it. Promoting `give-item` when a
    PC genuinely runs out of empty slots becomes the forcing
    function.

- **`tools/save-inspect/` v0.9.1** adds the **edit half** of the
  modder-altitude surface: `edit-pc` and `edit-item`. Pairs
  with v0.9.0's `list-pcs` / `list-items` discovery commands.
  Brandon: "we have a saved game; if we can add items by a
  reference we have four character inventories we can fill."
  - **`edit-pc <save> --pc N`** with short flags for the
    high-leverage fields:

        --hp N --psp N --max-hp N --max-psp N --xp N
        --str N --dex N --con N --int N --wis N --cha N

    Each flag writes the right sub-block (combat for current
    hp/psp/stats; character for max-* and xp). Stats write to
    BOTH combat.stats and character.stats so the values stay
    consistent (the engine reads from both at different times).
    `--dry-run` previews; backup-before-write to
    `<file>.bak.<mtime>`; `--no-backup` opts out.
  - **`edit-item <save> --pc N --slot K`** with short flags:

        --item-id X --quantity Q --charges C --value V

    Overwrites an existing inventory slot in place (no chunk
    growth; safe). Same backup + dry-run conventions. Opens
    the bootstrap loop for `syms/items.toml`: pick a spare
    slot, set --item-id to a candidate, load in DOSBox, see
    what shows up, tag it.
  - **`docs/cookbook/edit-pc-hp.md`** is the first cookbook
    entry I've actually written instead of promised. Real
    commands against Brandon's DS2 played save (Ar'Anda PC 15
    at 34/57 HP); real before/after; documented caveats
    (derived fields, class changes, DS1 vs DS2). The
    walkthrough takes about 60 seconds end-to-end.
  - **Smoke**: copied factory DS2 CHARSAVE.GFF; edited Caron
    (PC 0) HP 21 → 999, max-HP 21 → 999, STR/CON 17 → 18,
    verified via list-pcs that the values stuck.
  - **What still doesn't ship**: `give-item` (append a new
    inventory slot) — needs RE of the `rdff_header.index` and
    `item.next` chaining conventions; deferred to v0.9.2+.
    `edit-item` covers the bootstrap-catalogue use case
    without the chunk-growth complexity.
  - **No new external deps**.

- **`tools/save-inspect/` v0.9.0** opens the modder-altitude
  discovery surface: `list-pcs` and `list-items`. First piece
  of the "no more JSON-edit-by-hand" pivot Brandon called out;
  the high-level fields above the v0.8.0 raw-JSON write path.
  - **`list-pcs <save>`** enumerates every CHAR record in the
    save with PC index, CHAR id, name, current/max HP, current/
    max PSP, current XP, and inventory count. Sorted by record
    order; the PC index is the `--pc N` handle every other
    PC-targeted command consumes.

    ```
    $ list-pcs CHARSAVE.GFF
    19 PC(s):
      PC  CHAR  Name             HP/Max  PSP/Max     XP  Items
      15    50  Ar'Anda          34/57  162/202  1400000  11
      18    53  Terrannus        88/113  11/91   2475000  10
      ...
    ```

  - **`list-items <save> --pc N`** lists one PC's inventory.
    Each row shows item slot index, raw `id`, quantity, charges,
    slot kind (`ARM`/`AMMO`/`HAND0`/etc.), and a name lookup
    from a new `syms/items.toml` catalogue. The catalogue ships
    empty by design; the bootstrap is Brandon's idea
    (2026-05-18):
    1. Run `list-items` to see the raw ids in your save
    2. Load the save in DOSBox; observe what each slot actually
       contains in the inventory screen
    3. Add rows to `syms/items.toml` (`id = -746, name = "Iron
       Sword"`)
    4. Re-run `list-items`; the name column populates
  - **`syms/items.toml`** scaffold + curation rule header.
    Per-game-agnostic by default; an `applies_to = ["ds2"]`
    field handles game-specific clashes when they surface.
  - Both subcommands `--json` for tooling.
  - Verified against both Brandon's played saves:
    - DS1 `~/.wine/.../Dark Sun/CHARSAVE.GFF`: 8 PCs
      (T'kir'taap, Aticus, Lanthazar, Garn, etc.)
    - DS2 `~/.wine/.../Dark Sun 2/CHARSAVE.GFF`: 19 records
      including the high-XP played party (Ar'Anda 1.4M XP,
      Terrannus 2.4M XP) with full 27-item inventories.
  - No new external deps (stdlib `tomllib` for the catalogue).
  - Next: `edit-pc` (high-leverage hp/psp/stat/xp edits via
    short flags) + `give-item` (open the bootstrap loop) +
    `docs/cookbook/edit-pc-hp.md` walkthrough.

- **`tools/region-render/` v0.7.1** fixes entity-sprite vertical
  orientation. Brandon caught it visually on both DS1 outdoor
  RGN02 and DS2 dungeon RGN033: NPCs and creatures rendered
  upside-down while tiles, walls, and furniture stayed correct.
  - **Root cause**: `image-extract`'s `decode_frame` produces
    sprites with the orientation that's right for ICON / WALL /
    TILE chunks (libgff's `create_ds1_rgba` flip is correct for
    those), but entity sprites in BOTH SEGOBJEX (DS1) and OBJEX
    (DS2) need the inverse orientation.
  - **Fix**: new `WallSprite::flip_vertical()` helper; applied
    once at each entity-load site (non-animated + animated
    paths). Walls and tiles unchanged.
  - Verified by direct ASCII-dump comparison of one SEGOBJEX
    entity decoded both ways (`head at top` only matches when
    the libgff flip is undone for entity sprites).
  - All 6 lib tests + corpus tests still pass.
  - Atlas rebuild on the corpus succeeds (DS1 33 regions, DS2
    20 regions); ready for Brandon to eyeball.

- **`tools/region-render/` v0.7.0** ships **animated GIF
  output**. Closes the B-tier sprint. `--animate-entities`
  already emits a numbered PNG sequence (v0.6.0); v0.7.0 adds
  `--gif` to bundle that sequence into a single shareable GIF
  via `ffmpeg`.

  ```sh
  region-render RGN02.GFF --palette-preset ds1-pink \
      --animate-entities --frame-count 8 \
      --gif --gif-fps 8 -o rgn02.gif
  # wrote rgn02.gif (1438763 bytes, 8 fps); frames stay in
  # rgn02-frames/ alongside
  ```

  Two-pass ffmpeg pipeline (palettegen + paletteuse with
  `dither=none`) so pixel-art colour fidelity stays clean.
  Default 8 fps; `--gif-fps N` overrides. Palette intermediate
  parks in `$TMPDIR` and is cleaned up after encode. Stderr
  from ffmpeg captured (surfaced only on encode failure) so the
  image2 demuxer's harmless sequence-pattern warning doesn't
  clutter the output.

  Per-frame PNGs land in a sibling `<output-stem>-frames/`
  directory so the user can keep them around (for sprite
  editing) or delete after.

  Text annotations (`--annotate` entity-name overlays + region-
  id labels) skipped from v0.7.0 — no in-tree Rust font
  available without a new dep. Land in v0.7.1 once we pick
  between embedding a bitmap font const, a small font crate, or
  the SVG-sidecar route.

  ffmpeg detected via a stdlib-only `$PATH` lookup (no `which`
  crate dep; reused the umbrella `opends` crate's pattern).
  Missing ffmpeg surfaces as a clear error message pointing
  to the install command.

- **`tools/gpl-asm/` v0.8.0** ships **declarative patch-script
  mode** (`gpl-asm --patch fix.patch chunk.bin -o new.bin`).
  B-tier item; the authoring surface darkfix patches will use
  once Phase 6 starts. Offset-based MVP; label-relative
  addressing (`at = "label_0x42 + 3"`) lands in v0.8.1.
  - **Patch TOML schema**:

    ```toml
    [[edit]]
    at_offset = 0x000B
    bytes_old = "54"
    bytes_new = "55"
    reason = "off-by-one in flag check"
    ```

    Hex strings accept `"01"`, `"0x01"`, `"01 02 03"` (spaces
    allowed). `at_offset` accepts decimal or TOML's hex form.
    `bytes_old` and `bytes_new` must be the same length
    (offset edits don't grow or shrink the chunk).
  - **bytes_old fingerprint verification**: the patcher refuses
    to apply if the original bytes at `at_offset` don't match.
    Protects against applying the wrong patch to the wrong
    chunk:

    ```
    Error: edit[0]: bytes_old fingerprint mismatch at offset 0x17
      expected: 99
      actual:   4f
      (refusing to apply; bytes_old verifies the patch targets the right chunk)
    ```
  - **`--dry-run`** reports what would change without writing.
  - **End-to-end smoke**: extracted DS1 GPLDATA GPL/1, wrote a
    two-edit patch (one no-op fingerprint check + one
    deliberate byte flip), ran dry-run + real apply, verified
    the byte changed.
  - **What v0.8.0 doesn't ship**: label-relative addressing
    (`at = "label_0x42 + 3"`) needs the disassembly context to
    resolve; v0.8.1 will pull that in. Snippet library
    (`%include`-able common idioms) is v0.8.x+ once the patch
    workflow has more shape.
  - **No new test failures**; existing 48 lib + 2 corpus tests
    pass at release.
  - **Toml dep added** to gpl-asm's `Cargo.toml` (workspace
    `toml = "0.8"`, already pre-approved for format I/O per
    spec §7a; same dep gpl-disasm uses for `syms/*.toml`).

- **`tools/gff-edit/` v0.6.0** ships **`gff-cat what <kind>
  <id>`**: per-chunk describer that combines the kind purpose
  (from KIND_CATALOGUE), chunk size, chunk-specific facts
  (bitmap dimensions, text preview), and a next-step pointer to
  the right tool. The "I have this chunk, what do I do with it?"
  answer in one command.

  ```
  $ gff-cat what RESOURCE.GFF BMP 3007
  BMP  id=3007  (9998 bytes)
    purpose: Bitmap, one or more frames.
    bitmap: 1 frame(s)
    frame 0 size: 320 x 200
    next step: `image-extract RESOURCE.GFF --kind BMP --id 3007 -o sprite.png`
  ```

  Dispatch by FOURCC family: bitmap kinds point at
  `image-extract`; `GPL `/`MAS ` at `gpl-disasm`;
  `TEXT`/`ETME`/`MERR`/`NAME`/`SPIN` show a text preview and
  point at `gff-cat dump-text`; save-record kinds
  (`CHAR`/`SAVE`/`STXT`/`PSIN`/`PSST`/`SPST`/`CACT`/`PREF`/
  `GREQ`/`ETAB`) point at `save-inspect`; `RMAP`/`GMAP` point
  at `region-render`. Kinds without a tool match still get the
  KIND_CATALOGUE purpose line.

  Pure-Rust facts only (no pulling tool-specific decoders as
  deps); the previews are best-effort from the chunk's header
  bytes.

  **Segmented-type GffBuilder** (deferred from v0.5.0) stays
  deferred to v0.6.1+. The use case (modders building GFFs from
  scratch with segmented chunks) is rare; sprite mods and save
  edits all work on existing GFFs which the v0.3.0 replace
  path covers. Promoting the segmented build only when a
  consumer needs it.

- **`tools/verify-install/` v0.3.0** ships **`--rollback`** and
  **`--summary`**. First of the B-tier ships from the human-
  friendliness sprint plan; small but useful both ways.
  - **`--rollback`** restores every file under
    `<install>/__verify-install-backup/` to its original
    location and removes the backup dir. The inverse of
    v0.2.0's `--repair`. Pairs with `--dry-run` to preview
    what would be restored. No-op (with a clear message) if
    no backup dir exists.
  - **`--summary`** emits a one-line plain-English status
    instead of the full hash-by-hash table. For the
    common-case modder running `verify-install` out of habit:
    "is my install in shape; yes / no; what to do." Pluralises
    properly ("1 mismatched file" not "1 mismatched files").
    Frames the next-step advice (`--repair`, `--rollback`,
    `--show-extras`) so the user doesn't have to remember which
    flag does what.

    ```
    $ verify-install --game ds1 --summary
    Your Dark Sun: Shattered Lands install matches the canonical
    GOG hash manifest. 111 extras (probably saves / DOSBox
    config / DSUN.LOG). 17 runtime-state files skipped by policy.
      (57 files matched, no mismatches, no missing files.)
    ```

- **`tools/opcode-fuzz/` v0.3.0** ships **`boot-chunks`** (the
  discovery half of the long-promised fuzz loop) plus a
  forward-looking **`recipes/`** scaffold. Item #9 of the
  human-friendliness sprint; the inherited S10 from yesterday
  with three of its four dependencies now landed
  (`save-inspect v0.7.0` + `v0.8.0`, `repro v0.4.0`,
  `gff-edit v0.5.0` builder).
  - **`opcode-fuzz boot-chunks <gff>`**: drives `gpl-disasm
    --global-cfg --json` and reports per-chunk
    `inbound_calls` counts. Chunks with **zero inbound
    `gpl global sub` edges** are entry points the engine
    must dispatch directly (since nobody else does), so
    they're the safest swap target for fuzz runs. Output is
    JSON with `boot_candidates` + `most_called` arrays plus a
    stderr summary line.
    - DS1 GPLDATA: 129 boot candidates out of 250 chunks
      (587 edges).
    - DS2 GPLDATA: 196 boot candidates out of 350 chunks
      (797 edges).
    - DS1's most-called chunk is GPL/74 (169 inbound calls);
      DS2's is GPL/27 (218 inbound calls). Those are engine
      utility / helper functions the toolkit can curate names
      for once the role is RE'd.
  - **`recipes/` scaffold** with a README documenting the
    intended recipe format and the reasons it's not active
    yet. The `fuzz <opcode>` subcommand needs either a
    short-form preprocessor in opcode-fuzz or a `gpl-asm
    v0.8.0` extension that accepts mnemonic-only input
    (today's gpl-asm requires the full `<offset> <byte>
    <mnemonic>` listing format). Recipe-driven `fuzz` ships
    in v0.3.1+ once that format settles.
  - **Existing v0.2.0 subcommands** (`extract`, `pack`,
    `roundtrip`, `run`) unchanged. Corpus round-trip stays at
    250 / 250 byte-identical on DS1 GPLDATA.
  - **No `fuzz` subcommand in v0.3.0**. Scope-cut for honesty:
    a half-functional fuzz would mislead more than it'd help.
    The discovery half (boot-chunks) ships now; the recipe-
    execution half waits.

- **`tools/repro/` v0.4.0** ships **scheduled keystrokes**
  (ydotool) and **video capture** (ffmpeg). Item #8 of the
  human-friendliness sprint; the deferred S9 from yesterday's
  plan with Brandon's deps approved 2026-05-17. Unblocks the
  deterministic-execution half of `opcode-fuzz v0.3.0`'s
  automated discovery loop and any future "click through this
  menu, then trigger the bug" fixture.
  - **`[[trigger.keystrokes]]` schema** in `bug.toml`:

    ```toml
    [[trigger.keystrokes]]
    at_seconds = 8
    send = "Return"            # KEY_ENTER

    [[trigger.keystrokes]]
    at_seconds = 12
    send = "type:dsun"         # type a string

    [[trigger.keystrokes]]
    at_seconds = 15
    send = "16:1 16:0"          # raw scancode pairs
    ```

    Friendly aliases for `Return` / `Enter` / `space` /
    `Escape` / `Esc` / `Tab`; `type:<string>` for arbitrary
    typed input; raw `<code>:<state> <code>:<state>` pairs
    for arbitrary scancodes. The scheduler runs as a daemon
    thread; keystrokes that miss their window log to
    `<scratch>/automation.log` but never abort the run.
  - **`[expected].record_video`** flag enables `ffmpeg -f
    x11grab` capture to `<scratch>/repro.mp4`. Picks up
    `$DISPLAY` automatically; XWayland surfaces (which
    DOSBox-Staging produces by default on GNOME-Wayland) are
    visible to x11grab, so no Wayland-native screencast
    portal is needed. Encoded as libx264 yuv420p 24fps mute
    with the `veryfast` preset. ffmpeg gets `SIGINT` at
    DOSBox-exit so the MP4 finalises cleanly.
  - **Graceful degradation**. The harness probes `ydotool`
    and `ffmpeg` on `$PATH`. Missing dependency logs a
    warning to `automation.log` and skips that automation
    surface; the bug run still completes. Modders without
    ydotool installed still get the v0.3.0 functionality.
  - **`automation.log`** captures every keystroke's
    `+<elapsed>s <args> -> <result>` line and the recorder's
    lifecycle. Useful for debugging timing issues
    independently of `dosbox.log`.
  - **`BugFixture.keystrokes` + `BugFixture.record_video`**
    dataclass fields default to `[]` and `False`
    respectively, so existing fixtures (`ds1-smoke`,
    `ds2-smoke`) keep their v0.3.0 behaviour without
    modification.
  - **README walkthrough** for the one-time `dnf install
    ydotool` + `systemctl --user enable --now ydotoold`
    setup. Notes that group / udev rules may require a
    logout + back-in to take effect.

- **`tools/atlas/` v0.1.1** fixes DS1 region rendering. v0.1.0
  inherited `region-render`'s default `--palette-preset
  ds1-rust` (CPAL:200), which flattens every DS1 region into
  one rusty-red colour family and loses vegetation / sand /
  water distinctions (the engine's per-region palette routine
  isn't fully RE'd yet; see `docs/dsun-exe-re.md` §4.5). v0.1.1
  detects DS1 regions by stem length (`RGN??` = DS1, `RGN???`
  = DS2) and passes `--palette-preset ds1-pink` (PAL :1000)
  for DS1 only. Terrain types are now visually distinct. DS2
  unchanged (uses inline per-region palettes correctly).
  Pink off-camera void is a known cosmetic quirk pending the
  per-region palette RE.

- **`tools/atlas/` v0.1.0** (new crate). Item #7 of the
  human-friendliness sprint: the static-HTML site generator.
  Drives the existing tools as subprocesses and produces a
  browsable directory of HTML pages. The first "open the whole
  game and look around" surface on the toolkit.
  - **One subcommand**: `atlas build --games-dir DIR -o OUT`.
    Auto-detects game installs by presence of `DSUN.EXE` (one
    subdir per game, or a single game install).
  - **Three sections per game**:
    - **Sprite gallery**: `image-extract --all` drives every
      BMP / PORT / ICON / BMAP / OMAP / TILE chunk in
      `RESOURCE.GFF` into PNG; one paginated grid page per
      game (`sprites-RESOURCE.html`).
    - **Region maps**: `region-render` drives every `RGN*.GFF`
      into a PNG; one inline-image page per game
      (`regions.html`).
    - **Dialog browser**: drives `dialog-extract --format
      html` against `GPLDATA.GFF` and threads the cross-
      section nav bar into the output.
  - **Cross-section nav** carried through every page; root
    `index.html` links to per-game indexes; per-game indexes
    link to each section. Static; opens via `file://`; no
    JavaScript.
  - **Tool discovery** mirrors the umbrella `opends` crate:
    `target/release/` > `target/debug/` > `$PATH`; Python
    tools resolve to `tools/<crate>/<script>.py` and invoke
    via `python3`. Missing tools print a warning and skip
    that section gracefully.
  - **Smoke against the corpus**: 1685 sprites (DS1 649 +
    DS2 1036), 53 region maps (DS1 33 + DS2 20), 2 dialog
    browsers. Full site ~92 MB on disk.
  - **Stdlib-only Python**; no template engine, no third-
    party deps. CSS is a single embedded string injected
    into every page. Templating uses Python f-strings.
  - **No tests**. v0.1.0 is mostly subprocess plumbing; the
    smoke is the corpus-build above. Failed builds surface
    per-section warnings instead of crashing.
  - **Out of v0.1.0 scope**: cross-references between
    sections, search, save inspector, GPL chunk index,
    per-frame sprite animation. Each is a v0.2.0 candidate.

- **`tools/dialog-extract/` v0.7.0** ships **`--format
  transcript`** (per-NPC plain-text dialog listing) and
  **`--format html`** (single-file static HTML browser).
  Item #6 of the human-friendliness sprint. v0.1.0 - v0.6.0
  shipped the structured JSON dialog tree; v0.7.0 closes the
  loop with human-readable surfaces a player or writer-curious
  modder can actually read.
  - **`--format transcript`** emits a markdown-style per-chunk
    listing: header naming the chunk + speaker, indented body
    of every dialog string in source order. DS1 GPLDATA
    produces an 18349-line transcript covering 215 chunks /
    17699 strings.

    ```
    ## GPL-1: Iniya
      (DS1 starting cell-block; the imprisoned mage NPC.)

      Iniya: Free! Finally free! I will destroy you all! Ha ha ha!
      Iniya: Please help me. I was betrayed and locked in my own dungeon.
      ...
    ```

  - **`--format html`** emits a single static HTML page with
    embedded CSS, collapsible `<details>` per chunk, colour-
    coded unresolved strings. Works opened directly via
    `file://`; no JavaScript, no external assets. The on-ramp
    to the `atlas` tool's dialog browser. DS1 GPLDATA full
    output: 1.9 MB.
  - **`syms/speakers.toml`** curated catalogue: maps GPL
    chunk id to NPC name. Loaded by the transcript / HTML
    emitters; missing rows fall back to `"GPL chunk N"`.
    v0.7.0 ships with one verified entry (Iniya, DS1 GPL
    chunk 1; sourced from gpl-disasm's curated function entry)
    and grows organically.
  - **`--format json`** (default) stays unchanged for back-
    compat with v0.6.0 consumers (`opends find`,
    `opcode-fuzz`).
  - **Bug fix**: render_transcript previously crashed on a
    null `value` from unresolved strings (`'NoneType' has no
    attribute 'strip'`). Handled gracefully.

- **`tools/save-inspect/` v0.8.0** ships the **write path**:
  `save-edit` takes a JSON edit, re-encodes every chunk, and
  writes a patched GFF. Item #5 of the human-friendliness
  sprint and the first true end-to-end mod workflow on the
  toolkit (decode → edit field → encode → game-compatible
  output).
  - **`save-edit` subcommand**:

    ```sh
    save-inspect.py CHARSAVE.GFF -o save.json
    # ... edit save.json (e.g. bump combat.hp from 54 to 999) ...
    save-inspect.py save-edit save.json CHARSAVE.GFF -o patched.gff
    ```

    Backup-before-write (`<output>.bak.<mtime>`), `--dry-run`
    mode, `--no-backup` opt-out. Refuses to add or remove
    chunks (count must match the original).
  - **`roundtrip` subcommand**: built-in regression check.
    Decodes every chunk, re-encodes, asserts byte-identical;
    exit 0 if every chunk round-trips, exit 1 if any fail.
    Corpus result: **27 / 27** chunks for DS1 CHARSAVE,
    **98 / 98** for DS2 CHARSAVE, **1 / 1** for the factory
    DARKSAVE, **63 / 63** for Brandon's played DS1
    DARKRUN.GFF. **100% chunk-level byte-identity across
    every save in the corpus.**
  - **Encoders for every existing decoder branch**:
    `_encode_combat` / `_encode_combat_ds2` (combat
    sub-block, 58 / 49 bytes), `_encode_character` /
    `_encode_character_ds2` (71-72 / 66 bytes),
    `_encode_item` (21 / 23 bytes), `_encode_stats`,
    `_encode_saving_throw`, plus chunk-level paths for
    CHAR / PSIN / PSST / TEXT / STXT / SAVE / ETME / ETAB.
    Mechanical inverse of each `_decode_X`; same field
    ordering and pack format.
  - **Pure-Python GFF writer** (`write_gff`). Inverse of
    `parse_gff` for indexed-only files: 28-byte header,
    contiguous chunk-data area starting at offset 28,
    TOC at the end with type list and per-chunk
    `(id, offset, length)`. File-level output is smaller
    than the original (the original carries 1.6 KB of
    pre-allocated gap space between chunks; the writer
    packs contiguously). Engine-equivalent; gaps are
    layout-only.
  - **Round-trip fidelity fixes**:
    - **Combat name field**: real saves leave non-zero
      garbage in the name field's trailing padding bytes
      (the engine doesn't always zero the buffer between
      writes). The decoder now captures `_name_raw_hex`
      alongside `name`; the encoder prefers the raw hex
      so round-trip stays byte-identical. When the user
      edits `name` and deletes `_name_raw_hex`, the
      encoder falls back to null-padded encoding (clean,
      not byte-identical-with-original, still
      engine-valid).
    - **Item decoder truncation**: DS1's 21-byte items
      truncate at the 2-byte `priority` field (1 byte
      left at pos 20). The decoder now captures that
      trailing byte in `_trailing_hex` so the encoder
      can re-emit it. Same fix shape for any future
      decoder that returns early on truncation.
    - **Opaque-chunk full-bytes capture**: `SAVE`,
      `ETAB`, `SPST`, `CACT`, `PREF`, `GREQ` decoders
      now also emit `_raw_bytes_hex` (full bytes)
      alongside the truncated `raw_hex` preview. The
      preview stays for human readability; the full
      hex is what the encoder uses so chunks bigger
      than the 128-byte preview cap round-trip
      correctly. Necessary because DARKRUN SAVE chunks
      hit 10 KB.
  - **End-to-end smoke**: edit CHAR-36 combat.hp from 54
    to 999 via the JSON, run save-edit, re-decode the
    patched GFF: hp = 999 in the output. The first true
    mod workflow on the toolkit.

- **`tools/save-inspect/` v0.7.0** ships SAVE-chunk
  structural decoding plus a `save-diff` subcommand for
  empirical world-state RE. Item #4 of the human-friendliness
  sprint; inherits S8's scope (DARKRUN-side decode) from
  yesterday's plan with the realistic ceiling: schema is
  empirically incomplete, so v0.7.0 surfaces what's locked
  (chunk-id-keyed shape; u16 scalars in the 2-byte family)
  and leaves the body as opaque hex with the per-game tag
  `_format: ds1_save_chunk`. DS2's wire format probably
  matches but we have no played DS2 sample to verify; the
  tag is updated once that data exists.
  - **Four new decoder branches in `decode_chunk`**: `SAVE`
    (per-region world state inside DARKRUN.GFF; ~60 per
    save), `STXT` (the save name, e.g. the "FUCK" save;
    null-terminated ASCII padded to chunk length), `ETAB`
    (the engine entity table; 10 KB allocation, mostly zero
    in fresh saves; opaque hex + leading-zero-byte
    fingerprint), `ETME` (engine-template-metadata text
    block present in both factory DARKSAVE and played
    DARKRUN; surfaced as text).
  - **`save-diff` subcommand**: new sibling to the existing
    `diff` (which compares CHARSAVE summaries). `save-diff`
    operates at the chunk-byte level: for each chunk that
    exists in both files, reports `byte_diff_count` and
    `first_diff_offset` plus 64-byte hex previews of both
    sides. Defaults to SAVE-chunks-only; `--all-chunks`
    extends to ETAB / STXT / ETME / etc.
    The intent is empirical SAVE-chunk RE: do an action
    in-game, save, compare against the pre-action save, see
    exactly which bytes changed in which chunk. Drops the
    diff size from "all changed fields per chunk" (the
    existing `diff`) to "byte-counts per chunk."
  - **Inventory captured from the one Brandon-played DS1
    save** (the "FUCK" save at
    `~/.wine/drive_c/GOG Games/Dark Sun/DARKRUN.GFF`):
    60 SAVE chunks ranging from 2 bytes to 10240 bytes.
    Notable patterns:
    - Chunk id 1 (10240 bytes): the largest; almost
      certainly the party / PC data.
    - Chunk ids 10-17: each exactly 2 bytes (u16 LE).
      v0.7.0 decodes them as `u16_value`.
    - Chunk id 18 (51 bytes, all 0x01 in the sample save):
      51 boolean flags; speculation is region-visited or
      party-known flags.
    - All other ids: opaque hex, schema TBD.
  - **No tests** for the new decoders (the existing CHAR/
    PSIN/etc. decoders also ship test-free in the script).
    Smoke covers all four branches on the played DARKRUN +
    the regression on the v0.6.0 CHARSAVE inspect / diff
    paths.

- **`tools/opends/` v0.1.0** (new crate). Item #3 of the
  human-friendliness sprint: the umbrella CLI that auto-
  dispatches by file magic. New contributors who don't yet
  know which tool reads which file have a single entry point:
  `opends inspect <file>`.
  - **Subcommands**: `inspect`, `render`, `find`, `extract`,
    `tools`. All thin shells over the existing toolkit; no
    logic reimplemented.
  - **`opends inspect <file>`**: GFF magic (`GFFI`) →
    `gff-cat info`; save filenames (`DARKRUN.GFF`,
    `CHARSAVE.GFF`, `DARKSAVE.GFF`, `SAVE??.SAV`) →
    `save-inspect`; PNG signature → inline summary +
    `image-pack` pointer (for indexed) or conversion hint
    (for non-indexed); anything else → magic-byte readout.
  - **`opends tools`**: reads every wrapped tool's `VERSION`
    file and prints a table with the resolved binary path,
    so contributors see at a glance what's built and where.
  - **Tool discovery**: prefers in-tree
    `<workspace-root>/target/release/<name>` over
    `target/debug/<name>` over `$PATH`. Workspace root is
    found by walking up from the running binary's directory
    looking for `Cargo.lock` and a sibling `tools/` dir.
    Python tools (`*.py`) resolve to
    `<workspace-root>/tools/<crate>/<name>.py` and invoke via
    `python3`.
  - **Workspace registration**: added `tools/opends` to the
    workspace `Cargo.toml` members list.
  - **No tests yet**; v0.1.0 is mostly subprocess plumbing and
    file-magic detection. End-to-end smoke covers all three
    dispatch paths (GFF / save / PNG) on real game files.

- **`tools/image-extract/` v0.4.0** ships the inverse of the
  v0.1.0 decoder: a companion `image-pack` binary that encodes
  palette-indexed PNGs back into DS1 RLE bitmap chunks. Item
  #2 of the human-friendliness sprint; the single feature that
  takes sprite modding from "look at the sprite" to "ship a
  sprite mod." Also catches up the lapsed `VERSION` file (it
  was stuck at `0.2.1` after the v0.3.0 ship; v0.4.0 corrects
  it).
  - **Library**: new public `encode_bitmap_rle(frames: &[Frame])
    -> Result<Vec<u8>>`. Emits the full chunk shape (u32
    chunk_size + u16 frame_count + u32 × N frame_offsets +
    per-frame DS1 RLE bodies). Every frame encodes as DS1 RLE
    regardless of the input `frame_type`; the engine reads
    PLNR and PLAN transparently from chunks of any kind, so
    RLE output is universally compatible. Frames whose
    `frame_type` is the composited `STRP` marker are rejected
    (those aren't real game frames).
  - **Greedy RLE encoder**: a repeated run of N >= 2 identical
    pixels emits as one byte saved over the direct form;
    otherwise extends a direct run until the next repeated
    pair or the 128-pixel cap. Multi-span row emission handles
    wide rows (e.g. 320-pixel DS sprite rows whose RLE payload
    exceeds the 255-byte single-span `compressed_length`
    field): the encoder splits cleanly on code boundaries and
    tracks per-span `startx` precisely, including the 9-bit
    extended startx flag for `startx >= 256`.
  - **Binary**: new `image-pack` CLI. Reads a palette-indexed
    8-bit PNG and writes the encoded chunk to `-o <file>` or
    stdout (default). `--frames-dir <dir>` packs every `*.png`
    in sorted-filename order as a multi-frame chunk (round-
    trips the v0.3.0 `image-extract --frames-all` output).
    Pipe the stdout into `gff-cat replace <gff> <kind> <id> -`
    to slot the new bitmap into a real game file.
  - **Round-trip property test**: 883 / 883 DS1 RLE frames
    across the DS1 + DS2 corpus (GPLDATA + RESOURCE in both
    games) pack → re-parse → decode pixel-identical to the
    original. 855 PLNR + 237 PLAN frames are skipped per
    design (no encoder for those formats; the engine reads
    all three so it's fine). The one known malformed frame
    from v0.2.1 (DS1 `RESOURCE.GFF:ICON/0x7f9` frame 2) stays
    known-broken; it errored at decode and never reached the
    encoder.
  - **End-to-end smoke**: extract ICON 2000 from DS1
    `RESOURCE.GFF` as a PNG, run `image-pack` on it, replace
    the chunk via `gff-cat replace`, re-extract: the two PNGs
    are byte-identical. The full modder workflow works on a
    real chunk.
  - **Tests**: 9 new lib tests covering the RLE encoder
    (single-pixel, repeated-pair, mixed runs, 128-pixel cap
    on both forms, multi-row with zero rows, all-zero frame,
    multi-frame chunk, empty / STRP rejection) plus the
    `pack_corpus.rs` property test above. 17 / 17 lib tests
    pass; corpus test passes with 883 frames round-tripped.

- **`tools/gpl-disasm/` v0.6.0** is the first ship of the
  human-friendliness sprint (planned in `docs/next-versions.md`,
  retired 2026-06-10 once the sprint shipped; in git history). Two
  modder-facing wins, plus the latent variables-bug fix the
  v0.5.0 ship missed.
  - **Per-chunk local-variable overlays**. New
    `syms/locals.toml` schema with per-kind tables (`[[lbyte]]`
    / `[[lnum]]` / `[[lbignum]]` / `[[lflag]]` / `[[lname]]`
    / `[[lstring]]`) keyed by `(file, kind, chunk_id, id,
    name, doc?)`. Decoration renders as `LBYTE[7
    (loop_counter)]` in text output and as a `name` field on
    `Expression::Variable` in JSON, exactly mirroring v0.5.0's
    global pass. Library: `Symbols::local_name` lookup +
    `Symbols::apply_to_locals(result, file, kind, chunk_id)`
    walker; the CLI wires it in at every disassembly site
    (single-chunk, `--all`, `--global-cfg`). v0.6.0 ships
    `syms/locals.toml` empty by design; the catalogue grows
    organically per the curation rule in the file's header.
  - **DSO-symbol importer script** at
    `tools/gpl-disasm/scripts/import-dso-symbols.py` (stdlib-
    only Python). Parses `.dso-online/tools/symbols.txt`
    (3,527 functions + 2,246 globals from the DSO v1.0
    Crimson Sands client) and emits review-ready proposals:
    - `--opcodes-proposed`: 100 TOML opcode-byte rename
      proposals where libgff's mnemonic matches DSO's
      `Decode*` handler family by PascalCase equivalence.
      Cherry-pick into `syms/opcodes.toml`; the existing
      curation rule (don't relax) still applies; v0.6.0
      itself commits zero rows (the script is the review
      surface, not the writer).
    - `--unmatched-decoders`: 15 DSO `Decode*` names with no
      obvious libgff slot. Most are libgff's `*trigger`
      family under DSO's `*check` naming (e.g.
      `DecodeAttackcheck` against libgff's
      `gpl attacktrigger` at 0x65); `DecodeDefault` is real
      (libgff's `gpl default` at 0x26 names a real handler,
      not a placeholder). These are research candidates for
      a follow-up curation pass.
    - `--functions-summary` / `--globals-summary`: markdown
      tables of GPL/GFF-related engine intrinsics suitable
      for pasting into `docs/dso-symbols.md`'s "Highest-value
      symbols" tier.
    The script never writes to `syms/` directly. Per the
    curation rule, every row commit is hand-reviewed.
  - **Bug fix (latent from v0.5.0)**: the single-chunk
    disassembly path (`gpl-disasm --kind GPL --id N`) didn't
    call `apply_to_variables`, so globals went undecorated
    even when `variables.toml` had entries. The `--all` and
    `--global-cfg` paths got it right. Both paths now also
    call the new `apply_to_locals`.
  - **Bug fix (latent from v0.5.0)**: the CLI's `load_symbols`
    early-out only checked `opcodes.is_empty() &&
    functions.is_empty()`, so a `syms/` dir with *only*
    variables (or, now, locals) was treated as empty and
    discarded. The check now covers all four catalogues.
  - **Tests**: three new lib tests
    (`symbols_load_locals_from_toml`,
    `apply_to_locals_decorates_matching_chunk_only`,
    `apply_to_locals_skips_non_matching_chunk`) plus the
    existing 600/600 corpus round-trip stays clean.

- **`tools/gpl-asm/` v0.7.0** adds two real authoring
  features on top of v0.6.0's directive infrastructure. Pure
  preprocessor work; the encoder is unchanged, and the
  corpus round-trip stays at 600 / 600.
  - **Parameterised macros**: `%define <name>(<params>)
    <body>`. A call `<name>(actual1, actual2)` at identifier
    positions expands to `<body>` with `<params>` bound to
    the actuals. Arguments are pre-expanded against the
    outer `%define` table before binding so plain defines
    flow naturally into macro args (e.g. `%define SLOT 9` +
    `%define wrap(id) GBYTE[id]` + `wrap(SLOT)` → `GBYTE
    [9]`). Wrong-arity calls surface as
    `MacroParamCount`; duplicate param names as
    `DuplicateMacroParam`. Macro names share the namespace
    with plain `%define` (declaring both is a
    `DuplicateDefine`).
  - **`@include "path/file.asm"`** for textual include
    relative to the current file. Used to split common
    macro / define libraries out of an instruction file.
    Canonical-path circular-include guard
    (`CircularInclude`); `INCLUDE_DEPTH_LIMIT = 16` cap
    (`IncludeDepthExceeded`). Errors land as
    `BadIncludeSyntax`, `IncludeIo`, etc.
  - **`apply_defines` signature change**: now also takes a
    `macros` table and `line_no` so macro-expansion errors
    can be reported with line attribution. Existing
    consumers update mechanically; the preprocessor is the
    only intra-crate caller.
  - **Library API surfaces**: `INCLUDE_DEPTH_LIMIT`
    constant; private `preprocess_with_root(input, root)`
    for tests / future programmatic-include use. The public
    `parse(input)` continues to resolve `@include` relative
    to `"."` (the process cwd).
  - **Tests**: 6 new lib tests cover macro expansion,
    wrong-arity, duplicate params, plain-define-flows-into-
    macro, `@include` happy path, circular detection, and
    missing-file. 600 / 600 release-mode corpus round-trip
    unchanged.

- **`tools/gpl-disasm/` v0.5.0** + **`tools/gpl-asm/`
  decorated-form parser**: variable-naming infrastructure.
  Currently the disassembler emits `GBYTE[42]`, `GNUM[3]`,
  etc. as raw indices; v0.5.0 lets a curated
  `syms/variables.toml` attach names to specific slots,
  decorating output across the toolkit. Every consumer
  (gpl-asm, dialog-extract, opcode-fuzz) sees the names
  automatically because the disasm output is the universal
  input format.
  - **`syms/variables.toml`** schema: one `[[gbyte]]` /
    `[[gnum]]` / `[[gbignum]]` / `[[gflag]]` / `[[gname]]` /
    `[[gstring]]` per-kind array. Each entry has `id`
    (u16), `name` (string), and optional `doc`. Locals
    (LSTR / LNUM / etc.) are intentionally out of scope
    (per-chunk override surface queued for v0.6.0+).
  - **`Expression::Variable.name`** optional field
    (`Option<Cow<'static, str>>`), serde-skipped when None
    so the v0.4.6 JSON shape is unchanged for callers that
    don't ship a catalogue.
  - **Text rendering**: `KIND[id]` when no name, `KIND[id
    (NAME)]` when curated. Decorated form survives a
    `gpl-asm` parse round-trip: the parser accepts both
    plain and decorated forms, discards the annotation
    (it's documentation, not encoding), and rebuilds the
    dispatch byte from `var_kind + id + extended`.
  - **`Symbols::apply_to_variables`** walks every
    instruction's params (including nested `Expression::
    RetVal::inner_params`) and decorates matching
    `(VarKind, id)` pairs. The `gpl-disasm` binary now
    calls it alongside `apply_to_labels` / `apply_to_
    mnemonics` on every disasm pass.
  - **Empty catalogue ships in v0.5.0**: `syms/variables
    .toml` carries the schema commentary and zero entries.
    The catalogue grows organically as the toolkit
    surfaces meaningful slots; adding an entry has no
    effect on bytecode encoding (display only).
  - **Corpus**: 600 / 600 gpl-asm corpus round-trip
    unchanged (the decoration affects display, not the
    encoded byte stream). New unit tests:
    `symbols_load_variables_from_toml`,
    `apply_to_variables_decorates_matching_expressions`.

- **`tools/dialog-extract/` v0.6.0** orders the v0.5.0
  `possible_writers` array by graph distance, so the closest
  writer surfaces first. The reverse-CFG BFS now records
  shortest-path distance per ancestor (BFS instead of v0.5's
  visited-set DFS); each writer record carries a `distance`
  field (0 = same chunk, 1 = direct caller, N = N hops);
  `possible_writers` sorts ascending by
  `(distance, kind, id, offset)`. `null` distances (the
  global-fallback case where no static path connects writer
  to reader) sort last.
  - **`--quick-resolve`** flag restricts the list to
    `distance <= 1` (same-chunk + direct callers). Useful
    for the common case where the LSTR is set by the
    immediate caller and the longer ancestor tail is noise.
    Filter label becomes
    `callgraph-reachable+quick-resolve` (or the matching
    fallback variant). Slots whose only candidates were
    further-away callers move from `possible_resolved` to
    `no_writers` in `lstr_stats` under this mode.
  - **Corpus signal (DS1 GPLDATA)**: 255 LSTR reads, 230
    exact (90.2%), 25 via `possible_writers`. Writer
    distance histogram is bimodal: 31 at distance 0
    (same-chunk writes the flat-scan tracker missed) and
    68 at distance `null` (global-fallback). The "caller
    writes then callee reads" idiom is dominated by exact
    resolution (the v0.4.0 path-aware tracker catches it),
    so distance 1+ is uncommon in the unresolved tail.
    `--quick-resolve` drops to 23 reads with writers; the
    2 global-fallback cases become `no_writers` since
    `null > 1`.
  - **No regression**: exact resolution count is unchanged
    (still 230 / 255 on DS1 GPLDATA). The only change is
    the *order* of the writer list and the new `distance`
    field; v0.5.0 consumers that ignored the order keep
    working.

- **`tools/region-render/` v0.6.0** pivots past the
  palette-cycle wall (`docs/dsun-exe-re.md` §4.5 documents
  why the DSUN.EXE byte-pattern search has run its course on
  that surface) and animates the **entity layer** instead.
  Uses `image-extract v0.3.0`'s multi-frame decoder to walk
  every ETAB-referenced BMP's full `frame_count` and emit a
  numbered PNG sequence with each entity stepping through
  its cycle.
  - **`--animate-entities`** flag. Loads every frame of each
    referenced BMP via the new library helper
    `with_animated_entities_from`. Emits
    `<output>/<stem>-frame-<N>.png` per frame.
  - **`--frame-count N`** override. Default: the max
    `frame_count` across all loaded sprites (DS1 RGN02 max
    is 15 frames; every entity cycles through at least
    once); `--frame-count` can cap or extend the sequence.
    Each entity loops independently within the span via
    `entity.frames[global_frame % entity.frames.len()]`.
  - **No regression**. Frame 0 of an `--animate-entities`
    render is byte-identical to v0.5.0's single-frame
    output (verified on DS1 RGN02: same SHA-256). The
    frame-0-only path keeps the v0.5.0 `with_entities_from`
    API; the new path populates a separate multi-frame map
    (`entity_sprite_frames`).
  - **Library**: `with_animated_entities_from`,
    `render_indexed_frame(N)`, `write_png_frame(path, N)`,
    `max_entity_frame_count()`,
    `entity_sprite_frames_count()`. Frame decode failures
    are silently dropped at the per-frame level (the cycle
    wraps without that frame); whole-BMP failures land in
    `entity_decode_failures` as before.
  - Palette animation stays parked behind the cycle-table
    wall; per-entity timing (each sprite has its own
    animation rate in the engine) and GIF / single-file
    output remain v0.7.0+ work.

- **`tools/image-extract/` v0.3.0** ships multi-frame sprite
  export. v0.2.x decoded every frame of every multi-frame
  chunk under `--all`, but the single-chunk path only emitted
  `--frame N`. v0.3.0 closes that gap with two explicit
  entry points plus a new library helper that
  `region-render v0.6.0` (animated entities) will call.
  - **Library**: `Bitmap::decode_all_frames(&self) ->
    Vec<Result<Frame>>` returns one `Result` per frame index
    so callers keep the good frames when one is malformed
    (the DS1 `RESOURCE.GFF:ICON/0x7f9` frame-2 case).
    `composite_horizontal_strip(frames) -> Option<Frame>`
    lays frames out left-to-right, top-aligned, padded with
    palette index 0; the composite is itself a `Frame` with
    `frame_type = Unknown("STRP")` so callers can
    distinguish a spritesheet from a game-encoded frame.
  - **CLI**: `--frames-all` (single chunk; emits
    `<KIND>-<ID>-frame-<N>.png` per frame to `-o <dir>`).
    `--spritesheet` (single chunk; composites every frame
    into one horizontal-strip PNG). Both flags are mutually
    exclusive on a single chunk. With `--all`,
    `--spritesheet` switches the bulk emitter from per-frame
    PNGs to one spritesheet per multi-frame chunk.
  - **Verified** on a known multi-frame chunk (DS1 ICON
    2000, 4 frames of 59x18 → 236x18 strip).
  - Corpus stats unchanged from v0.2.1: 1,975 / 1,976 frames
    decode across the DS1 + DS2 corpus. The single
    `EXPECTED_FAILURES` entry (ICON `0x7f9` frame 2) stays
    pinned.

- **`tools/gff-edit/` v0.5.0** adds construction-from-scratch
  via a new `GffBuilder` library type. Phase 1 was already
  the foundation library for read / write / extract / replace
  / bulk-dump / text-codec / JSON / catalogue; v0.5.0 closes
  the last common gap by letting downstream tools synthesise
  a new GFF without having to start from an existing one.
  - **`GffBuilder` API**. `new()` starts empty; `add_chunk
    (kind, id, payload)` appends; `with_data0(v)` and
    `with_file_flags(v)` override the header sentinels;
    `build()` returns `Vec<u8>` ready for `Gff::from_bytes`.
    Types appear in first-seen-kind order; chunks within a
    type stay in insertion order. Free list emits a single
    zero-count entry (matches the dominant corpus shape).
  - **`builder_from_gff(&Gff) -> Option<GffBuilder>`** for
    round-tripping a parsed GFF back through the builder.
    Returns `None` if the input has any segmented types.
  - **Indexed-only**. Segmented build (the `0x80000000` flag
    plus the secondary-table + `GFFI` cross-reference dance)
    is deferred to v0.6.0. The builder rejects segmented
    inputs via `builder_from_gff` returning `None`; the
    standalone `add_chunk` path can only express indexed
    chunks.
  - **Corpus round-trip test**
    (`tests/builder_corpus.rs`): parse → builder → rebuild →
    re-parse on every GFF under `.games/` and the Wine
    install. **50 indexed-only GFFs** verified structurally
    equivalent (same chunks: kind, id, payload bytes). **78
    segmented-type GFFs skipped** awaiting v0.6.0.
    Byte-identical rebuild is *not* the property tested:
    existing GFFs are not in a single canonical layout
    (types-list ordering, dead space from prior edits, and
    free-list shape all vary), so the test asserts chunk-
    level equivalence instead.
  - **No CLI surface**. v0.5.0 is library-only; `gff-cat`
    subcommands don't gain a builder entry point in this
    release. The first CLI consumer of the builder will be
    `opcode-fuzz v0.3.0` (recipe synthesis).
  - Unit tests: minimal two-chunk GFF, first-seen kind
    ordering, `data0` / `file_flags` round-trip, empty
    builder, and `builder_from_gff` re-parse equivalence.

- **`tools/verify-install/` v0.2.0** turns the verifier into a
  fix-it-yourself tool and gives downstream tooling (the repro
  harness, CI, the planned opcode-fuzz pre-run check) a stable
  machine-readable surface.
  - **`--json`** emits the full verify report on stdout as
    `{tool, version, install, manifest, meta, summary,
    mismatched, missing, extras, skipped, ok}`. Lists are
    sorted for stable diffs across runs. The human-text path
    is unchanged.
  - **`--repair <installer.exe>`** restores the canonical bytes
    of every mismatched / missing file from the GOG installer.
    Shells to `innoextract -e -d <tmp> <installer>` to stage
    the pristine tree, then copies each requested file into
    place over a same-path backup at
    `<install>/__verify-install-backup/<path>` (always created
    before overwriting). The backup directory is automatically
    skipped by the runtime_state patterns in both manifests,
    so a repaired install still verifies clean.
  - **`--dry-run`** with `--repair` reports the plan (what
    would be restored) without writing anything; useful before
    pointing repair at a real install.
  - **Sandbox-tested**: corrupted DS1 `MIDITSR.EXE` in a copy
    of `.games/ds1`, ran `--repair`, got matched 56 -> 57,
    backup file present, ok=True on re-verify.
  - Requires `innoextract` on PATH (Fedora:
    `dnf install innoextract`). The verifier remains
    stdlib-only; the dependency is on the user's system, not
    Python.

- **`docs/dsun-exe-re.md` §4.5** deepening: a third time-boxed
  pass at the palette-cycle routine produced bounded findings
  but not a feature. Same pre-committed shape as the prior
  two passes; `region-render` stays at v0.5.0.
  - **§4.5.1 segment-selector hunt** against `0x288a4`. The
    zero-run boundary places the segment base near
    `0x28700`, making `0x288a4`'s segment-local offset
    `0x01a4` (`a4 01`). Pattern-search of the binary for
    `a4 01 <sel-lo> <sel-hi>` returns 17 total hits across
    at least 14 distinct candidate selectors; no selector
    dominates the distribution the way `0x3a98` did for the
    §3 dispatcher, so the trick doesn't disambiguate here.
  - **§4.5.2 DPMI / timer-ISR hunt**. Bytes `b8 05 02`
    (`mov ax, 0x205`, Set-Protected-Mode-Vector) **don't
    occur in DSUN.EXE**. The two `cd 31` (`int 31h`) hits
    are false positives (the bytes appear inside
    `mov ax, 0x31cd` immediates). Implication: the engine
    does not install timer ISRs via DPMI; the DOS/4GW
    extender's runtime must be doing it on the engine's
    behalf. Following the tick-handler chain requires
    understanding the DOS/4GW ABI; queued as a separate RE
    thread.
  - **§4.5.3 no additional palette-I/O sites**. The six
    sites catalogued in §4.2 / §4.3 are the complete
    inventory. The cycle routine MUST call one of them;
    it doesn't write to the DAC directly.
  - **§4.5.4 what's left to try**. Five concrete directions
    documented (better segment-base candidate, DOS/4GW
    runtime cross-reference, data-segment patterns to find
    the cycle table itself, dynamic analysis via
    opcode-fuzz, DS2 shape-match if a DSO function-table
    dump ever surfaces).
  - `region-render` stays at v0.5.0 per the pre-committed
    docs-only fallback.

- **`tools/opcode-fuzz/` v0.2.0** adds the `run` subcommand:
  the **run + observe** half of the Phase 5 discovery loop.
  v0.1.0 shipped the chunk-patchwork pipeline (extract / pack
  / roundtrip); v0.2.0 wires it into `repro v0.3.0`'s
  resumable `--play --session` mode so a patched chunk can be
  loaded into DOSBox and the resulting state diff captured.
  - **`opcode-fuzz run <work-dir>`**. Encodes `chunk.json`
    via `gpl-asm` (validator runs), replaces the chunk in
    the source GFF, synthesises a temporary repro fixture
    under `<tmpdir>/bugs/opcode-fuzz/` whose
    `[setup].copy_files` stages the patched `GPLDATA.GFF`
    plus the matching `ds[12]-smoke` `SOUND.CFG` into the
    C: overlay. Then invokes `repro.py opcode-fuzz --play
    --session opcode-fuzz-<work-dir-name> --bugs-dir <tmp>`.
  - **State diff**. Snapshots the session's
    `c-overlay/DARKRUN.GFF` before launch (factory if the
    session was fresh; the prior end-state if resumed) and
    after launch. Emits a JSON byte-level diff
    (`{status, pre_bytes, post_bytes, bytes_same,
    bytes_different, first_diff_offsets, session_dir,
    target_game, chunk, repro_rc}`) on the run's tail.
    For structural diff, the post snapshot persists in the
    session dir; users can shell to `save-inspect diff
    pre.gff post.gff` for SAVE-chunk granularity.
  - **Session continuity inherited from repro v0.3.0**. The
    same session dir is reused across `opcode-fuzz run`
    invocations, so iterative fuzzing on the same chunk
    accumulates state. `repro --list-sessions` finds these
    sessions alongside regular play sessions.
  - **Honest scope statement** in the README. The full
    discovery loop (write single-opcode test chunk, observe
    its side effect, iterate to fill `docs/gpl-opcodes.md`)
    needs two things v0.2.0 doesn't yet have: input
    automation to drive the engine to the state where the
    chunk fires without manual keystroke wrangling (`repro
    v0.3.x` ydotool integration, dep-approval pending), and
    identification of which chunks the engine invokes on
    boot (`DSUN.EXE` RE). v0.2.0 ships the run + observe
    scaffolding the discovery loop sits on; the smoke test
    is "swap a chunk with itself, run, observe minimal
    diff."
  - **Roadmap Phase 5 §opcode-fuzz**: harness-and-state-
    delta rows transition from `[ ]` to `[~]` (partial); the
    "discover one previously-unknown opcode" `[ ]` is the
    Phase 5 "done when" bar, still ahead of us.
  - **VERSION**: 0.1.0 -> 0.2.0.

- **`tools/repro/` v0.3.0** makes `--play` resumable. v0.2.1
  invented the play mode but every invocation created a fresh
  `/tmp/repro-XXXX/` scratch dir, so in-game saves vanished
  between runs. v0.3.0 adds session continuity via a stable
  scratch path under `$XDG_STATE_HOME`. Input automation +
  video capture remain v0.3.x / v0.4.0+ (need dep approvals).
  - **`--session <name>` + persistent overlays**. Each
    `--play --session foo` uses `$XDG_STATE_HOME/opends-repro/
    play-<game>-<session>/` (defaults to
    `~/.local/state/opends-repro/`). The `c-overlay/` inside
    that path holds the C: drive state from every previous
    run; factory-save staging skips when the overlay already
    has the file, so player saves are never overwritten.
    Default session name on `--play` is the bug id itself, so
    `repro.py ds1-smoke --play` keeps its own saves
    automatically.
  - **`--list-sessions`** enumerates every session under the
    state root with the last-played mtime of `c-overlay/
    DARKRUN.GFF` (tracks actual in-game activity rather than
    dir-creation time).
  - **`--reset-session <name>`** prompts for explicit `yes`
    then deletes the named session dir. Requires a `bug_id`
    positional so the target game is known.
  - **Resume / fresh marker** in the run header: the scratch
    line says `(fresh)` or `(resumed)` depending on whether
    the session dir was just created.
  - **Regression mode unchanged**. Test runs (`--play`
    omitted) still use `tempfile.mkdtemp` so they don't
    accumulate stale state.
  - **Out of scope (v0.3.x / v0.4.0+)**: input automation
    (ydotool); video capture (GNOME-Wayland-compatible
    recorder); differential capture.
  - **`roadmap.md` Phase 2 §save-state library**: session-
    continuity note added; row stays partial pending real
    bug-triggering save curation.
  - **VERSION**: 0.2.1 -> 0.3.0.

- **`tools/dialog-extract/` v0.5.0** closes the LSTR tail. The
  32 LSTR reads v0.4 couldn't pin to a single writer
  (caller-populated slots: the engine writes to LSTR slot N
  in one chunk, then reads it back in a different chunk
  reached via `gpl global sub`) now each carry a callgraph-
  narrowed `possible_writers` array. Zero reads in the corpus
  lack a statically-reachable writer.
  - **Global LSTR-writer index**. Pre-scan every chunk for
    `gpl_string_copy` (0x0A) writes into LSTR slots; index
    by destination slot. Each writer record captures
    `(chunk, kind, id, offset, source)` plus the value /
    `text_id` / `source_slot` per the original instruction's
    payload kind (`inline` / `gstring` / `lstring` /
    `computed`).
  - **Callgraph-narrowed filtering**. The reverse closure of
    each chunk's `cross_chunk_calls` (gpl-disasm v0.4.1+
    inter-chunk graph) gives the set of chunks that can
    statically reach a given read site. Writers in unreachable
    chunks are filtered out. Same-chunk writers always stay.
    When the callgraph leaves zero matches, fall back to the
    global writer set so the user always sees at least one
    candidate.
  - **Output shape**: every unresolved `text:lstring` record
    gains `possible_writers: [...]` and a
    `possible_writers_filter` label
    (`callgraph-reachable` / `global-fallback` / `global`).
  - **Corpus numbers**: DS1 = 255 LSTR reads, 230 exact-
    resolved (90.2%), 25 via possible_writers (avg 4.0
    candidates each, max 34). DS2 = 99 reads, 92 exact
    (92.9%), 7 via possible_writers (avg 6.7, max 21). Zero
    reads in either game lack a writer.
  - **New top-level field** `lstr_stats` and a stderr stats
    line at end of run so a corpus run shows the resolution
    breakdown at a glance.
  - **Out of scope (v0.6.0+)**: CFG-distance-ordered
    `possible_writers` lists, proper symbolic call-path
    tracing, resolution through `gpl_search` raw_tail
    rewrites.
  - **`roadmap.md` Phase 4 §dialog-extract**: LSTR tail row
    ticked.
  - **VERSION**: 0.4.0 -> 0.5.0.

- **`tools/gpl-asm/` v0.6.0** adds the preprocessor: two
  directives that make hand-authored GPL listings more
  ergonomic without changing the bytecode the encoder
  produces. The v0.5.0 validator pass + caret-style errors
  remain in place.
  - **`%define <name> <replacement>`**: token substitution
    applied to every subsequent non-directive line. Names
    are identifier-shaped only (letters / digits / underscore,
    leading letter or `_`) and cannot shadow reserved tokens:
    operator words (`and`, `or`), variable shorts (`GNUM`,
    `GBYTE`, `LSTR`, ...), keyword tokens (`RETVAL`,
    `INTRODUCE`, `ACCUM`, ...), or mnemonic words (`gpl`,
    `jump`, `endif`, `else`, `while`, ...). Substitution
    skips quoted string regions and the per-line
    `  ; trailer` comment portion.
  - **`%search-tail <hex-bytes>`**: ergonomic alternative to
    the `; raw_tail=HEX` trailer comment, with space-separated
    hex bytes. Attaches to the next instruction line; errors
    if a trailer comment is also present.
  - **Directive lines blank-replace**, not remove, so caret
    error line numbers still match the user's source. A
    `%define` on line 7 of an authored listing still surfaces
    a parse error on line 9 as `line 9`.
  - **New `ParseError` variants**: `BadDefineSyntax`,
    `BadDefineName`, `DuplicateDefine`, `BadSearchTailSyntax`,
    `DuplicateSearchTail`. All flow through
    `format_with_caret` and underline the offending
    directive line end-to-end.
  - **Corpus stays at 600 / 600 byte-identical**. The
    disassembler doesn't emit directives, so the round-trip
    path is unchanged.
  - **Out of scope (v0.7.0+)**: parameterised macros
    (`%define foo(arg1, arg2)`), `@include` directives, a
    separate `.const` keyword distinct from `%define`.
  - **`roadmap.md` Phase 5 §gpl-asm**: authoring-conveniences
    row ticked; v0.7.0 carries the parameterised-macro
    follow-on.
  - **VERSION**: 0.5.0 -> 0.6.0.

- **`tools/opcode-fuzz/` v0.1.0** lands the Phase 5 second
  tool's scaffold and chunk-patchwork pipeline. Same shape as
  `repro` v0.1.0: ship the foundation, defer the discovery
  loop. The eventual goal (run swapped GPL chunks under DOSBox
  and watch what each opcode does to engine state) needs the
  GPL VM state addresses in DSUN.EXE and a deterministic
  DOSBox-launch path through repro, neither of which exist
  yet; v0.1.0 ships the chunk-handling layer those depend on.
  - **`opcode-fuzz extract <gff> <kind> <id> -o <work-dir>`**.
    Stages a single GPL / MAS chunk into a work-dir as
    `original.bin` (raw bytes, reference for diff),
    `chunk.json` (gpl-disasm JSON, editable), `chunk.asm`
    (gpl-disasm text listing, also editable), and `meta.json`
    (source GFF + chunk coordinate so `pack` doesn't need
    them re-specified).
  - **`opcode-fuzz pack <work-dir> -o <new.gff>`**. Reads
    `meta.json`, encodes the (possibly edited) `chunk.json`
    via `gpl-asm` (which runs validate by default and aborts
    on any branch-bound / Immediate14-overflow / RetVal-depth
    error), replaces the chunk in the source GFF via
    `gff-cat replace`, writes the result to `--output`.
  - **`opcode-fuzz roundtrip <gff>`**. Corpus self-test:
    `extract -> disasm -> reasm -> replace -> compare GFF`
    for every GPL / MAS chunk. DS1 (250 / 250) and DS2
    (350 / 350) round-trip byte-identical; the combined
    600 / 600 matches `gpl-asm`'s per-chunk corpus test
    exactly. The new value over gpl-asm's test is the full
    GFF-level path: any `gff-cat replace` regression or
    chunk-relocation bug surfaces here, not just per-chunk
    encode mismatches.
  - **Out of scope (v0.2.0+)**. The `run` subcommand that
    swaps a chunk, launches DOSBox via repro, and diffs
    pre/post `DARKRUN.GFF`. Per-opcode test-chunk generation
    (the prologue / opcode-under-test / epilogue authoring
    pattern). Identifying which chunks run on game boot
    (depends on `dialog-extract`'s CFG and a DSUN.EXE main-
    loop trace).
  - **Open dependencies**. GPL VM state addresses in
    DSUN.EXE; the 0x230e5 GMAP / entity-render finding in
    dsun-exe-re.md §4.4 hints at where some engine state
    lives, more work needed. Deterministic DOSBox-launch
    through repro (queued for repro v0.3.0 alongside input
    automation).
  - **`roadmap.md` Phase 5 §opcode-fuzz**: chunk-pipeline
    row ticked, tagged-v0.1.0 row ticked; the harness +
    state-delta rows remain open and now reference the
    concrete blockers (state addresses + deterministic
    launch).
  - **VERSION**: 0.1.0 (new tool).

- **`tools/save-inspect/` v0.6.0** validates the DS2 item
  sub-block schema and finishes the DS2 save-state decode arc.
  Plus a bonus structural discovery: `SAVE0N.SAV` files are
  byte-identical snapshots of `DARKRUN.GFF`.
  - **DS2 item validation**. libgff's `ds1_item_t` (23 bytes
    on the wire, "Not confirmed at all" per the upstream
    comment) **is** the DS2 wire format byte-for-byte. v0.6.0
    confirms against 151 items across two CHARSAVE corpora
    (played: a `ds2-smoke --play` capture; factory: the
    pristine GOG 1.10 ship). Zero truncations on DS2; every
    item reads through the trailing `priority` + `data0` pair.
  - **`_format` tags**. `_decode_item` now emits
    `_format: ds1_item` for 21-byte records and
    `_format: ds2_item` for 23-byte records. Consistent with
    how v0.4 (combat) and v0.5 (character) surface the
    per-game shape; downstream tooling can feature-detect on
    the tag.
  - **`SAVE0N.SAV` == `DARKRUN.GFF` discovery**. While
    capturing the played-save fixtures, the save-slot
    mechanism became visible: the engine writes a `SAVE0N.SAV`
    file that is byte-for-byte the current `DARKRUN.GFF`
    (sha256 match confirmed on both games). Both are standard
    GFF containers; save-inspect reads `SAVE0N.SAV` directly
    with no changes. Inside is ~60 `SAVE` chunks (per-region
    world state), an `STXT` save-name chunk, an `ETME`
    event-table-metadata chunk, plus DS1's `ETAB` entity
    table. The `SAVE` chunk decode is the next un-cracked
    surface; queued without a version target.
  - **`roadmap.md` Phase 4 §save-inspect**: DS2 item row
    ticked; `SAVE` chunk decode is the new tail.
  - **Memory** `dsun_install_paths` updated with the
    save-slot semantics.
  - **VERSION**: 0.5.0 -> 0.6.0.

- **`tools/repro/` v0.2.1** adds `--play` mode: the same setup
  recipe the regression test uses (overlay-mounted C:, factory
  saves staged at C:\\ root, sound_ds-generated `SOUND.CFG`,
  the harness's `configs/ds[12].conf`), but with no wall-clock
  budget and no pass/fail evaluation. Lets the user actually
  *play* the game with the harness's setup instead of just
  proving the engine survives 30 seconds.
  - **Why it exists**. A bare `dosbox DSUN.EXE` against the
    GOG install hits two engine-side gotchas: `DARKSAVE.GFF`
    is not at C:\\ root (so the engine fails the
    `DARKSAVE -> DARKRUN` copy and exits), and the factory
    `SOUND.CFG` fails MEL DSP detect (same bug family as
    `docs/known-bugs.md` §2.6, exits inside a second). The
    harness already had to solve both for the regression test
    to function; `--play` exposes that workaround as a
    user-facing mode.
  - **Usage**. `repro.py ds1-smoke --play` /
    `repro.py ds2-smoke --play`. DOSBox opens, user plays,
    quits the game in-engine; the harness keeps `--exit` in
    the command line so DOSBox closes cleanly on its own.
  - **In-game saves land in `<scratch>/c-overlay/`**. The
    harness always retains the scratch dir in `--play` mode
    (the user almost certainly wants to keep their saves) and
    prints the path at the end of the run so they can copy
    CHARSAVE.GFF / DARKSAVE.GFF / BACKSAVE.GFF / DARKRUN.GFF
    out to a stable location.
  - **Resume across sessions** is **not** automatic in v0.2.1.
    Each `--play` invocation creates a fresh scratch dir under
    `/tmp`; to continue an existing playthrough, copy the
    saved GFFs into the bug fixture's directory and add them
    to `[setup].copy_files`. A `--scratch-dir` for stable
    session paths is queued for v0.3.0.
  - **VERSION**: 0.2.0 -> 0.2.1.

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
