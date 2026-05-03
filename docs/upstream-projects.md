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

- `gffmod` — library with image, palette, animation, map, window, GPL,
  character, region, item, text, audio readers
- `gfftool` — CLI for listing and extracting chunks
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
runner — no playable end-to-end yet.

Includes `code-generation/powers/` directory pulling DS1, DS2, and DSO
power tables — useful for validating our `opends-rules` data.

**darkfix strategy**: read the source for two things —
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
- License: MIT
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
`xmi-tracks.txt`. The XMI tracks file is a useful cross-reference for
naming the music in DS1.

## 2. dsun_music (John Glassmyer)

- URL: https://github.com/JohnGlassmyer/dsun_music
- Language: Java (Maven)
- License: MIT
- Status: stable, niche

An independent, earlier reverse-engineering effort. Four CLI tools:

- `gff-tool` — extract and **replace** GFF contents (write support
  exists here, unlike libgff)
- `xmi-tool` — describe and modify PSEQ/LSEQ/GSEQ XMI sequences
- `image-tool` — render bitmap chunks to TIFF
- `region-tool` — render terrain to TIFF

**darkfix strategy**: `gff-tool`'s **write support** is the keystone of
the data-patch path. Every GPL fix flows through it: extract the
chunk, edit, replace. We may eventually fork or rewrite it in Python
to drop the JVM dependency, but for v1 it's our primary editor.

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

**darkfix strategy**: out of scope (multiplayer rather than
single-player), but the v1.0 debug symbols are a research goldmine
for naming functions in WotR's `DSUN.EXE` when binary patching.
Coordinate with Greg before exploring; he has done the homework on
what's safe to publish.

## 4. Other tools

| Project / Tool                  | Purpose                                                 |
|---------------------------------|---------------------------------------------------------|
| **FearLess Cheat Engine tables**| Memory editing tables for DS1 and DS2                   |
| **DREAD +10 Trainer**           | Classic DOS-era trainer                                 |

URLs:

- DS1 CE table — https://fearlessrevolution.com/viewtopic.php?t=23768
- DS2 CE table — https://fearlessrevolution.com/viewtopic.php?t=23944
- DREAD trainer — https://archive.org/details/D-SUNTRNsoftware

These are reverse-engineering aides, not assets. Useful for
identifying memory layouts and verifying our rules-engine math
against the original binary.

## 5. Inactive / dormant

- **Beamdog forums Shattered Lands → Infinity Engine port** —
  https://forums.beamdog.com/discussion/72931 — modders
  recreating DS1 inside BG2:EE. Not a reimplementation; a port.
  Useful as an asset-conversion reference if we want a sanity-check
  on how someone else extracted regions.

## 6. ScummVM

**No support, no pending engine.** Dark Sun has not been adopted by
ScummVM. The project broadened scope to RPGs (Xeen, EOB I/II are in)
but no Dark Sun engine has been merged or proposed. This is the
project's gap to fill.

## 7. Coordination strategy

Before duplicating any non-trivial RE work:

1. Check libgff's chunk catalog and source.
2. Cross-check `dsun_music`'s implementation if a chunk seems
   ambiguous.
3. Ask in the dsoageofheroes Discord.
4. For DSO-related questions, ask Greg Kennedy.

The point is that this is a small enough community that we should
ship code, not duplicate effort.
