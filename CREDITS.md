# CREDITS

OpenDS stands on the shoulders of three public reverse-engineering
projects. This file maps each OpenDS feature to the specific
upstream file or function that informed it.

[`docs/upstream-projects.md`](docs/upstream-projects.md) carries
the broader project context. [`README.md`](README.md) §Credits
keeps the top-level acknowledgements short. This file is the
canonical, per-feature attribution manifest. We follow the
convention of also citing each port in the source file's
comments next to the relevant code.

## GFF container format

| Feature | Upstream | License |
|---------|----------|---------|
| File header (7-field, 28-byte struct: identity / version / data_location / toc_location / toc_length / file_flags / data0) | `dsoageofheroes/libgff` `include/gff/common.h` `gff_file_header_s` | MIT |
| TOC layout (toc_header → num_types → per-type chunk_list_header → indexed entries or segmented metadata) | `dsoageofheroes/libgff` `include/gff/common.h` + `src/gpl/gpl.c` `gff_read_headers` | MIT |
| Segmented-flag mask (`0x80000000`) on `chunk_count` (not `chunk_type`) | `dsoageofheroes/libgff` `include/gff/common.h` `GFFSEGFLAGMASK` / `GFFMAXCHUNKMASK` + `src/gpl/gpl.c` line 293 | MIT |
| Segmented chunk resolution (GFFI primary table at TOC level, secondary table at GFFI chunk's data offset, resource ids reconstructed from segment runs) | `dsoageofheroes/libgff` `src/gpl/gpl.c` `gff_find_chunk_header` + `JohnGlassmyer/dsun_music` `common/src/main/java/net/johnglassmyer/dsun/common/gff/GffFile.java` `createTables` + `SecondaryGffiTable.java` | MIT (both) |
| Writer policy (in-place if `new_size <= old_size`, append at end-of-file otherwise; update `(location, length)` in the TOC for indexed chunks or in the secondary table for segmented chunks) | `JohnGlassmyer/dsun_music` `common/src/main/java/net/johnglassmyer/dsun/common/gff/GffFile.java` `replaceResource` | MIT |
| Chunk-type FOURCC catalogue (~70 entries: GFFI, FORM, GFRE, GTOC, PAL, BMP, BMAP, PORT, WALL, ICON, TILE, RMAP, GMAP, ETAB, RDFF, etc.) | `dsoageofheroes/libgff` `include/gff/gfftypes.h` | MIT |

**OpenDS code that consumes the above:**
- `tools/gff-edit/src/lib.rs` — `FileHeader`, `parse_toc`, `resolve_segmented_type`, `Gff::replace_chunk`
- `tools/gff-edit/src/bin/gff-cat.rs` — `KIND_CATALOGUE`
- `docs/file-formats.md` §1 and §1's "Segmented chunk resolution"

## GPL bytecode

| Feature | Upstream | License |
|---------|----------|---------|
| Opcode catalogue (129 entries 0x00–0x80 with mnemonic names) | `dsoageofheroes/libgff` `src/gpl/parse.c` `gpl_commands` table (lines 1554–1684) | MIT |
| GPL_* constants (operator offsets, parens, variable types, IMMED_* markers, `EXTENDED_VAR`, `OPERATOR_OFFSET`, `OPERATOR_LAST`) | `dsoageofheroes/libgff` `include/gpl/var.h` | MIT |
| "Safe in RETVAL context" opcode annotations | `dsoageofheroes/libgff` `src/gpl/parse.c` `gpl_retval` switch (lines 1791–1826) | MIT |
| Variable-length expression decoder (`gpl_read_number`, lines 369-635): 14-bit immediate, IMMED_BYTE / BIGNUM / NAME / STRING, variable references with `EXTENDED_VAR`, operator loop, parens. Deferred-but-detected: `GPL_RETVAL`, `GPL_COMPLEX_*`, `0xb3`. | `dsoageofheroes/libgff` `src/gpl/parse.c` `gpl_read_number` | MIT |
| Variable-reference helper (`gpl_read_simple_num_var`, lines 134-233): 1 or 2 byte vid, per-type dispatch (GFLAG/LFLAG/GNUM/LNUM/GBIGNUM/LBIGNUM/GSTRING/LSTRING/GNAME). | `dsoageofheroes/libgff` `src/gpl/parse.c` `gpl_read_simple_num_var` | MIT |
| Per-opcode parameter-count table (`PARAM_COUNTS`): 129 entries 0x00..0x80, derived from each handler body's `gpl_get_parameters(gpl, N)` / `gpl_read_number(gpl)` calls. Wrappers (`gpl_template`, `gpl_type_op_equal`) expanded inline. | `dsoageofheroes/libgff` `src/gpl/parse.c` per-handler bodies (lines 660-1552) | MIT |
| `0x5F music` parameter count (1 expression): libgff treats as `gpl_unknown`; soloscuro-archive reads 1 `read_number`. | `dsoageofheroes/soloscuro-archive` `src/gpl/gpl-lua.c` `gpl_lua_music` | MIT |
| Structural handler ports (gpl-disasm v0.2.0): `gpl_load_variable` (0x16, simple-variable path), `gpl_menu` (0x48, three-expression entries terminated by 0x4A), `gpl_search` (0x33, do-while loop with SEARCH_QUAL 0x53 marker), `gpl_log` (0x2C, packed string only). | `dsoageofheroes/libgff` `src/gpl/parse.c` lines 1339, 1052, 901, 812 | MIT |
| `gpl_access_complex` (gpl-disasm v0.2.1): word obj_name + byte depth + depth bytes of element data. Decodes record-field access for the `GPL_COMPLEX_*` (`0xB0..=0xBF`) range, the `0xb3` special case, `gpl_setrecord` (0x40), and the complex-write path of `gpl_load_variable` (0x16). `obj_name >= 0x8000` keyword set (POV, ACTIVE, PASSIVE, OTHER, OTHER1, THING) preserved. | `dsoageofheroes/libgff` `src/gpl/parse.c` `gpl_access_complex` lines 235-288 | MIT |
| `gpl_retval` safe-subset dispatch (gpl-disasm v0.2.1): the 21 opcodes libgff permits inside a `GPL_RETVAL` nested call. Recursive port reuses `read_instruction_params_with_depth` and the same `PARAM_COUNTS` table; bounded by `MAX_RETVAL_DEPTH = 4`. | `dsoageofheroes/libgff` `src/gpl/parse.c` `gpl_retval` lines 1791-1826 | MIT |
| 7-bit packed inline-string decoder (sub-type markers `0x01` INTRODUCE / `0x02` UNCOMPRESSED / `0x05` COMPRESSED; 7-bit packed stream terminated by `0x03`; non-printable bytes replaced with space) | `dsoageofheroes/soloscuro-archive` `src/gpl/gpl-string.c` `sol_gpl_read_text` + `read_compressed` | MIT |

**OpenDS code that consumes the above:**
- `tools/gpl-disasm/src/lib.rs` — `OPCODES`
- `docs/gpl-opcodes.md`
- `tools/dialog-extract/dialog-extract.py` — `decode_compressed_string`

## Character data (CHARSAVE.GFF)

| Feature | Upstream | License |
|---------|----------|---------|
| `gff_rdff_header_t` (10-byte header: load_action, blocknum, type, index, from, len) | `dsoageofheroes/libgff` `include/gff/rdff.h` | MIT |
| `gff_char_entry_t` (RDFF header + opaque `data[]`) | `dsoageofheroes/libgff` `include/gff/char.h` | MIT |
| `gff_psin_t` (`uint8_t types[7]` — psionic discipline byte codes) | `dsoageofheroes/libgff` `include/gff/psionic.h` | MIT |
| `gff_psionic_list_t` / `gff_psst_t` (`uint8_t psionics[34]` — psionic mastery array) | `dsoageofheroes/libgff` `include/gff/psionic.h` | MIT |
| `ds_character_t` (72-byte computed; DS1 on-disk is 71 bytes per actual save files): current_xp / high_xp / base_hp / high_hp / base_psp / id / legal_class / race / gender / alignment / stats (str/dex/con/intel/wis/cha) / real_class[3] / level[3] / base_ac / base_move / magic_resistance / num_blows / num_attacks[3] / num_dice[3] / num_sides[3] / num_bonuses[3] / saving_throw[5] / allegiance / size / spell_group / high_level[3] / sound_fx / attack_sound / psi_group / palette | `dsoageofheroes/libgff` `include/gff/object.h` `ds_character_s` | MIT |
| `ds1_combat_t` (58 bytes): hp / psp / char_index / id / ready_item_index / weapon_index / pack_index / data_block[8] / special_attack / special_defense / icon / ac / move / status / allegiance / data / thac0 / priority / flags / stats / name[18] | `dsoageofheroes/libgff` `include/gff/object.h` `_ds_combat_t` | MIT |
| `ds1_item_t` (~23 bytes computed; DS1 on-disk is 21): id / quantity / next / value / pack_index / item_index / icon / charges / special / slot / name_idx / bonus / priority / data0 | `dsoageofheroes/libgff` `include/gff/item.h` `ds1_item_s` | MIT (annotated "Not confirmed at all" by upstream) |
| Positional sub-block reader for CHAR bodies (combat → character → item × N, terminated by RDFF_END): the engine reads sub-blocks by position, not by `rdff.type`. The first sub-block's `blocknum` gives the total count. | `dsoageofheroes/libsoloscuro` `src/entity.c` `sol_entity_load_from_gff` | MIT |
| `gff_race_e` (MONSTER / HUMAN / DWARF / ELF / HALFELF / HALFGIANT / HALFLING / MUL / THRIKREEN) | `dsoageofheroes/libgff` `include/gff/object.h` `enum gff_race_e` | MIT |
| Item slot enum (ARM / AMMO / MISSILE / HAND0 / FINGER0 / WAIST / LEGS / HEAD / NECK / CHEST / HAND1 / FINGER1 / CLOAK / FOOT) | `dsoageofheroes/libgff` `include/gff/item.h` slot enum | MIT |
| DS2 RDFF schemas (combat 49 bytes, character 66 bytes) — defer; v0.2.0 surfaces character names heuristically and emits raw hex for DS2 sub-blocks rather than producing wrong-looking fields. | `dsoageofheroes/libsoloscuro` (TBD) | TBD |

**OpenDS code that consumes the above:**
- `tools/save-inspect/save-inspect.py` — `decode_rdff_header`, PSIN / PSST branches in `decode_chunk`

## Influences (read but not yet ported)

- **`dsoageofheroes/libsoloscuro`** — DS-specific rules engine
  (class.c, race.c, stats.c, dude.c, item.h, combat.h, powers.h,
  psionic.h). Will inform save-inspect v0.2.0 (CHAR record body
  decoding) and any future rules-aware tool.
- **`greg-kennedy/DarkSunOnline`** — DSO server reimplementation
  + wiki. The DSO v1.0 client shipped with Watcom debug symbols
  including function and variable names; Greg's repo extracts
  them to `tools/symbols.txt` (3,530 functions + 2,247 globals).
  WotR shares this codebase, so those names are the single best
  public source for naming functions inside `DSUN.EXE`.
  AGPL-3.0; the names are facts we cite individually in
  [`docs/dso-symbols.md`](docs/dso-symbols.md), not source code
  we port. Future reference for `gpl-disasm` symbol curation
  (v0.4.0+) and any binary patching work.
- **Crimson Sands postmortem** (Gamasutra / Game Developer
  Magazine) — the only first-person account that names "GPL"
  as the in-engine scripting language. Cited in
  [`docs/gpl-bytecode.md`](docs/gpl-bytecode.md) §2.
- **Beamdog forums Shattered Lands → Infinity Engine port** —
  community attempt to recreate DS1 inside BG2:EE. Useful as a
  reference for asset extraction patterns.
- **FearLess Cheat Engine tables** (DS1 + DS2) and the
  **DREAD +10 Trainer** — memory-layout references for any
  future binary patching work.

## Reference checkouts

For fast iteration during research, the following are cloned
locally and gitignored:

- `.dsun_music/` — shallow clone of
  [`JohnGlassmyer/dsun_music`](https://github.com/JohnGlassmyer/dsun_music)
  (MIT).
- `.dsoageofheroes/` — shallow clones of all 7 repos at
  [`github.com/dsoageofheroes`](https://github.com/dsoageofheroes):
  `libgff`, `libsoloscuro`, `soloscuro`, `soloscuro-archive`,
  `soloscuro-oldgo`, `soloscuro-orx`, `the-dark-lens` (mostly
  MIT).
- `.dso-online/` — shallow clone of
  [`greg-kennedy/DarkSunOnline`](https://github.com/greg-kennedy/DarkSunOnline)
  (AGPL-3.0). Research mirror; we do not port source code from
  it. We cite individual symbol names from its
  `tools/symbols.txt` in [`docs/dso-symbols.md`](docs/dso-symbols.md).

These are not redistributed by OpenDS; they are research
mirrors for the maintainer's machine.

## Licensing

OpenDS itself is MIT-licensed. The upstream ports listed in
this file are all from MIT-licensed sources (`libgff`,
`soloscuro-archive`, `dsun_music`). Re-implementation in
idiomatic Rust / Python with attribution is permitted by the
MIT terms; we preserve the copyright notice and license
intent by:

1. Naming the upstream file and function in a comment next to
   each ported piece of code.
2. Maintaining this CREDITS.md as the canonical per-feature
   manifest.
3. Linking each upstream project in
   [`docs/upstream-projects.md`](docs/upstream-projects.md).

If you've worked on Dark Sun reverse-engineering and your work
is reflected in OpenDS without a credit here, open an issue.
We'd rather over-credit than under-credit.
