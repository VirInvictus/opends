# DSUN.EXE Reverse Engineering

The Dark Sun engine lives in `DSUN.EXE`. Both DS1 (*Shattered
Lands*, 611 KB) and DS2 (*Wake of the Ravager*, 634 KB) ship one
under that name; they descend from the same Watcom C/C++ codebase
but were compiled separately. This page is the maintainer's index
into the engine binary: where to look, what's known, and what
each finding unlocks for the rest of the toolkit.

The companion symbol catalogue lives at
[`dso-symbols.md`](dso-symbols.md). That page is the
DSO-symbols-to-DS2-functions cross-reference; this page is the
behavioural / structural notes that come out of opening the
binary directly.

## 1. Binary layout

| | DS1 | DS2 |
|---|---|---|
| File size | 611,408 bytes (597 KB) | 634,416 bytes (619 KB) |
| Container | MS-DOS MZ executable | MS-DOS MZ executable |
| `e_lfanew` | `0x10000` | `0x10000` |
| Bytes at `e_lfanew` | `89 46 ...` | `89 46 ...` |
| Extender | DOS/4GW DPMI, 32-bit overlay | DOS/4GW DPMI, 32-bit overlay |

The MZ stub at offset 0 is the loader; the real 32-bit code sits
in a DOS/4GW DPMI overlay after it. The four bytes at `e_lfanew`
are **not** an LE / LX signature, so radare2's bin-loader can't
chop the executable into segments automatically. To read code,
work in raw mode against file offsets (`r2 -e bin.cache=true
-e asm.bits=32`) or hex-search for the patterns documented below
and disassemble small windows by eye / with Capstone.

## 2. The resource loader: `load_resource(fourcc, id, far*)`

There is a single internal helper that loads a typed chunk from
the active resource container, by FOURCC + id. Everything the
engine does at runtime that touches `RESOURCE.GFF`, `GPLDATA.GFF`,
or any other GFF goes through it. Identifying the call site
unlocks the engine-side mapping for every chunk type we already
read offline.

### Signature

```c
int load_resource(uint32_t fourcc, int id, void far *out_buf);
```

Calling convention (cdecl, Watcom): args pushed right-to-left,
caller cleans up. The setup pattern at every call site is the
same six instructions:

```
16              push ss              ; far ptr seg
8d 46 XX        lea  ax, [bp-XX]     ; far ptr offset (local buffer)
50              push ax
66 0f bf c6     movsx eax, si        ; id, sign-extended from SI
66 50           push eax
66 68 FC FC FC FC  push dword <FOURCC>  ; e.g. 66 68 43 4d 41 54 = 'CMAT'
9a XX XX XX XX  call far <seg>:<off> ; the loader
83 c4 0c        add  esp, 12         ; cdecl cleanup, 3 dwords
```

Return value: `AX` (`eax` low word). Engine code immediately
follows with `0b c0 75 XX` (`or ax, ax; jne short XX`), which
treats **non-zero as failure** and falls through on success. (At
least at the CMAT/CPAL site; the convention may invert
elsewhere, verify per site.)

### Two distinct loader entry points

| Game | Far-call target | Call sites (push FOURCC + call) |
|---|---|---|
| DS1 | `0001:04a4` | 96 total: CMAT 1, CPAL 1, PAL 4, GMAP 2, etc. |
| DS2 | `0128:04ab` | Used by all FOURCC pushes; CMAT/CPAL absent. |

Both engines route every FOURCC-keyed lookup through one
function. DS1's target is at logical address `0001:04a4`; DS2's
is at `0128:04ab`. Treat them as the canonical
`load_resource`. Mapping the segment to a file offset is the next
step (would let us name DS2 functions from `.dso-online`'s symbol
table by call-graph shape).

## 3. Per-region palette + remap (DS1 only)

### 3.1 Routine overview

The CMAT and CPAL pushes both live inside one function. The
function is a **switch on a single 16-bit argument** (let's call
it `family_id`) that picks one of five known cases. The CMAT /
CPAL load lives in the `family_id == 200` and `family_id == 300`
arms of that switch.

| File offset | Element | Notes |
|---|---|---|
| `0x56490` | Helper function entry | Called by the dispatcher 3 times. Reads `[bp+6]` into `si`. Pushes `'ETAB'`, dword 1000, far-calls `0xf0:0x05d0`. Probably the region-load worker. |
| `0x568be` | Dispatcher function entry | `55 8b ec 83 ec 0e 56 57 8b 76 06`. Reads `[bp+6]` (`family_id`) into `si`, zeros three dword locals (`[bp-4]`, `[bp-8]`, `[bp-12]`), tests global `[0x1162]`, then enters the switch. |
| `0x568f1` | Switch dispatch | `mov cx, 5; mov bx, 0x073c; cs:[bx]` linear-scan of the cmp table, `jmp far cs:[bx+10]` when matched. |
| `0x56bcc` | Switch comparison table | Five 16-bit entries: `{0, 1, 100, 200, 300}`. |
| `0x56bd6` | Switch jump table | Five 16-bit `cs:` offsets: `{0x047a, 0x0532, 0x0574, 0x060d, 0x060d}`. |

`cs.base` for this segment is at file offset `0x56490` (the
preceding region is zero-padded, consistent with a segment-start
alignment). Every `cs:0xXXXX` reference in this section
resolves to file offset `0x56490 + 0xXXXX`.

### 3.2 The five family cases

| Case | `cs:off` | File offset | What it does |
|---|---|---|---|
| `si == 0` | `0x047a` | `0x5690a` | Calls helper `0x56490` with arg 0, then far-calls `0530:0025` (resource loader for a different chunk type), then far-calls `0660:0020(1)`. No CMAT/CPAL. |
| `si == 1` | `0x0532` | `0x569c2` | Sets `di = 1`, calls helper `0x56490` with arg 1, then runs a similar load chain. No CMAT/CPAL. |
| `si == 100` | `0x0574` | `0x56a04` | Three sequential far-calls to `0038:4723(1)` / `0038:4feb(0)` / `0038:4723(0)`, plus `0090:013f()`, then helper `0x56490(0)`. No CMAT/CPAL. |
| `si == 200` | `0x060d` | `0x56a9d` | Two preliminary far-calls (`0088:22ba`, `0088:2c2c`), then the same `0038:` helper triplet as case 100, then **`load_resource('CMAT', 200, &buf); if (failed) load_resource('CPAL', 200, &buf);`**. |
| `si == 300` | `0x060d` | `0x56a9d` | **Falls through to the same handler as 200.** The id 300 is supplied to the CMAT / CPAL load only because it's still in `si`. |

Default (anything not in the five): `jmp +0x2db` → `0x56bc8`,
which is the function's epilogue / fall-through.

### 3.3 What we still need to crack

The switch handles **five fixed family ids**, not 50-odd
region numbers. So the engine's region-load path must compute
`family_id ∈ {0, 1, 100, 200, 300}` from the region number
*before* calling this dispatcher. Identifying that
region-number-to-family-id mapping (per region in DS1) is the
remaining gap.

Pattern-search for callers of the dispatcher at `0x568be`
turned up zero hits across the obvious channels: no
`9a 2e 04 <seg> <seg>` (16-bit far call), no `9a 2e 04 00 00
<seg> <seg>` (32-bit far call), no `e8` near call landing on
`0x568be`, and no other `9a` site with a target offset of
`0x042e`. The dispatcher is reachable via some indirect
mechanism that byte-pattern search doesn't surface.

**One real signal did fall out of the caller-trace pass: the
segment selector for the dispatcher's code segment is
`0x3a98`.** It's the only `2e 04` (offset `0x042e`) value at a
2-byte-aligned position outside the segment itself; the
adjacent bytes resolve to a far pointer `0x3a98:0x042e`. So
the code segment that starts at file offset `0x56490`
corresponds to DOS/4GW selector `0x3a98`. That maps cleanly
onto the dispatcher entry: `0x3a98:0x042e` is file
`0x56490 + 0x042e = 0x568be`. Useful for naming the segment
in any future RE pass.

The reference itself, however, sits inside a long array of
uniform 6-byte records of the form `(0x0500, offset, 0x3a98)`
at file `0x40670..` onward, with `offset` ascending by `0x0c`
per entry (`0x031a, 0x0326, 0x0332, ..., 0x042e, 0x043a, ...`).
The targets at every twelfth byte in segment `0x3a98` mostly
fall mid-instruction, not on function prologues, so the array
isn't a function-pointer table. It looks more like a Watcom
or DOS/4GW emitted bookkeeping table (relocations, line-number
records, or similar). Worth verifying once we have an LE / LX
parser, but it's not the caller channel.

What's worth trying next: walk the data segment forward from
the bookkeeping table looking for a *different* table with
4-byte entries that holds real callable far pointers, and
search for code that loads from `ds:<that table>` to find the
indirect-call site.

### 3.4 Original finding: the CMAT-first / CPAL-fallback pattern



DS1 ships exactly **one** code site that pushes `'CMAT'` or
`'CPAL'`:

| File offset | What's pushed | Reads as |
|---|---|---|
| `0x56ad3` | `66 68 43 4d 41 54` | `push 'CMAT'` |
| `0x56af0` | `66 68 43 50 41 4c` | `push 'CPAL'` |

The 29 bytes between them are the inter-call branch:

```
9a a4 04 00 01   call far 0001:04a4   ; load CMAT
83 c4 0c          add  esp, 12
0b c0             or   ax, ax
75 7b             jne  short +0x7b    ; if CMAT failed, skip CPAL
16                push ss
8d 46 f4          lea  ax, [bp-12]    ; second local buffer
50                push ax
66 0f bf c6       movsx eax, si       ; same id
66 50             push eax
66 68 43 50 41 4c push 'CPAL'         ; ...load CPAL
```

Both loads use **the same `si` as the id**, and they write into
**two different local buffers** (`[bp-8]` for CMAT, `[bp-12]` for
CPAL). The branch (`jne short +0x7b`) skips the CPAL load when
CMAT succeeded.

### What this means

DS1's engine, for some region-derived id `si`, attempts:

1. `load_resource('CMAT', si, &cmat_buf)`. If non-zero (failure),
   continue to step 2.
2. `load_resource('CPAL', si, &cpal_buf)`.

CMAT is the **colour remap table** (libgff has no documented
consumer; sizes in `RESOURCE.GFF` are 41,368 and 21,643 bytes,
consistent with bulk remap data, not a 768-byte palette). CPAL
is the **custom palette** (full 768-byte PAL replacement). The
fall-through behaviour means the engine prefers a CMAT *delta*
over a CPAL *replacement* when both could apply: each region
either uses a tweak of the base palette (CMAT) or a full custom
palette (CPAL), not both.

`RESOURCE.GFF` ships two of each:

| FOURCC | Ids present | Size (bytes) |
|---|---|---|
| `CMAT` | 200, 300 | 41,368 / 21,643 |
| `CPAL` | 200, 300 | 768 / 768 |

So `si` resolves to one of `{200, 300}` at this call site,
meaning the engine recognises **two palette families** keyed on
some region property. Likely candidates: outdoor/desert vs.
interior/dungeon; biome; or daytime/nighttime variant. The
mapping of region number to family id is in the calling routine
(not yet decoded).

### DS2 dropped CMAT entirely

DS2's `DSUN.EXE` contains **zero** CMAT or CPAL FOURCC pushes
and zero `'CMAT'` / `'CPAL'` byte sequences. DS2 also ships no
CMAT or CPAL chunks in any GFF in the GOG 1.10 corpus. The
engine reverted to plain `PAL` lookups for palette work. Whether
that means "every DS2 region uses the menu palette" or "DS2
palettes come from a different chunk type entirely" is open.

## 4. Palette I/O catalogue and animation routine

The CMAT/CPAL routine in §3 picks *which* palette to load. The
runtime engine that actually pushes the bytes to the VGA DAC is
a separate cluster of small helpers, all reachable via byte-
pattern search for VGA port-0x3c8 / port-0x3c9 / port-0x3c7
writes (`ba c8 03` / `ba c9 03` / `ba c7 03` followed by `ee`).
This section is the catalogue and the partial decode of the
animated-palette path.

### 4.1 Per-binary byte-pattern hit counts

```
DS1 DSUN.EXE                      DS2 DSUN.EXE
  ba c8 03  (mov dx,0x3c8): 4       ba c8 03: 5
  ba c9 03  (mov dx,0x3c9): 2       ba c9 03: 2
  ba c7 03  (mov dx,0x3c7): 2       ba c7 03: 2  (in 0x11693 cluster)
  66 ee     (out dx,eax)  : 1       66 ee   : 1  (the lone 32-bit
                                                  palette I/O site)
```

The lone 32-bit `out dx, eax` instance in each binary is the
loadbearing one; the inner loops of the animation routine sit
in a 32-bit code segment.

### 4.2 The DS1 palette-helper cluster at `0x1168c..0x116f3`

Four adjacent 16-bit far-call routines back-to-back. Per-entry
prologue is the standard Watcom shape (`55 8b ec ... cb`). These
are the lowest-level VGA primitives:

| File offset | Signature | What it does |
|---|---|---|
| `0x1168c` | `set_color(idx, r, g, b)` | `mov dx,0x3c8; out dx,al`; `inc dx; out three RGB bytes`. Writes one palette entry. Args from `[bp+6..0xc]`. |
| `0x116a7` | `read_color_far(idx, *r, *g, *b)` | `mov dx,0x3c7; out`; `mov dx,0x3c9; in al,dx` three times; result stored via far ptrs (`les bx, ptr`). |
| `0x116cf` | `read_color_near(idx, *r, *g, *b)` | Same shape with near pointers (`mov bx, word ptr`). |
| `0x116f4` | `lookup_remap_row(idx)` | Indexes a multi-row table at `cs:0x4` with rows at `+0x000`, `+0x200`, `+0x400`, `+0x600`, `+0x800`, ... and copies row entries into globals `[0xe04..]`. **Not a palette write directly; this looks like a brightness / fade / remap row reader.** Eight rows of 256 words = 4 KB total. |

The two `0x3c9` hits inside this cluster (file `0x116b4` and
`0x116dc`) are the DAC read-data ports for the read-color
helpers. Earlier counts that looked like "two distinct
palette routines" are actually one read function in two
near/far variants.

### 4.3 The DS1 bulk-palette routines at `0x144dc` and `0x288a4`

| File offset | Signature | What it does |
|---|---|---|
| `0x144dc` | `load_full_palette(buf)` | Sets all 256 entries from a 768-byte RGB buffer. Each lobed byte is right-shifted by 2 (`shr al, 1; shr al, 1`) to convert 8-bit values to the 6-bit DAC range; the same `intensity_multiplier` divergence libgff documents in the opposite direction for CPAL parsing. |
| `0x288a4` | `write_palette_range(start, count, *buf)` | Writes `count` entries starting at index `start`, reading RGB triples from `ds:si`. **No `>> 2` shift here**, so the buffer is already in 6-bit DAC form. Tight `lodsb / out` loop. |
| `0x288c4` | `read_palette_range(start, count, *buf)` | Inverse of `0x288a4`: reads `count` entries into `es:di`. No shift either way. |

These three handle full-palette loads and arbitrary range writes
and are the obvious candidates for the consumer side of the
CMAT/CPAL fallback (§3) and the per-tick cycle update (§4.4).

### 4.4 The cycle-table walker at `0x23075` (partial)

The lone 32-bit `out dx, eax` (`66 ee`) site in DS1 sits inside
a small loop that reads from an **8-byte-record table** indexed
by a counter. Decoded in 16-bit mode (the surrounding context
is 16-bit; `f7 66 ee` is `mul word ptr [bp-0x12]`, not three
separate opcodes; Capstone in 32-bit mode mis-splits these
bytes):

```
0x023067: a1 ca 57         mov  ax, [0x57ca]            ; load count? threshold?
0x02306a: 89 46 ee         mov  [bp-0x12], ax           ; save as counter
0x02306d: c4 3e 90 66      les  di, [0x6690]            ; cycle-table base
0x023071: b8 08 00         mov  ax, 0x0008              ; record stride = 8
0x023074: f7 66 ee         mul  word ptr [bp-0x12]      ; ax = 8 * counter
0x023077: 03 f8            add  di, ax                  ; di -> record[counter]
0x023079: 26 8b 05         mov  ax, es:[di]             ; read first 2-byte field
0x02307c: 3b 06 4a 57      cmp  ax, [0x574a]
0x023080: 7c 06            jl   0x23088                 ; below low bound -> skip
0x023082: 3b 06 46 57      cmp  ax, [0x5746]
0x023086: 7c 0d            jl   0x23095                 ; in range -> do work
0x023088: ff 46 ee         inc  word ptr [bp-0x12]      ; counter++
0x02308b: a1 c8 57         mov  ax, [0x57c8]
0x02308e: 3b 46 ee         cmp  ax, [bp-0x12]
0x023091: 77 da            ja   0x2306d                 ; loop while counter < limit
```

What we have from this window:

- **Record size**: 8 bytes (the literal `mov ax, 8; mul counter`).
  Fits a `(start_index, end_index, period, current_phase)` layout
  at 2 bytes each, or `(start, end, period_ticks, accumulator)`.
- **Table base**: `es:[0x6690]` is a far pointer to the table in
  whatever segment the cycle data sits in.
- **Table size**: word at `[0x57c8]` (data segment) is the entry
  count.
- **Range bounds in globals**: `[0x5746]` and `[0x574a]` are
  4 bytes apart and look like `(low, high)` filter window the
  walker compares the first record field against. Whether this
  is "current palette index being redrawn" or "tick value range"
  is open.
- **The work block** at `0x23095` (the `jl in-range` target) is
  where the actual cycle update happens. Likely a call into
  `set_color` (`0x1168c`) or `write_palette_range` (`0x288a4`)
  with rotated buffer contents.

This is enough to know the cycle table is `count × 8 bytes` of
some `(low, high, ...)` structure. Recovering the field-level
semantics (what the remaining 4 bytes per record do, and where
the runtime tick is fed in) is the next pass.

### 4.5 Cross-game parallels

DS2's mirror routines sit at the same offsets relative to its
segment (`0x13bc3` etc. for the palette-write cluster, with
`0x3c7` reads at `0x13be4` / `0x13c0c`). The 32-bit `out
dx,eax` site is at file `0x26e51` in DS2; cycle-table walker
shape is expected to match. Confirming this is a small followup
pass once the DS1 record layout is fully decoded.

### 4.6 DSO symbol cross-reference

The DSO v1.0 client (`.dso-online/tools/symbols.txt`) names
the cycle path in three pieces:

| DSO offset | Symbol | Likely DSUN.EXE counterpart |
|---|---|---|
| `0x0009E98A` | `VGASetCycle` | Cycle-table install (writes `[0x6690]` / `[0x57c8]` etc.) |
| `0x0009E9C9` | `VGAResetCycle` | Cycle teardown |
| `0x0009EAA3` | `VGAColorCycle` | Per-tick walker; the function containing `0x23075`. |
| `0x000BE8ED` | `cycleshow` | Higher-level "render with cycling enabled" wrapper |
| `0x00167C6D` | `gCycleColor` | The cycle-state global. The `[0x6690]` / `[0x57c8]` / `[0x5746]` / `[0x574a]` cluster in DS1 is the data-side embodiment of this symbol on the engine binary. |

These names are anchors; the offsets are DSO-relative and don't
map directly to DSUN.EXE. But the call-graph shape (4-byte
record walker reading from a far pointer at fixed offset) is
distinctive enough to confirm `0x23075`'s function is the
`VGAColorCycle` counterpart once we have a caller-trace.

## 5. What we still don't know

These are the next pieces an RE pass should crack, in rough
order of value to the toolkit:

1. **The region-number-to-family-id map** (DS1). §3.2 narrowed
   the question: each region picks one of five family ids (`{0,
   1, 100, 200, 300}`) before calling the dispatcher at
   `0x568be`. Finding the caller (or whatever indirect dispatch
   table reaches `0x568be`) gives us the lookup. Byte-pattern
   search for direct callers turned up zero hits; the next try
   is walking function-pointer tables in the data segment
   backwards from `0x568be`.
2. **The CMAT format**. With two known instances at 41,368 and
   21,643 bytes, the per-entry layout should be derivable from
   how the engine consumes the buffer. The success path after
   `or ax, ax; jne` (at `0x56ae5 + 0x7b = 0x56b60`) is the
   consumer's code window.
3. **Animated palette cycle-table field semantics**. §4.4
   narrowed this from "open question" to "decode the 6 unknown
   bytes per record". The walker at file `0x23075` confirmed:
   record size = 8 bytes, table base = `es:[0x6690]`, count =
   word at `[0x57c8]`, filter window = `[0x5746]`/`[0x574a]`.
   The first 2 bytes of each record are what the walker
   compares against the filter; the remaining 6 bytes per
   record carry start/end/period/phase. Next step: trace the
   in-range path at `0x23095` to see which palette write
   routine (`0x1168c` single-color or `0x288a4` range) it
   delegates to, and read off the field positions from the
   stack offsets it uses. The `VGASetCycle` / `VGAResetCycle`
   DSO symbols (§4.6) name the install/teardown sites; finding
   them gives us the writer's view of the same fields.
4. **DS2's palette source**. With CMAT/CPAL gone, DS2 must select
   a region palette some other way. Cross-check the four DS2
   `'PAL '` push sites (`0x2b770`, `0x68ab5`, `0x71f94`,
   `0x8db24`) against the DSO symbol table to identify the
   region-render path vs. the menu/title path.
5. **The DS2 `load_resource` segment**. The DS2 target
   `0128:04ab` needs mapping to a file offset; then the function
   can be named by call-graph shape against DSO's symbol table
   (`GffSeekChunk`, `GetResource`, `LoadResource` are the
   plausible names).

## 5. How to reproduce the findings on this page

All of section 2 / 3 was extracted with Python against the raw
file bytes. Radare2 can't auto-load the DOS/4GW DPMI overlay,
so byte-pattern search is the working tool. The minimal recipe:

```python
import re
with open('.games/ds1/DSUN.EXE', 'rb') as f:
    data = f.read()

# every FOURCC push
for fcc in (b'CMAT', b'CPAL', b'PAL ', b'GMAP'):
    push = b'\x66\x68' + fcc
    print(fcc, [hex(m.start()) for m in re.finditer(re.escape(push), data)])

# at each site, the 8 bytes after the 6-byte push are 'call far <seg>:<off>; add esp, 12'
```

For window disassembly without r2: pull 64-128 bytes around the
site of interest and decode by hand against the Intel manual, or
feed the slice to Capstone (`md = Cs(CS_ARCH_X86, CS_MODE_32)`).
The patterns in section 2 are short enough that hand-decoding
catches it.

## 6. Related

- [`dso-symbols.md`](dso-symbols.md) is the DSO function-name
  cross-reference; pair findings on this page with candidate
  names from there.
- [`file-formats.md`](file-formats.md) documents the `CPAL`
  chunk layout. CMAT is the open piece called out in section 4.
- [`research.md`](research.md) is the per-game GFF survey that
  established the CMAT/CPAL chunk inventory referenced above.
- [`upstream-projects.md`](upstream-projects.md) links to the
  `libgff` and `dsoageofheroes` work that shaped the GFF chunk
  vocabulary the engine consumes.
