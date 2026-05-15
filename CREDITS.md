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
| Per-game RDFF schemas (DS1 vs DS2 character record byte layouts) — planned for save-inspect v0.2.0 | `dsoageofheroes/libsoloscuro` `src/dude.c` + `src/entity.c` + `src/stats.c` + `inc/soloscuro/*.h` | no LICENSE file (single-author dsoageofheroes org; treated as honor-system MIT pending confirmation) |

**OpenDS code that consumes the above:**
- `tools/save-inspect/save-inspect.py` — `decode_rdff_header`, PSIN / PSST branches in `decode_chunk`

## Influences (read but not yet ported)

- **`dsoageofheroes/libsoloscuro`** — DS-specific rules engine
  (class.c, race.c, stats.c, dude.c, item.h, combat.h, powers.h,
  psionic.h). Will inform save-inspect v0.2.0 (CHAR record body
  decoding) and any future rules-aware tool.
- **`greg-kennedy/DarkSunOnline`** — DSO server reimplementation
  + wiki. Reports that the DSO v1.0 client shipped with debug
  symbols including function and variable names. WotR shares
  this codebase, so those symbols are the single best public
  source for naming functions inside `DSUN.EXE`. Future
  reference for `gpl-disasm` symbol curation (v0.4.0+) and any
  binary patching work.
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
  [`JohnGlassmyer/dsun_music`](https://github.com/JohnGlassmyer/dsun_music).
- `.dsoageofheroes/` — shallow clones of all 7 repos at
  [`github.com/dsoageofheroes`](https://github.com/dsoageofheroes):
  `libgff`, `libsoloscuro`, `soloscuro`, `soloscuro-archive`,
  `soloscuro-oldgo`, `soloscuro-orx`, `the-dark-lens`.

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
