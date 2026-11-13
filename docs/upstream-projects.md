# Upstream Projects

The reverse-engineering work we are building on. Coordinating with
these projects is preferable to duplicating their work.

## 1. dsoageofheroes (paulofthewest)

The most active and serious public RE effort. The umbrella organization
is on GitHub as [dsoageofheroes](https://github.com/dsoageofheroes).
Lead: **Paul West**. Discord: https://discord.gg/W942xHN72S.

### `libgff`

- URL: https://github.com/dsoageofheroes/libgff
- Language: C, with optional Zig
- License: MIT
- Status: actively maintained as of May 2025

The reference GFF reader. Full chunk-type catalog in
`include/gff/gfftypes.h`. Provides:

- `gffmod`: library with image, palette, animation, map, window, GPL,
  character, region, item, text, audio readers
- `gfftool`: CLI for listing and extracting chunks
- Bundled `xmi2mid` for XMI → standard MIDI conversion
- Build via CMake, Zig, Make, or Premake5

**darkfix strategy**: use `libgff`'s `gfftool` as a read-side reference
and validation tool. We don't reimplement the reader for v1; we either
shell out to `gfftool` or read just enough of the format to extract
`GPL ` chunks for our disassembler.

### `soloscuro-archive`

- URL: https://github.com/dsoageofheroes/soloscuro-archive
- Language: C, Lua scripting layer
- License: MIT
- Status: stalled 2023, ~567 commits

The most mature engine reimplementation attempt. Stack:

- SDL2, SDL2_mixer, SDL2_image, SDL2_ttf, SDL2_net
- libsndfile, libadlmidi (OPL synthesis)
- Lua 5.3 (scripting bridge)
- GitHub Actions CI for Linux + MSYS2/Windows (Windows build is
  currently broken)

DS1 ("Shattered Lands") is the primary target; DS2 and DSO are stated
goals but unimplemented. Runs as a GFF browser plus a Lua script test
runner: no playable end-to-end yet.

Includes `code-generation/powers/` directory pulling DS1, DS2, and DSO
power tables: useful for validating our `opends-rules` data.

**darkfix strategy**: read the source for two things ;
(1) the partial GPL parser in `src/gpl/`, which is our starting point
for `gpl-disasm`, and (2) the chunk-reading logic, useful for
validating what we extract.

### `soloscuro` (the Zig rewrite)

- URL: https://github.com/dsoageofheroes/soloscuro
- Language: Zig (66%) + C (33%)
- License: MIT
- Status: very early; ~7 commits, README is "TBW"

The presumed successor to `soloscuro-archive`. Worth watching but not
relying on.

### `libsoloscuro`

- URL: https://github.com/dsoageofheroes/libsoloscuro
- Language: C + Zig + Lua
- License: none shipped (corrected 2026-09-05; the clone carries no
  LICENSE file: treat as all-rights-reserved until upstream adds
  one; code must not be copied, only cited)
- Status: early

Internal name "nucleo": "core rules to work with libgff and soloscuro."
A game-rules layer (AD&D 2e Dark Sun) intended to sit above libgff.

### `soloscuro-orx`

- URL: https://github.com/dsoageofheroes/soloscuro-orx
- Language: C
- Status: experimental

Alternate engine attempt using the Orx 2D engine. Looks dormant.

### `soloscuro-oldgo`

- URL: https://github.com/dsoageofheroes/soloscuro-oldgo
- Language: Go + C
- Status: archived

An older Go-based DSO server/client experiment.

### `the-dark-lens`

- URL: https://github.com/dsoageofheroes/the-dark-lens
- Status: documentation-only

Tiny but useful: `DSO Players e-mails.txt`, `PacketFormatDSO.txt`,
`xmi-tracks.txt`. The XMI tracks file names DSO tracks (Slave Pens,
Arena, Sewers, ...), not DS1 tracks: the two games share the XMI
format but not the soundtrack. Still useful as a format reference.
Note: `DSO Players e-mails.txt` contains personal information; never
quote or absorb its contents.

## 2. dsun_music (John Glassmyer)

- URL: https://github.com/JohnGlassmyer/dsun_music
- Language: Java (Maven)
- License: MIT
- Status: stable, niche

An independent, earlier reverse-engineering effort. Four CLI tools:

- `gff-tool`: extract and **replace** GFF contents (write support
  exists here, unlike libgff)
- `xmi-tool`: describe and modify PSEQ/LSEQ/GSEQ XMI sequences
- `image-tool`: render bitmap chunks to TIFF
- `region-tool`: render terrain to TIFF

**Historical role**: `gff-tool`'s **write support** was the
original keystone of the data-patch path, back when it was the
only public GFF writer. Superseded by our own `gff-edit`
(spec §3.1): its in-place-or-append `replaceResource` policy is
what `gff-edit` ports (credited in [`../CREDITS.md`](../CREDITS.md)),
and every GPL fix now flows through `gff-edit` + `gpl-asm`, no
JVM required. `gff-tool` remains the reference implementation of
the writer policy.

## 3. DarkSunOnline (Greg Kennedy)

- URL: https://github.com/greg-kennedy/DarkSunOnline
- Language: Python + C + Perl
- License: AGPL-3.0
- Status: actively maintained as of February 2026

DSO-specific (Crimson Sands). Ships:

- A Python 3 server (`DSOServer/server.py`, listens TCP/14902, SQLite
  credentials)
- A Win16 launcher utility for connecting the original 1.0 client
- Wiki with reverse-engineering notes

**Crucial detail**: Greg's notes report that **the DSO v1.0 client
shipped with debug symbols including function and variable names.**
DSO inherited the WotR codebase, so those symbols are the single
best public source of named functions for the Dark Sun engine
internals at large. We should reference them when stuck on opcode
identification or function purpose.

The DSO project also documents prior revival attempts: Dark Sun World
(2004–2008), and a 2010s emulator shut down by Wizards of the Coast.

**darkfix strategy**: out of scope as a project to integrate
with (multiplayer rather than single-player), but the v1.0 debug
symbols are a research goldmine for naming functions in WotR's
`DSUN.EXE` when binary patching. Greg's repo extracts the
symbol table to `tools/symbols.txt`: 3,530 named functions and
2,247 named globals/labels. Locally checked out at
`.dso-online/` (research mirror; AGPL-3.0, never redistributed).
We curate hand-verified DSO-to-DS2 mappings in
[`dso-symbols.md`](dso-symbols.md); the symbol file itself is
the load-bearing reference for `gpl-disasm v0.4.0+` symbol
import and any future binary patching. Coordinate with Greg
before exploring publication of derived work; he has done the
homework on what's safe to publish.

## 4. yuan-ti (Calvin Rodo)

- URL: https://github.com/CalvinRodo/yuan-ti
- Language: C# (Godot 4.7 / .NET 10 engine) + Python (toolkit and Flask viewer)
- License: MIT (dual copyright: yuan-ti contributors 2026 + John
  Glassmyer 2018, reflecting the toolkit's descent from `dsun_music`)
- Status: actively developed as of November 2026 (PR #162 merged
  2026-11-07; CI + release builds for Linux/Windows/macOS)
- Came to us via opends issue #13 (2026-11-13). Workspace clone at
  `~/.gitrepos/yuan-ti/` (read-only reference; catalog row in
  `~/.gitrepos/CLAUDE.md`).

A DS1 engine rewrite plus the toolkit it grew out of, with DS2
partial and Al-Qadim partial (the toolkit's stated support). The
engine runs the full DS1 loop: chargen, every region, GPL scripts,
conversations, turn-based combat with psionics and the original
monster AI, items, saves, and a mod system replacing loose-file
resources. The toolkit side is a GFF parser, image decoder, GPL
disassembler, structured record parsers, and a web viewer; the RE
notes in `.github/instructions/` include a 2,548-line
`dsun-exe-reference.md` (derived with Ghidra 12.1.4 via REA, the
same tooling lane as ours) with the GPL interpreter's segment map,
expression grammar, and a combat/AI chapter.

**Where the work meets ours:**

- `engine/src/DarkSun.Game/Scripting/GplRepairs.cs` ports our
  darkfix-ds1 fixes byte-for-byte (verified against GOG 1.10 on
  2026-11-13: 23/23 fingerprints clean), implements three of our
  unshipped triage candidates, and adds 17 script-bug discoveries
  of Calvin's own. The full classification and adoption gate:
  [`detour-repairs.md`](detour-repairs.md); the catalog rows:
  [`known-bugs.md`](known-bugs.md) §3.6.
- The detour mechanism (length-changing script repairs without
  moving any address) is adopted as the design for our own applier
  work; credited in [`../CREDITS.md`](../CREDITS.md).
- Exchange briefs prepared 2026-11-13 (DS2 decode, the DS1
  region-change question, symbol exchange, runtime QA):
  [`exchange-yuan-ti-2026-11-13.md`](exchange-yuan-ti-2026-11-13.md).

Their engine README credits OpenDS for the shipped-script bug
catalog that its repairs option implements; the reuse pattern we
hoped for when darkfix published.

## 5. DarkSunTools (TimQuester)

<!-- DarkSunTools facts: this section, the CREDITS.md facts
section, and the file-formats.md FONT section land in one marked
commit so a single `git revert` removes every DarkSunTools-derived
statement if licensing does not pan out (decision 2026-11-13). -->

- URL: https://github.com/TimQuester/DarkSunTools
- Language: C# / .NET (WPF resource editor + codec class library)
- License: **none shipped** (default copyright; asked for an OSI
  license in opends issue #14 on 2026-11-13). Treat as
  all-rights-reserved until one lands: facts-only reference, no
  code ported, no code embedded.
- Status: single-commit snapshot cloned 2026-11-13 (latest commit
  2026-11-05: glyph editing + dialog-resource preservation)
- Came to us via opends issue #14. Workspace clone at
  `~/.gitrepos/DarkSunTools/`.

A Dark Sun resource-editing toolkit whose center of gravity is a
Russian fan-translation workflow: FONT glyph replacement (a
round-trip-tested font codec), fixed-length GPL string editing
(same character count => same byte count, no padding after the
0x03 terminator), and a transliteration layer mapping Cyrillic
back onto the Latin glyph codes the 7-bit font actually stores.
The codec library also carries a GFF reader, a GPL chunk parser,
and an opcode parameter-shape table whose doc comment names our
`gpl-disasm` v0.2.0 `PARAM_COUNTS` as its source (frozen at that
release; ours has moved on).

**What we take from it today** (facts, credited):
[`file-formats.md`](file-formats.md) §FONT records the FONT chunk
layout the codec documents, verified against our corpus the same
day; [`../CREDITS.md`](../CREDITS.md) carries the facts-only credit
row. **darkfix strategy**: none until a license appears; the
standing offer is exchange, not adoption (their string codec
against our `gpl-disasm --json`, our speakers/translation catalogs
against their editor UI).

## 6. Other tools

| Project / Tool                  | Purpose                                                 |
|---------------------------------|---------------------------------------------------------|
| **FearLess Cheat Engine tables**| Memory editing tables for DS1 and DS2                   |
| **DREAD +10 Trainer**           | Classic DOS-era trainer                                 |

URLs:

- DS1 CE table: https://fearlessrevolution.com/viewtopic.php?t=23768
- DS2 CE table: https://fearlessrevolution.com/viewtopic.php?t=23944
- DREAD trainer: https://archive.org/details/D-SUNTRNsoftware

These are reverse-engineering aides, not assets. Useful for
identifying memory layouts and verifying our rules-engine math
against the original binary.

## 7. Inactive / dormant

- **Beamdog forums Shattered Lands → Infinity Engine port** ;
  https://forums.beamdog.com/discussion/72931: modders
  recreating DS1 inside BG2:EE. Not a reimplementation; a port.
  Useful as an asset-conversion reference if we want a sanity-check
  on how someone else extracted regions.

## 8. ScummVM

**No support, no pending engine.** Dark Sun has not been adopted by
ScummVM. The project broadened scope to RPGs (Xeen, EOB I/II are in)
but no Dark Sun engine has been merged or proposed. This is the
project's gap to fill.

## 9. Coordination strategy

Before duplicating any non-trivial RE work:

1. Check libgff's chunk catalog and source.
2. Cross-check `dsun_music`'s implementation if a chunk seems
   ambiguous.
3. Ask in the dsoageofheroes Discord.
4. For DSO-related questions, ask Greg Kennedy.

The point is that this is a small enough community that we should
ship code, not duplicate effort.
