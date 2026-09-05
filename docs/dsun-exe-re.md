# DSUN.EXE Reverse Engineering

The Dark Sun engine lives in `DSUN.EXE`. Both DS1 (*Shattered
Lands*, 611 KB) and DS2 (*Wake of the Ravager*, 634 KB) ship one
under that name; they descend from the same Watcom C/C++ codebase
but were compiled separately. This page is the maintainer's index
into the engine binary: where to look, what's known, and what
each finding unlocks for the rest of the toolkit. If you're new
to the engine, read [`research.md`](research.md) first; this page
assumes that context and a hex editor.

The companion symbol catalogue lives at
[`dso-symbols.md`](dso-symbols.md). That page is the
DSO-symbols-to-DS2-functions cross-reference; this page is the
behavioural / structural notes that come out of opening the
binary directly. The whole-binary measured structure (resident
API census, overlay int/PROLOGUE census, FOURCC vocabulary,
file surface, official-patch diff verdict) lives in
[`dsun-exe-survey.md`](dsun-exe-survey.md); this page stays the
behavioural index, the survey stays the numbers.

## 1. Binary layout

| | DS1 | DS2 |
|---|---|---|
| File size | 611,408 bytes (597 KB) | 634,416 bytes (619 KB) |
| Container | MS-DOS MZ executable | MS-DOS MZ executable |
| `e_lfanew` | `0x10000` | `0x10000` |
| Bytes at `e_lfanew` | `89 46 ...` | `89 46 ...` |
| MZ image ends | `0x52ea0` | `0x57570` |
| Signature at image end | `FBOV` | `FBOV` |
| MZ relocations | 4,853 | 4,703 |
| `INT 3Fh` sites | 994 | 904 |
| Overlay scheme | Borland/TLINK (VROOM), 16-bit real mode | same |

> **Correction (2026-08-08).** This table previously read
> "Extender: DOS/4GW DPMI, 32-bit overlay" for both games, and the
> paragraph below described "the real 32-bit code" sitting in a
> DPMI overlay. **That was wrong, and it sent the per-region
> palette caller-hunt (§3.3) down a dead end for a whole pass.**
> The evidence against it is unambiguous:
>
> - An **`FBOV`** signature sits immediately after the MZ image in
>   both binaries. That is the Borland/TLINK overlay header, not
>   anything DOS/4GW emits.
> - Both carry ~5,000 **MZ relocations**. A DOS/4GW program's MZ
>   part is a tiny stub with almost none; thousands of them mean
>   the real program *is* the MZ image, in real mode.
> - There are **994 / 904 `INT 3Fh` sites**. `INT 3Fh` is Borland's
>   overlay-manager entry point.
> - The code is **16-bit** with occasional `66` operand-size
>   prefixes. What looked like 32-bit code is 16-bit code compiled
>   for a 386: `66 68 43 4d 41 54` is `push dword 'CMAT'` *in a
>   16-bit segment*, not a 32-bit instruction.
> - No `LE` / `LX` header exists at `e_lfanew` because there is no
>   linear executable to find. That absence was read as "the
>   bin-loader can't cope"; it actually means "wrong format
>   assumed".
>
> The practical consequence is in §3.3: overlaid routines are not
> reached by `9A` far calls to their own code, so searching for
> those finds nothing. See §3.5 for how the overlay actually works
> and how to find a caller.

The MZ image at offset 0 **is** the program. Everything past the
`FBOV` header is the overlay area: code segments that the Borland
overlay manager pages in on demand. To read code, work in raw mode
against file offsets with 16-bit disassembly (`ndisasm -b 16`, or
`r2 -e asm.bits=16`), and use §3.5's overlay tables to turn a file
offset into a segment and an entry point.

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
region numbers. The open question was therefore: where does the
engine compute `family_id ∈ {0, 1, 100, 200, 300}` from a region
number, and what is that per-region map?

**Resolved 2026-08-08: there is no such map, because the
dispatcher is called exactly once in the whole program, with a
constant.** See §3.5 for the method; the result is:

- The dispatcher's overlay segment exports **three** entry points
  (`cs:0x0000`, `cs:0x0165`, `cs:0x042e`).
- Entry `cs:0x042e` (the dispatcher) has exactly **one** caller in
  the binary: a far call at file `0x01cc0f`.
- The other two entry points have **no** callers at all.
- That one caller pushes a literal `1`:

```
0000CBFF  833E721F04   cmp  word [0x1f72], 4
0000CC04  770F         ja   0xcc15            ; skip unless <= 4
0000CC06  833E7C112A   cmp  word [0x117c], 0x2a
0000CC0B  7508         jnz  0xcc15            ; skip unless == 42
0000CC0D  6A01         push word 1            ; family_id = 1, always
0000CC0F  9A2000BB41   call 0x41bb:0x0020     ; -> overlay stub -> dispatcher
0000CC14  59           pop  cx
```

So `si` is never region-derived, and the `si == 200` / `si == 300`
arms that hold the `CMAT` / `CPAL` load are **unreachable through
the only call path**. DS1 as shipped never loads a per-region
`CMAT` or `CPAL` at runtime through this routine, which is
consistent with `0x56ad3` / `0x56af0` being the only two sites in
the binary that push those FOURCCs at all (§3.4).

**What this means for `region-render`:** the current
`CPAL:200` engine-default fallback is the correct behaviour, not a
stopgap awaiting a per-region table. There is no per-region
palette selection to reproduce.

Two honest caveats. This is static analysis: an argument patched
at runtime, or a dispatch path that does not look like a call,
would not show up, though nothing seen suggests either. And the
guard (`[0x117c] == 42`) is not yet identified, so *what* that one
invocation is for remains open; it is plainly not "load the
palette for region N".

### 3.5 How overlaid code is actually called (the method)

The previous pass searched for `9A` far calls to `0x568be` and for
`E8` near calls landing there, and found nothing. Both searches
were correct and both were doomed, because **an overlaid routine
is never called at its own address.**

DS1 and DS2 are Borland-overlaid real-mode programs (see the
correction in §1). The scheme works like this:

1. Past the MZ image sits an `FBOV` header: `'FBOV'`, then dwords
   `ovrsize`, `exeinfo`, `segnum`. In DS1 that is file `0x52ea0`,
   so the **overlay area begins at `0x52eb0`**.
2. Each overlaid code segment is described by a record in the
   resident image that begins `CD 3F 00 00` and continues with a
   dword payload offset (relative to the overlay area) and a word
   size.
3. Immediately after each descriptor sit that segment's **entry
   stubs**, five bytes each: `CD 3F <entry_offset:2> <ovr:1>`.
4. A caller does an ordinary **far call to the stub**. `INT 3Fh`
   traps into the overlay manager, which pages the segment in and
   jumps to `entry_offset` within it.

So the call graph edge you are looking for points at the *stub*,
in the resident image, not at the function.

Worked example for the palette dispatcher:

| Item | Value |
|---|---|
| Overlay area base | `0x52eb0` |
| Segment descriptor | file `0x046fb0` |
| Descriptor payload / size | `0x35e0` / `0x0750` |
| Segment file range | `0x52eb0 + 0x35e0 = 0x56490` .. `0x56be0` |
| Entry stubs | `0x046fd0` (`cs:0x042e`), `0x046fd5` (`cs:0x0000`), `0x046fda` (`cs:0x0165`) |
| Dispatcher | `0x56490 + 0x042e = 0x568be` |
| Its one caller | far call at file `0x01cc0f` → `0x41bb:0x0020` |

The descriptor **independently confirms** the segment base that
§3.1 had inferred from zero-padding, and confirms its extent: the
segment ends at `0x56be0`, which is exactly where the switch jump
table (`0x56bd6` + five words) ends. That is a strong check that
the segmentation is right.

To find the callers of any overlaid routine:

1. Find the descriptor whose payload offset equals
   `segment_file_base - 0x52eb0`.
2. Read the stubs after it; match your routine's `cs:` offset.
3. Convert the stub's file offset to a load-image linear address
   by subtracting the MZ header size (`0x5400` in DS1).
4. Scan for `9A <off:2> <seg:2>` where `seg * 16 + off` equals that
   linear address. Cross-check that the segment word appears in the
   MZ relocation table (4,853 entries at file `0x3e`), since it is
   fixed up at load time.

The old `(0x0500, offset, 0x3a98)` array at `0x40670` and the
"DOS/4GW selector `0x3a98`" reading are both **withdrawn**. There
are no DOS/4GW selectors in this binary. That array is unrelated
bookkeeping and was a false lead.

The old plan under that model (walk the data segment for a table
of callable far pointers and find code loading from
`ds:<that table>`) is moot: the indirect channel was the overlay
stub all along.

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

### 4.4 The `0x23067` walker is NOT the cycle routine (correction)

> **Summary for the impatient:** `0x23067`-`0x23093` is the region
> GMAP / entity render loop, not palette cycling. The `66 ee`
> byte pair that started the wrong theory is two bytes of a
> 16-bit `mul`, not an `out dx, eax`. Read the correction for the
> method lesson; the cycle-routine hunt itself lives in §4.5.

An earlier revision of this section identified the loop at
`0x23067..0x23093` as the per-tick palette cycle walker, on
the strength of an apparent 32-bit `out dx, eax` instruction
(`66 ee`) at file offset `0x23075`. **That identification was
wrong**, and the documented inference chain was rooted in the
mis-disassembly.

The reason: the surrounding code segment is **16-bit**, not
32-bit DPMI. In 16-bit mode the bytes at `0x23074..0x23076`
parse as `f7 66 ee` = `mul word ptr [bp - 0x12]`, a single
instruction; the `66 ee` is the latter two bytes of `mul`'s
ModR/M + displacement encoding, not an operand-size override
plus `out`. The 0x66 prefix is meaningful only against a
32-bit code window; this isn't one. So the corpus-wide
pattern search for `66 ee` produced one DS1 hit and one DS2
hit, but both hits land inside 16-bit `mul` instructions and
neither does any palette I/O.

The walker itself is genuine code:

```
0x023067: a1 ca 57         mov  ax, [0x57ca]
0x02306a: 89 46 ee         mov  [bp-0x12], ax           ; outer counter
0x02306d: c4 3e 90 66      les  di, [0x6690]            ; base of an 8-byte-record table
0x023071: b8 08 00         mov  ax, 0x0008              ; record stride = 8
0x023074: f7 66 ee         mul  word ptr [bp-0x12]      ; ax = 8 * counter
0x023077: 03 f8            add  di, ax                  ; di -> record[counter]
0x023079: 26 8b 05         mov  ax, es:[di]             ; read first 2-byte field
0x02307c: 3b 06 4a 57      cmp  ax, [0x574a]            ; low filter
0x023080: 7c 06            jl   0x23088                 ; below low -> skip
0x023082: 3b 06 46 57      cmp  ax, [0x5746]            ; high filter
0x023086: 7c 0d            jl   0x23095                 ; in range -> work block
0x023088: ff 46 ee         inc  word ptr [bp-0x12]
0x02308b: a1 c8 57         mov  ax, [0x57c8]
0x02308e: 3b 46 ee         cmp  ax, [bp-0x12]
0x023091: 77 da            ja   0x2306d
```

What's *actually* there: the work block at `0x23095..0x2316d`
is the **region GMAP / entity render loop**. The body reads a
128-wide tile grid from `es:[0x556]`, masks the low 5 bits of
each cell as an entity-index, looks up a 4-byte record at
`[0x574c + 4 * (idx-1)]` carrying `(x_offset:u8, y_offset:u8,
sprite_id:u16)`, computes screen coordinates `(col*16 -
x_offset - arg0, row*16 + 16 - y_offset - arg1)`, and far-
calls a draw routine at `0x1df3:0x2adc` with the sprite-id and
coordinates. That maps cleanly onto the entity layer
`region-render` already renders (which is itself based on
libgff's `ds_object_t` / GMAP semantics), not onto palette
cycling.

So `[0x6690]`, `[0x57c8]`, `[0x5746]`, `[0x574a]` describe an
**entity-list culling** state, not a cycle table. The
record's first 2 bytes are some entity property the walker
filters on (likely a Y coordinate against vertical viewport
bounds, since the walker preludes the GMAP draw with a
top-of-screen sort). The remaining 6 bytes per record are
the rest of the entity metadata.

### 4.5 The actual palette-cycle routine remains unfound

> **Summary:** the complete palette-I/O inventory is in §4.2/4.3
> (six sites, no more). The cycle routine must call
> `write_palette_range` (0x288a4) or `load_full_palette` (0x144dc)
> rather than writing the DAC directly. The remaining search paths
> are in §4.5.4 (real-mode timer hooks, cycle-table data scan,
> DOSBox dynamic read, DS2 shape-match). The 0x23067 retraction is
> in §4.4 above.


The lesson from §4.4 is that VGA-port byte signatures
(`ba c8 03`, `ba c9 03`, single-byte `ee`) tag every palette
write site, but **none of them is unique to the cycle
routine**: the low-level palette helpers (`set_color`,
`write_palette_range`, `load_full_palette` from §4.2 / §4.3)
are shared by every code path that touches the DAC.

This section catalogues what's been ruled out, what's left to
try, and the findings that bound the remaining surface.

#### 4.5.1 Segment-selector hunt against `write_palette_range`

`0x288a4` sits in a code segment whose base is plausibly file
offset `0x28700` (the first 16-byte-aligned boundary after a
~900-byte zero-run that ends at `0x28706`). At that base,
`0x288a4` is at segment-local offset `0x01a4` (= `a4 01`
little-endian). The §3.3 trick (search the data segment for a
4-byte block matching `<offset> <selector>` paired with the
routine's segment-local offset) gives **17 total hits** on
`a4 01` across the binary, distributed across at least 14
distinct candidate selectors. No selector dominates the
distribution in the way `0x3a98` did for the §3 dispatcher,
so the trick doesn't disambiguate here. Either the routine's
segment is selected via a different mechanism (e.g. a
function-pointer table indexed at runtime, not a literal far
call) or the segment base is wrong (the routine actually lives
in a segment whose base is somewhere later in the zero-run,
making the offset different). The 17-hit set is in the doc as
a future-pass anchor, not a result.

#### 4.5.2 DPMI / timer-ISR hunt

Bytes `b8 05 02` (`mov ax, 0x205`, the DPMI Set-Protected-Mode-
Vector function code) **does not occur in DSUN.EXE**. Bytes
`b8 04 02` (`mov ax, 0x204`, Get-Protected-Mode-Vector) also
don't occur. The two `cd 31` (`int 31h`) hits at `0x88f12` and
`0x88fde` are **false positives**: the bytes appear inside
`mov ax, 0x31cd` immediates, not actual interrupts.

> **Correction (2026-08-08), consequent on §1.** This subsection
> previously concluded that "the DOS/4GW extender's runtime must be
> doing it on the engine's behalf" and sent the tick-handler thread
> off to study the DOS/4GW runtime. **There is no DOS/4GW runtime.**
> §1 established these are Borland-overlaid 16-bit real-mode
> programs, so that thread pointed at a component that does not
> exist in the binary.
>
> The DPMI evidence above is still *correct*, it is just no longer
> *informative*: a real-mode program has no reason to call
> `int 31h`, so the absence of `b8 05 02` / `b8 04 02` / real
> `cd 31` is exactly what the format predicts. It rules nothing in
> or out.
>
> **The replacement question** (not yet a finding): in a real-mode
> DOS program the timer is hooked either through `int 21h` with
> `AH=25h` (Set Interrupt Vector) or by writing the interrupt
> vector table directly, and the tick source is `int 8` (IRQ0) or
> `int 1Ch` (the BIOS user-timer hook). Those are the byte patterns
> worth inventorying next, in place of the DPMI set above.

#### 4.5.3 No additional palette-I/O sites

The complete inventory of `mov dx, 0x3c8` (`ba c8 03`),
`mov dx, 0x3c9` (`ba c9 03`), and `mov dx, 0x3c7` (`ba c7 03`)
in DS1 DSUN.EXE is **the six sites already catalogued in §4.2
and §4.3**. There is no eighth palette routine hiding
elsewhere. If the cycle routine exists, it MUST call one of
the six (most likely `write_palette_range` at `0x288a4` or
`load_full_palette` at `0x144dc`); it doesn't write to the
DAC directly.

#### 4.5.4 What's left to try

1. **Better segment-base candidate for `0x288a4`'s segment**.
   The zero-run guess (`0x28700`) is one possibility; the
   segment might actually start earlier (inside the
   zero-padding) or later (after a non-zero prologue that's
   common to the segment). ✅ **This no longer needs guessing.**
   The `FBOV` overlay descriptors carry each segment's real base
   and payload range; parsing them is exactly what `ovr-map`
   (Phase 5.5) ships. The old text said "DPMI / LX-overlay
   parsing would give the actual segment table", which was the
   wrong format (see §1) and is superseded by `ovr-map --verify`.
2. ~~**DOS/4GW runtime cross-reference**~~. **Struck 2026-08-08:
   there is no extender to cross-reference.** Replaced by the
   real-mode ISR inventory described in §4.5.2's correction
   (`int 21h`/`AH=25h`, direct IVT writes, `int 8` / `int 1Ch`).
3. **Locate cycle table via data-segment patterns**. If the
   cycle table is `count × N-byte record`, scanning the data
   segment for a uniform N-byte stride with plausible
   `(start, end, period, ...)` fields might surface it
   independently of finding the code that walks it. The
   `MAXLSTRINGS`-sized arrays in libgff's GPL VM state are
   the existing model for this kind of search.
4. **Dynamic analysis under DOSBox**. `opcode-fuzz v0.2.0`
   ships the chunk-swap + observe pipeline; if the engine
   writes the cycle table to a memory location that's
   reachable via the GPL global-arrays path, we could read
   the table at runtime instead of locating it statically.
   That'd require knowing the table's address in memory
   anyway, so it's not a shortcut.
5. **DS2 shape-match**. If we ever get a function-table dump
   from the DSO debug build, names like `VGAColorCycle` /
   `VGASetCycle` map to DS2 DSUN.EXE byte signatures by
   call-graph shape (the proven path in §3). Without the
   table, we're back to the same byte-pattern search that
   stalls on DS1.

`region-render v0.6.0` was a time-boxed third attempt at
this surface; the attempt produced the findings in this
subsection but not a working `--animate` flag, so
`region-render` stays at v0.5.0.

### 4.6 DSO symbol cross-reference

Moved to [`dso-symbols.md`](dso-symbols.md), which owns the DSO
symbol material (source, curation, the Decode\* dispatch study,
and the curated catalogue). Summary retained here: the DSO v1.0
client names the VGA colour-cycle path (`VGASetCycle`,
`VGAResetCycle`, `VGAColorCycle`, `cycleshow`, the `gCycleColor`
global); offsets are DSO-relative and do not map onto DSUN.EXE,
only the names transfer. The DSUN.EXE counterpart identification
at `0x23075` was retracted with §4.4 (that region is the GMAP /
entity render loop); `0x23067` was never it either.

## 5. What we still don't know

> ⓘ The whole-binary survey
> ([`dsun-exe-survey.md`](dsun-exe-survey.md), 2026-08-28) adds
> measured structure to several items below: the resident API
> surface is ~340 functions (census in survey §3.3), the overlay
> manager body is at file `0x466e0` (DS1) / `0x4aff0` (DS2), the
> save/region module is string-anchored via `gpldisk.c` breadcrumbs,
> and item 5 is resolved to a file offset. See survey §9 for the
> item-by-item answers.

These are the next pieces an RE pass should crack, in rough
order of value to the toolkit:

1. **RESOLVED 2026-08-08: there is no region-number-to-
   family-id map** (DS1). §3.2 had narrowed the question to the
   five family ids (`{0, 1, 100, 200, 300}`) and the dispatcher
   at `0x568be`; the follow-up pass concluded no lookup table
   exists to find. The better prize replaced it: the save/region
   module is string-anchored instead (see §3.3's breadcrumbs and
   the `syms/ds1.toml` anchors; survey §9.1).
2. **The CMAT format**. With two known instances at 41,368 and
   21,643 bytes, the per-entry layout should be derivable from
   how the engine consumes the buffer. The success path after
   `or ax, ax; jne` (at `0x56ae5 + 0x7b = 0x56b60`) is the
   consumer's code window.
3. **Animated palette cycle routine**. The earlier
   identification of `0x23067` as the cycle walker was
   retracted in §4.4 (the walker is region GMAP / entity
   rendering, not palette cycling). The actual cycle routine
   remains unfound. §4.5 lists the three productive next
   directions: a caller search against `write_palette_range`
   (`0x288a4`), a tick-handler trace through the engine's
   main loop, or shape-matching DS2 against DSO's
   `VGAColorCycle` symbol if we can extract a function-table
   dump.
4. **DS2's palette source**. With CMAT/CPAL gone, DS2 must select
   a region palette some other way. Cross-check the four DS2
   `'PAL '` push sites (`0x2b770`, `0x68ab5`, `0x71f94`,
   `0x8db24`) against the DSO symbol table to identify the
   region-render path vs. the menu/title path.
5. **RESOLVED: the DS2 `load_resource` segment** maps to file
   `0x692b` (`0128:04ab` with header `0x5200`; survey §9.5), and
   the function is named in `syms/ds2.toml` (verified). Its DS1
   counterpart `0x58b4` is catalogued alongside.

## 6. How to reproduce the findings on this page

All of section 2 / 3 was extracted with Python against the raw
file bytes. Radare2 can't auto-load the Borland/TLINK overlay
(§1; the old text here said "DOS/4GW DPMI overlay", same
mistake), so byte-pattern search was the working tool. The
minimal recipe below still stands, but see §7 for the tooling
that now supersedes hex-search for anything overlay-aware.

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
feed the slice to Capstone. ⚠ **Use `CS_MODE_16`, not `CS_MODE_32`**
(`md = Cs(CS_ARCH_X86, CS_MODE_16)`). This line said `CS_MODE_32`
until 2026-08-08, a leftover from the disproved extender theory in
§1; decoding this 16-bit binary in 32-bit mode silently produces
plausible-looking garbage rather than an error, which is the worst
possible failure for RE work. The patterns in section 2 are short
enough that hand-decoding catches it.

## 7. Related

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

## 8. Tooling

The host RE tooling (Ghidra 12.1.2 + pinned Temurin JDK, pwntools)
and the headless Ghidra pipeline moved to
[`re-tooling.md`](re-tooling.md): setup, the runnable recipe for
this checkout, and the OSGi troubleshooting entry. `radare2`
remains the scriptable first stop for everything in sections 1-6.
