# The mines-elevator night dig (2026-11-02): the Request machinery and the ride chain, pinned

Overnight autonomous session (Brandon directive: research, judge,
document, push). Method: the carved DS2 image
(`scratch/rea-bridge/DSUN-ds2-ovrflat.exe`, ovr-carve 0.1.0) under
the REA decompile corpus (`scratch/rea-bridge/decomp-ds2*/`), plus
`ovr-map --disasm 35` (ndisasm, entry-labelled) for the module the
decompiler had not reached, plus `gpl-disasm --kind GPL --id 287`
for the script side. Ghidra linear addresses are
`0x10000 + file_offset - 0x5200`. Nothing below is a verdict; the
played-save pair (capture-sessions.md card B) remains the
arbiter. All new facts are script/EXE static observations.

## 1. The Request dispatch, end to end (was "arms not pinned")

The VM opcode 0x22 handler (dispatch-table-ds2.md row `0x22 ->
0xd444`) is a thin arm: it fetches the four VM operands and makes
one overlay far call, `0x4787:0x66`. Under the docs/overlay-formats.md
section 6 resolution that is stub site 0x4cad6 (class-3 block,
start_para 0x4787, stub j=14), whose entry field reads 0x169:
**the Request dispatcher is ovr35 + 0x169** (file 0x8bf29), the
very module the 2026-10-07 correction named for the arm stubs.

The dispatcher (ovr35 disassembly, `scratch/rea-bridge/ovr35-disasm.txt`):

    cs:0x17b  bx = code - 1
    cs:0x17f  cmp bx, 0x34          ; bounds 1..0x35 = 1..53 (the DS2 bound)
    cs:0x189  jmp word near [cs:bx+0x6c7]   ; jump table at cs:0x6c7

Arm targets read from the table (file 0x8bdc0 + 0x6c7 + (code-1)*2):

- **arm 37** (elevator-operate) = cs:0x657, three cases on the two
  dword args, matching gpl-vm.md's "3-case":
  - `(arg2, arg3) == (0, 0)`: `call cs:0x284d` (state query service).
  - `(1, 0)`: `mov byte [cs:0x14e5], 1` (elevator-state byte) then a
    far call through segtab record 11 (start_para 0xbf3, the main
    resident code record) offset 0x4feb = **FUN_1bf3_4feb** (linear
    0x20f1b): the region map draw with the "Too heavy a load to
    carry" prompt and VGA blit loops, i.e. the loading-screen visual.
  - `arg3 == 1`: `push 1; call cs:0x1d2e` (the ride service, section 3).
- **arm 38** (state query) = cs:0x6a0: reads bytes 0x14e4/0x14e3,
  returns di = 0/1/2.
- **arm 39** = cs:0x3e3: the literal byte write to the elevator-state
  cell, as documented.

**No tport exists anywhere in the native arms.** The party's
movement is GPL-layer, confirming the pre-decided fix shape's
premise (engine-quirks.md 6) at the native side.

## 2. The ride chain in GPL-287 (full control flow)

From `gpl-disasm --kind GPL --id 287` (`scratch/rea-bridge/gpl287.txt`):

- **switch bank, entry 0xea9** (the `usetrigger 3753, 287,
  NAME(-5807)` handler): compares OTHER against NAME(-5807)..
  (-581x) and toggles GF[647]..GF[65x] with sound pairs
  (35+40 on, 41+30 off). Purely the switch bank; no ride, no tport.
- **call pads, entries 0x39d and 0x46b** (the east 0x3f8 / west
  0x494 sites engine-quirks names): set GNUM[139] (destination
  floor) and GNUM[140] (tick timer).
- **tick entry, label_0x0530**: while GNUM[140] != 0 it counts down
  (`word dec`, sound 200 at tick 4, `exit gpl`); on expiry:
  sound 115, `noorderstrigger 1598, 287, GNAME[38]`,
  `request 37, GNAME[39], 0, 0`, then a GF[640]/GF[639] gate with
  cart repositioning (`request 9` loops for NAME(-360)/(-288)/(-289)),
  then `local sub entry_0x086e` — the floor dispatch fanning out to
  the 14 floor handlers, each ending in
  `tport 32766, 57, x, y` (party, region 57, per-floor coordinates;
  tports at cs 0x963, 0x9ab, 0xa0c, 0xa6d, 0xac6, 0xb08, 0xb3e,
  0xb61, 0xb8a, 0xbb3, 0xbea, 0xc10, 0xc33, 0xc75).
- **pickup/noorders entry, label_0x063e**: cleanup trigger, then
  `request 33, GNAME[39], GBN[14], GBN[15]`, then the gate
  `GF[639] == 1 && get-range(GNAME[37], NAME(-5851)) < 15` ->
  **`request 37, GNAME[39], 0, 1`** (the ride service, next
  section) plus `noorderstrigger 1783, 287, GNAME[40]` and further
  staging. The pickup fires when the arrived car finds a party
  member within distance 15.

## 3. The ride service (arm 37 case 3): the pickup's native half

ovr35 entry[13], cs:0x1d2e (file 0x8daee):

    mov byte [cs:0x14e5], 0          ; clear the elevator-state byte
    ...
    push <buffer>; push word [0x140c]        ; THE CURRENT REGION ID
    push dword 0x204c4150                    ; 'PAL '
    call word 0x128:word 0x4ab               ; load_resource("PAL ", region, buf)

That `0x128:0x4ab` is the canonical load_resource raw form
(docs/overlay-formats.md worked example 2; target = resident
0x2e69b, verified). The body continues into a long staging loop
(sound service calls with `0x5a - state*10` arguments at cs:0x1d82+).

**The ride's pickup performs resource I/O on the current region's
palette.** This is a new, concrete tie between the ride path and the
resource machinery the freeze window lives in
(gpl_disk_change_region's DARKRUN close/reopen cycle runs in the
same window). It is a lead, not a finding: whether the PAL load and
the transition machinery can overlap badly is exactly what the
capture decides.

## 4. The despawn pump's feed

The pump (docs/engine-quirks.md 6 addendum: `while (head.flags & 8)
FUN_31e0_05bb(0,1,0,0)`) now has its writer:

- **FUN_9000_4042** (linear 0x94042, file 0x89242 = **ovr31 + 0xe2**,
  a stub entry): walks the 8-byte record chain, negates each linked
  record's +6 owner word, sets `flags |= 8`, and increments
  DAT_57e0_264e (the count). This is "mark records for
  despawn-on-region-change" - the exact flag the pump consumes.
- **FUN_7000_6381** (ovr18, linear 0x76381): writes
  `record[i].flags = FUN_2d40_2ec2() + 8` on the same array, in code
  near the `WGAME` menu string.
- FUN_289b_0094 (the unlink/compact helper the pump's despawn calls)
  has a sibling call site in FUN_376df (linear 0x376df) with the same
  trailing flag-zero shape.

Callers of ovr31+0xe2 are unresolved: the far-call callgraph
(`ovr-map --callgraph`, 216 edges, 14.2% direct-stub coverage) has
no edge into it, so the marker is reached indirectly (table dispatch
or FF /2). Open thread: resolve callers over the completed decompile
corpus, now that the marker is a stub entry the corpus can be
searched for.

## 5. Effect on the candidate list, and the capture's breakpoint list

Nothing here is a verdict. The state of play:

- Candidate B (GPL-layer, the ride waits on a transition nothing
  initiates) now has its full actor chain written down: switch bank,
  pads, tick, floor dispatch, pickup gate, ride service.
- The pickup's `load_resource("PAL ", region)` ties the ride to the
  resource-I/O machinery; whether that call can land inside the
  transition window (or block there) is a capture-shaped question.
- The despawn pump remains the only concrete unbounded loop on the
  change-region path, and its feed now has a name.

Route 2 (DOSBox debugger) breakpoint list, in addition to the
existing write-watchpoint on `DGROUP:0x6874+(id-5)*37+0x16`:

1. the pump loop inside gpl_disk_change_region (linear ~0x7bd70,
   after the save pair call in the 0x7bd62 body);
2. ovr35 ride service entry (stub 0x4787:0x66 -> ovr35 0x1d2e);
3. load_resource entry (resident file 0x2e69b);
4. FUN_9000_4042 (ovr31 + 0xe2).

Artifacts (scratch, gitignored): `ovr35-disasm.txt`,
`gpl287.txt`, `callgraph-ds2.txt`, `decomp-ds2*/`.
