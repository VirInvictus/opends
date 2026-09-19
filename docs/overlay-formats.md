# The Borland overlay (FBOV) apparatus: exeinfo, module table, relocations, dispatcher

The overlay loader of both engines, decoded byte-exactly (port-mining wave 1,
2026-09-19). Everything here is original to this pass: no public FBOV parser
exists in the reference clones (`.dsoageofheroes/`, `.dso-online/`,
`.dsun_music/` were checked; only an unrelated MZ-header reader in
`.dso-online/tools/unwatcom.pl`), and the structures were read from the
binaries with ndisasm + python. Verified on the GOG 1.10 corpus. This is the
static unlock for resolving far calls into overlay code (the spell
cast/apply handler route the bestiary campaign named).

Conventions: DS1 = `.games/ds1/DSUN.EXE` (611,408 B), DS2 =
`.games/ds2/DSUN.EXE` (634,416 B; called "DS2.EXE" in older docs). All
addresses are file offsets unless marked as segment:offset. MZ header sizes:
0x5400 (DS1, e_cparhdr 1344) and 0x5200 (DS2, 1312).

## 1. Header chain

| Item | DS1 | DS2 |
|---|---|---|
| MZ image end | 0x52ea0 | 0x57570 |
| `FBOV` signature | 0x52ea0 | 0x57570 |
| `ovrsize` (dword @+4) | 0x425a0 (271,776) | 0x438b0 (276,912) |
| `exeinfo` (dword @+8) | 0x46770 | 0x4b080 |
| `segnum` (dword @+0xc) | 220 | 229 |
| Overlay area (image_end+16 .. +16+ovrsize = EOF) | 0x52eb0..0x95450 | 0x57580..0x9ae30 |
| Build name (string after segtab) | "darkcd.exe" @ 0x46e50 | "dsmall.exe" @ 0x4b7a8 |

## 2. exeinfo is the SEGMENT LOAD TABLE (not debug data)

`segnum` records of 8 bytes at `exeinfo`:

```
word0  load paragraph (base-relative segment value; absolutized at runtime
       by the MZ relocation pass)
word1  byte size
word2  class (1 = code, 0 = data, 3 = overlay stub block, 4 = BSS marker)
word3  small ordinal, semantics open (possibly combine-group/overlay affinity)
```

DS1 records 0x46770..0x46e50; DS2 0x4b080..0x4b7a8. Class counts (DS1/DS2):
code 82/87, data 66/79 (the last data record is the stack: start == e_ss,
size == e_sp), overlay stub blocks 58/49, BSS markers 14/14 (size 0xffff).
At runtime the table lives at DGROUP:0x1a0 in both games (DS1 segtab segment
0x4137, DS2 0x45e8; see section 5 for why the segment value matters).

Every record's word0 is the target of exactly one MZ relocation (220/220
DS1, 229/229 DS2, all at field offset 0), and no MZ relocation targets the
descriptor region. This table is what the overlay manager actively walks.

## 3. The descriptor chain (the overlay "module table")

The chain begins at the first `CD 3F 00 00` after exeinfo and ends at the
Borland copyright string: DS1 0x46e60..0x48960, DS2 0x4b7c0..0x4d000 (these
end offsets are the prior waves' "DGROUP data anchors"). 32-byte descriptors:

```
+0x00  CD 3F 00 00          signature
+0x04  dword                payload offset, relative to the overlay area base
+0x08  word                 module CODE size (bytes)
+0x0a  word                 relocation-table size IN BYTES (entry count = value/2)
+0x0c  dword                entry-stub count
+0x10..0x1f                runtime scratch, zero on disk:
       +0x10 load segment, +0x18 near-offset of the reader (0x4c9 DS1 /
       0x4c6 DS2, written by init), +0x1a flags (bit2 in-use, bit3 cold
       load), +0x1b lock count, +0x1c LRU-next
+0x20..                    nstubs x 5-byte entry stubs, disk form CD 3F <entry_off:2> <0>
```

Facts that correct earlier readings:

- The stub's 5th byte is NOT an overlay id: it is 0 in all 935 (DS1) / 854
  (DS2) stubs and the handler never reads it (DS1 0x3be46, DS2 0x40563 read
  only the 2-byte entry offset). Overlay identity comes from the stub's
  SEGMENT.
- Descriptors are padded toward 16-byte alignment but gaps can exceed one
  paragraph; walk the chain, do not stride.
- The class-3 segtab records pair 1:1, in order, with the descriptor chain
  (verified for all 58/49): record `start_para` -> file `header +
  start_para*16` == descriptor offset; record `size` == 32 + 5*nstubs. DS1's
  6 empty slots (chain indices 18, 20, 23, 31, 39, 56) have class-3 records
  of size 0x20. Overlay id = chain index (minus the first class-3 record's
  segtab index: 151 DS1, 169 DS2).

## 4. Per-module relocation tables (static file data)

Each module in the overlay area is laid out `code (size bytes) |
relocation table (nreloc bytes) | zero pad to >= 16-alignment`. Entry
format: one little-endian word per entry = the byte offset WITHIN THE MODULE
of a segment word to translate; entries are mostly descending, no
terminator (the count is explicit).

Totals (validated exhaustively on all 101 modules: every entry < module
size, table-to-next-payload bytes all zero, all counts even):

| | DS1 | DS2 |
|---|---|---|
| Live modules | 52 (+6 empty) | 49 |
| Entry stubs | 935 | 854 |
| Module code bytes | 253,109 | 258,376 |
| Relocation table | 16,464 B = 8,232 entries | 16,524 B = 8,262 entries |
| Alignment slack | 2,203 | 1,780 |
| MZ (resident) relocations | 4,853 @ file 0x3e | 4,703 @ file 0x3e |

This supersedes the roadmap's 5.6.1 claim that these tables are "BSS,
runtime-populated": they are static file data, and the exeinfo block is the
segment load table the manager depends on, not a Turbo Debugger symbol
dump. The 4,853/4,703 figures quoted there are the MZ header's
resident-image relocation counts, a different table. tools/exe-patch's
`classify()` consults neither; an edit near any segtab record's word0 or
near a module-boundary relocation table is dangerous in ways classify()
cannot currently see.

## 5. The dispatcher (INT 3Fh machinery)

Handler entry points: DS1 file 0x3be27 (segment 0x3653 = segtab record 80,
offset 0x4f7; `iret` at 0x3be8c), DS2 file 0x40544 (segment 0x3ae5 = record
85, offset 0x4f4; `iret` at 0x405a9). (The survey's 0x466e0/0x404c4 "handler
bodies" were wrong: DS1 0x466e0 and DS2 0x4aff0 are degenerate 5-byte
`CD 3F 00 00 00` null-stub blocks in resident data, segments 0x412e/0x45df.)
Mechanics, instruction cites DS1 (DS2 is byte-identical logic):

1. A stub executes `INT 3Fh`; the interrupt frame lands with IP on the 3
   data bytes. Handler: `push bp; mov bp,sp; test bp,1` (odd-BP guard,
   aborts via `jmp far 0000:0x2df` at 0x3be30), saves regs, `mov ds,DGROUP`,
   `sti`.
2. `les bx,[bp+2]` (0x3be43): es = the stub's segment = the class-3 segment
   whose offset 0 IS the descriptor; bx points at the entry-offset word.
   The handler pushes it, then `sub word [bp+2],2` rewinds the return IP
   onto the `CD 3F`.
3. ensure-loaded (0x3bed7; DS2 0x405f4): if desc+0x10 != 0, refresh the
   lock (+0x1b = 1, flag +0x1a |= 4); else flag |= 8 (cold load), evict via
   the LRU chain (desc+0x1c), write an ownership backlink into the
   paragraph below the module, and `call near [desc+0x18]` (the reader).
4. Reader (DS1 0x3bd1b, DS2 0x40438): `bx = DGROUP[0x128]` (file handle),
   `AX=0x4200` lseek FROM FILE START to CX:DX = the payload dword
   (absolutized at init by adding DGROUP[0x114:8], the overlay-area file
   base), then AH=0x3F reads of <= 0xFFF0 bytes into consecutive segments;
   total = size + nreloc bytes (code and table read together).
5. Relocation applier (DS1 0x3bd54, DS2 0x40471): cx = nreloc >> 1 entries
   (confirming +0x0a is a byte count); table at `load_seg + (size>>4) :
   size&15`; per entry e: `v = module[e]; module[e] = segtab_word[v & ~7]`,
   segtab byte-indexed at DS1 0x4137 / DS2 0x45e8. So stored values are
   SEGTAB BYTE OFFSETS: record = v>>3, low 3 bits = tag, bit0 = an
   overlay-marker flag.
6. Slow path (DS1 0x3bd99, DS2 0x404b6), entered when bit0 is set:
   pattern-matches `mov r,SEG; push r; mov r,OFF; push r` sequences, then
   rewrites the offset word to the matching stub's address. NEVER FIRES in
   either game: 0 of 8,232/8,262 stored words has bit0 set. All
   overlay-to-overlay references are `9A` far calls whose offset word
   already IS a stub address.
7. Stub patch on activate (DS1 0x3bfa5, DS2 0x406c2): every stub of the
   module is rewritten in place to `EA <entry_off:2> <load_seg:2>` (direct
   far JMP). Page-out (DS1 0x3bfe4, DS2 0x40701) restores
   `CD 3F <entry_off:2> 00` (word 0x3FCD from DGROUP[0x110]).
8. Epilogue: pop the entry offset, read+clear flag bit3, `call far
   [DGROUP:0x86]` hook (ax = 8 cold / 0, es = descriptor), restore, `iret`
   ONTO THE NOW-PATCHED STUB, which far-jumps into the module. Transfer
   happens via patch + iret, which is why the return IP is rewound by 2.

Init (DS1 0x3bbce..0x3bc4d): walks segtab records from DGROUP:0x1a0 while
offset < 0x880, filters `class & 2 and size != 0` (live class-3 records),
writes desc+0x18 (0x4c9/0x4c6) and absolutizes each payload dword. It opens
the EXE by the stored build name ("darkcd.exe"/"dsmall.exe"; name-builder
0x3bb40..0x3bbbd, `open` 0x3bbb6).

## 6. Static resolution procedure

```
E = image_end; A = E + 16                      # overlay area base
segtab = 8-byte records at exeinfo             # (start_para, size, cls, x)
descs  = walk the CD 3F 00 00 chain            # deterministic via class-3 segtab records
ovr_segs = { r.start_para : k } for the k-th class-3 record r
H = MZ header size                             # 0x5400 DS1 / 0x5200 DS2

resolve_far_resident(seg, off):                # far pointer in RESIDENT code (file < E)
    if seg in ovr_segs:                        # targets an overlay stub
        k = ovr_segs[seg]; d = descs[k]
        j = (off - 0x20) // 5                  # must be integral, 0 <= j < d.nstubs
        e = word at (H + seg*16 + off + 2)     # entry_off from the CD 3F-form stub
        return ("overlay", k, entry_cs=e, file=A + d.payload + e)
    return ("resident", file=H + seg*16 + off) # MZ reloc adds the runtime base; file target unaffected

resolve_far_overlay(segword, off):             # far pointer inside an OVERLAY module
    r = segword >> 3                           # segtab record index; bit0 = marker (never set in this corpus)
    tgt = segtab[r]
    if tgt.cls == 3:                           # off already IS a stub address (the only form used)
        k = r - first_class3_index
        return resolve_far_resident(tgt.start_para, off)
    return ("resident", file=H + tgt.start_para*16 + off)
```

Resident-vs-overlay decision for an arbitrary segment value: membership in
`ovr_segs` (58 values DS1: 0x41a6..0x4354; 49 values DS2: 0x465c..0x47dd).

RESOLVED 2026-09-19 (wave 2): the earlier caveat about "module frame"
constants needing an observed capture is DISSOLVED. Every small segment
word observed in overlay code (DS1 `0x4e0:*`, `0x530:*`, `0x4e8:*`,
`0x5a8:*`, `0x5b8:*`, `0x598:*`, `0x600:*`, `0x628:*`; DS2 `0x570:*`,
`0x630:*` and the rest) is an ordinary segtab byte-offset under
`resolve_far_overlay` (record = segword >> 3). Wave 2 located the raw
`9A <off:2> <seg:2>` bytes for 30+ flagged sites and confirmed every
segment word is a member of its module's per-module relocation table;
all stub indices came out integral and in range. The mapping of frame
constants to modules: combat-flow.md section 1 and spell-effects.md
section 1. The ONLY runtime unknown left is the absolute EXE load-base
segment, which cancels in every file-level cross-reference. Note also
that the placeholder constants 0x420 (DS1) / 0x4d0 (DS2) in the rules
code are literally the rules-block segtab records, and GSTATE/MISC/
CSTATE2/STATE are frame constants to their own data records.

## 7. Worked examples (byte-verified)

1. DS1 palette dispatcher (dsun-exe-re.md 3.5): `9A 20 00 BB 41` at file
   0x1cc0f. seg 0x41bb = class-3 record 155 -> overlay id 4; off 0x20 ->
   stub j=0 (file 0x46fd0); entry = word at 0x46fd2 = 0x042e; target =
   0x52eb0 + 0x35e0 + 0x042e = 0x568be. `ovr-map --verify 0x568be`
   independently reports segment 4 / entry / range 0x56490..0x56be0.
2. DS2 load_resource: overlay-side `9A AB 04 28 01` (91 sites). Seg word
   0x0128 = segtab record 37 (class 1, start_para 0x28ff) -> file 0x5200 +
   0x28ff0 + 0x4ab = 0x2e69b, prologue `55 8B EC 39 26 9C 00`. The
   resident-side twin uses the raw form `9A AB 04 FF 28` -> same target.
   (The old syms claims 0x692b and "real prologue 0x6902" are wrong.)
3. DS1 load_resource: overlay-side `9A A4 04 00 01` (96 sites). Seg word
   bytes `00 01` = 0x0100 = segtab record 32 (start_para 0x2460) -> file
   0x5400 + 0x24600 + 0x4a4 = 0x29ea4. The doc's "0001:04a4 = 0x58b4" was
   an endian misread.
4. Overlay-to-overlay (first resolved statically): `9A 61 00 30 05` at file
   0x53dcf (inside module 2, 0x53ba0..0x54bbe). 0x0530 -> record 166
   (class 3) -> overlay id 15; off 0x61 -> stub j=13 at file 0x47571,
   entry cs:0x583 -> target 0x625b3 in module 15 (0x62030..0x6314c).
5. DS1 StartCycle: `0x22f8:0x387` -> not a class-3 segment -> resident,
   file 0x5400 + 0x22f80 + 0x387 = 0x28707 (matches the syms row).
6. Cross-checks: the dispatch-table handler bases (DS1 paragraph 0x43d,
   DS2 0x72c) fall inside class-1 segtab records; nothing in the dispatch
   tables touches overlays. All 7 DS1 and 7 of 8 DS2 overlay syms rows land
   exactly on stub entries; the exception, save_record_writer (18, 0x8e5),
   is 2 bytes off: the stub entry and prologue are at 0x8e3 (file 0x70713).

## 8. Unresolved

- Where DGROUP[0x114:8] (the overlay-file base) is computed at runtime; its
  use is decoded (init DS1 0x3bc1f), its initialization is not traced.
  Statically the math is image_end+16+payload, verified against module
  prologues.
- The IVT install instruction for vector 0x3F: the handler exists, but no
  `mov [0xfc]` / `int 21h/25h` write pattern was found in the resident
  image; the survey's `mov [cs:0x2c4],dx` claim remains unexplained.
- Segtab word3 semantics (small ordinals on class-1 records).
- The DGROUP:[0x86] far-call hook (ax = 0/8 per trap, bx=0xffff in init):
  likely the VMEM/paging notification or a null default; body not identified.
- Resident-set bound / buffer policy details (DGROUP[0x118]..[0x12c]):
  qualitatively decoded (allocations move downward from a high-water
  segment; LRU via desc+0x1c; lock count desc+0x1b; MCB-style backlinks).
- Why DS1's resident code calls load_resource via raw 0x2460:0x4a4 (14
  sites) while the documented 96 counted sites are all overlay-side: same
  target, unreconciled site composition.

Wave 2 addendum: the per-module relocation table sits at
`module_file_start + code_size` directly (the applier's
`(size>>4):(size&15)` form), not at the next 16-byte boundary; and the
DS2 rules-code placeholder 0x5c8 resolves to ovr16, a 1-stub 185-byte
module that is the DATA-chunk table lookup helper (spell-effects.md 1).
