# The GPL virtual machine: execution model and semantics

The machine-readable spec of SSI's GPL interpreter, read from
handler code in both `DSUN.EXE` binaries (wave 3 of the mining
campaign, 2026-09-16). This is the document a reimplementation
implements: the encoding side lives in
[`gpl-bytecode.md`](gpl-bytecode.md), the opcode NAME table in
[`gpl-opcodes.md`](gpl-opcodes.md), the resolved handler
addresses in [`dispatch-table-ds1.md`](dispatch-table-ds1.md) /
[`dispatch-table-ds2.md`](dispatch-table-ds2.md).

Headline: **the two games ship one VM.** Every structure below
has identical offsets in DS1 and DS2; every handler read in both
binaries matched instruction-for-instruction except addresses.
DS1 segment constants: VM state 0x3781, VM config 0x377c, DGROUP
file base 0x48960, code file base 0x97d0. DS2: 0x3c13, 0x3c0e,
0x4d000, 0xc4c0. Confidence marks as in
[`object-formats.md`](object-formats.md) (VB read on bytes /
instruction, H hypothesis).

## 1. The interpreter loop

Entry: `RunGplScript(chunk_id, entry_offset, type)` (DS1 code
0x97d1, DS2 0xc4cc), Pascal-style args; type 1 = `GPL ` chunks,
2 = `MAS ` chunks (libgff's `MASFILE` / `GLOBAL_MAS` enum is
engine-real). The bootstrap invocation in both engines is
`(99, 0, 2)`: MAS chunk 99, entry 0, the global master script.
Nine resident far-call sites re-enter it per game (event/UI
record walkers), plus overlay callers through the INT 3Fh stub
fields (DS1 stub segment 0x4251, DS2 0x4702; the two stub
tables are order-identical: Continue is stub 0x20 in both).

Loop: push the (chunk, entry, type) context unless chunk_id = 0
(CORRECTED 2026-10-07, port-digs-2026-10-07.md 3: chunk 0 is not
a resume; the branch skips the context push on a just-wiped state
and returns without executing a single opcode, a reset/no-run
service. The complete caller inventory finds nine resident far
callers of run_gpl_script plus the ovr0 session-init, none
passing 0; every run is synchronous inside RunGplScript's frame,
fetch-dispatch until the stop flag is set or the call ring
unwinds below its entry depth).

Fetch: IP comes from a 50-slot ring of chunk-relative offsets
(the call stack); the byte is `arena[chunk_data_ptr + ring_ip]`;
the advance helper bounds-checks against the ARENA capacity and
the chunk loader writes a `0x31` (ExitGpl) sentinel byte at
`data_ptr + chunk_size`, so running off a chunk's end executes
ExitGpl: termination is by construction, not by length checks.

Dispatch: `if opcode > 0x80: illegal handler` (DS1 0x264c, DS2
0x20a2: the 15 unimplemented bytes); then a per-opcode TRACE
HOOK in both games (`call far [ptr]` guarded by a null check;
DS1 pointer cell DGROUP:0xac, DS2 DGROUP:0x2f6, called with the
opcode); then `shl ax,1; call near [bx+table]` (DS1 table
DGROUP:0xc0, DS2 DGROUP:0x30a: the resolved tables). Handlers
return void; control flow works by side effect on the ring IP.

## 2. The VM state segment

One far segment holds everything; offsets identical in both
games (VB):

| Offset | Size | Meaning |
|---|---|---|
| 0x000..0x03b | 13 far ptrs | GNAME pseudo-array slots (n = 0x20..0x2e; RESOLVED 2026-10-07, port-digs-2026-10-07.md 4: file-backed and MZ-relocated in both games, 13/13 reloc targets, NOT runtime-initialized. GNAME[32..36] point at GSTATE mode/x-tile/y-tile/aux/region, [37..44] at the six current-object registers 0x369/0x367/0x365/0x363/0x361/0x35f, [41]/[42] at the time counter 0x35b and party money 0x357; so GNAME reads are engine-cell reads and their "producers" are the writers of those cells, all enumerated) |
| 0x034/0x074 | 0x40 each | the two RETVAL param-block save slots |
| 0x0b4..0x0d3 | 8 dwords | parameter registers P0..P7 (expression results) |
| 0x0d4..0x0f3 | 8 far ptrs | per-param result sinks (defaults to &accum) |
| 0x104..0x10b | 8 bytes | compare-chain case-matched marks |
| 0x171..0x190 | 32 bytes | if-nesting truth bytes |
| 0x193 | word | active chunk's arena offset |
| 0x195/0x197 | words | active chunk type / id (CORRECTED 2026-10-07, port-digs-2026-10-07.md 4: the SetContext tail writes [0x197] = chunk id and [0x195] = type; the old row had the roles swapped. Type 1 loads 'GPL ', type 2 loads 'MAS ') |
| 0x199..0x1b8 | 16 words | GlobalSub type stack |
| 0x1b9..0x248 | cache tables | 16-slot chunk cache: id key, type key, end ptr, data ptr, LRU age |
| 0x24d:0x24f | far ptr | expression result sink |
| 0x255:0x257 | far ptr | the chunk arena base |
| 0x25d..0x27c | 16 words | GlobalSub chunk-id stack |
| 0x295..0x2f8 | 50 words | the IP ring (the call stack) |
| 0x313 | dword | arena capacity |
| 0x31b | dword | **ACCUM** (the accumulator; RETVAL result channel) |
| 0x325/0x326/0x327 | bytes | flag / STOP flag / context depth |
| 0x32a/0x32b | bytes | last-opcode latch / trace flag |
| 0x32f..0x34e | 8 far ptrs | locals then globals: LSTR, LBIGNUM, LNUM, LFLAG (0x33b), GSTR, GBIGNUM, GNUM (0x347), GFLAG (0x34b) |

Config segment: +3 if-depth, +4 compare-depth, +9 in-script
flag, +0xb state gate, +0x10 RETVAL depth (limit 2), +0x12/0x14
current-chunk fast-path key.

Note the correction to `engine-quirks.md` section 7's prose: the
pointer cell at VM:0x33b is **LFLAG**, not GFLAG; GFLAG's cell
is **VM:0x34b** (both games' resolver handlers read [es:0x34b]).
That section's conclusion (the EXE never reads individual GF
flags) is unaffected.

### Variable storage (allocated once at VM start; freed at shutdown)

| Array | Alloc | Capacity |
|---|---|---|
| GFLAG | 101 bytes | 808 bit flags (byte n/8, bit n%8) |
| GNUM | 400 bytes | 200 signed words |
| GBIGNUM | 80 bytes | 20 dwords |
| GSTR | 420 bytes | 10 strings x 42-byte records |

Locals are a FRESH HEAP ALLOCATION per chunk load (zeroed;
freed at chunk unload), not a stack: LFLAG 9 B (72 flags),
LNUM 64 B (32 words), LBIGNUM 40 B (10 dwords), LSTR 420 B
(10 x 42), plus an 8-slot compare stack and a 300-byte string
work buffer.

Simple-variable kinds implemented by the resolver: LSTR(1),
LNUM(2), LBIGNUM(5), GSTR(6), GNUM(7), GNAME(9), GBIGNUM(0x0a),
GFLAG(0x0d), LFLAG(0x0e). LBYTE/LNAME/GBYTE have NO storage:
reads fall through to a stale tag cell and writes are silently
discarded. Strings are assigned with opcode 0x0A StringCopy.

"GF[N]" bracket addressing is not special: the variable operand
dispatch is `0x80 | kind` (or 0x40 extra when the index needs
two bytes), varnum 1-2 bytes big-endian; the resolver converts
n to (byte n/8, bit n%8) with signed division and DGROUP
set/clear mask tables (DS1 0xb0/0xb8, DS2 0x2fa/0x302).
GNAME[N] dereferences the pseudo-array pointer slot (values
outside 0x20..0x2e force 9999 then fatal).

## 3. The expression evaluator

One function serves every operand read (DS1 seg 0x398f, DS2
0x3278); `get_params(n)` (DS1 0x3daa, DS2 0x367b) loops it into
the P0..P7 value + sink registers. Algorithm (identical both
games, VB):

```
accums[8], opstack[8]; depth = 0
result sink defaults to &ACCUM
loop:
  b = fetch()
  b < 0x80   : 16-bit literal, big-endian pair, sign-extended
  0x80..0xAF : typed operand via table:
      0x80 ACCM        operand = accum
      0x81..0x8A,0x8D,0x8E  variable kinds: resolve kind|b&0x7F
      0x8B IMMED_BIGNUM  sign-16<<16 | uns16 (big-endian)
      0x8C RETVAL        save params, execute one fetched opcode
                         through the MAIN dispatch table, restore,
                         operand = accum
      0x8F IMMED_BYTE    sign-extended byte
      0x90 IMMED_WORD    sign-extended big-endian word
      0x91 IMMED_NAME    -(int16)word   (the NAME(-N) object ids)
      0x92 IMMED_STRING  value 0; result sink -> decoded string buffer
      0xB1 COMPLEX       structured access (read_complex)
  0xD1..0xDF : push operator, continue (no operand consumed)
  0xE1 ')'   : operand = accums[depth--] (underflow fatal)
  0xE2 '('   : push frame (depth >= 8 fatal)
apply: accums[depth] = accums[depth] OP operand when an operator
is pending, else accums[depth] = operand; clear pending op
continue while the peeked next byte is an operator, or a ')'
with depth > 0
result = accums[0], 32-bit
```

Operators, left-to-right, NO precedence beyond parentheses, all
32-bit signed (VB; identical to gpl-disasm's `Op::from_byte`):

| byte | op | byte | op |
|---|---|---|---|
| 0xD1 | + | 0xD9 | > (0/1) |
| 0xD2 | - | 0xDA | < (0/1) |
| 0xD3 | * | 0xDB | >= (0/1) |
| 0xD4 | / (idiv; /0 faults) | 0xDC | <= (0/1) |
| 0xD5 | logical and (0/1) | 0xDD | & |
| 0xD6 | logical or (0/1) | 0xDE | \| |
| 0xD7 | == (0/1) | 0xDF | & ~ (and-not) |
| 0xD8 | != (0/1) | | |

## 4. Opcode semantics (the decoded families)

`P[i]` = param i value; `&P[i]` = its result-sink address; A =
accum. Assign-family operand order is CONFIRMED: param 0 is the
target lvalue (its sink; a non-variable target silently writes
the accum), param 1 the source. All VB unless noted.

Assign / arithmetic (widths enforced by the handlers):

| op | semantics |
|---|---|
| 0x76/0x77 byte += -= | 8-bit wraparound on the target cell |
| 0x78/0x79 byte *= /= | imul/idiv, truncate to 8 bits; /0 faults |
| 0x7a..0x7d word += -= *= /= | 16-bit |
| 0x7e/0x7f long += -=, 0x01 long /=, 0x11 long *= | 32-bit |
| 0x02..0x04 byte/word/long dec; 0x05..0x07 inc | decrement/increment the target cell |
| 0x18 LoadAccum | A = eval() |
| 0x16 LoadVariable | A = eval(); store: datatype byte (bit 6 = extended varnum, big-endian), kinds >= 0x10 route to the complex-write path; flags set/clear by bit masks; other simple kinds no-op |
| 0x0E ToggleAccum | A = (A == 0) ? 1 : 0 |
| 0x00 Zero | stop-flag machine: terminates the current execution (helper sets VM:0x326; loop-level effect H) |

The compare machine (a switch statement over a 7-deep chain):

| op | semantics |
|---|---|
| 0x17 Compare | A = eval(); push onto the compare stack, clear case mark |
| 0x27 Ifcompare v, T | if compare-stack top != v jump T; else set the case-matched mark |
| 0x29 Orelse T | if the mark is set, jump T (skip remaining cases) |
| 0x61 Cmpend | pop the compare depth |

Branches: `If T` saves the truth byte and jumps to T when the
accum is zero; `Else T` jumps to T when the saved truth byte is
nonzero; `Endif` pops the if-depth (limit 32); `While T` /
`Wend` are If and unconditional Jump (Wend == Jump, confirming
the DSO alias); `Jump T` sets the ring IP absolutely.

Calls:

| op | semantics |
|---|---|
| 0x13 LocalSub | ring-push the entry offset (same chunk; max 50 activations, overflow far-aborts) |
| 0x15 LocalRet | ring-pop |
| 0x14 GlobalSub chunk, entry | push context, SetContext (16-slot LRU chunk arena; may evict), ring-push (depth limit 16 by construction, no guard: latent overflow) |
| 0x19 GlobalRet | pop context; at depth 0 sets the STOP flag (ends the run) |
| 0x31 ExitGpl | sets the STOP flag; nothing else (state reset lazily on next RunGplScript) |

Value-producing engine calls:

| op | semantics |
|---|---|
| 0x52 Rand N | r = RNG(); A = (r * (N+1)) / 32768 (RESOLVED 2026-09-19: `far 0:0x822` is an MZ-relocated call to Borland rand() at file 0x5c22 DS1 / 0x5a22 DS2: seed = seed*0x15A4E35 + 1; return (seed >> 16) & 0x7FFF. Range 0..32767 inclusive, so `gpl rand N` yields 0..N inclusive, N+1 outcomes. CORRECTED 2026-10-07: srand has THREE relocation-validated callers, all `srand(time(NULL))` (DS1 ovr13+1071; DS2 ovr11+1309, ovr35+30), so the stream is wall-clock seeded on those paths, not deterministic from 0) |
| 0x20 Bitsnoop a, b | A = ((a & b) == b) (all bits of b set in a) |
| 0x1E/0x1F Nametonum/Numtoname | A = -eval() (byte-identical pair; NAME(-N) conversion) |
| 0x0F Getstatus v | A = engine_call(v) |
| 0x09 Getxy v | engine_call writes the x/y tile words (CORRECTED 2026-09-19: the service, DS2 0x1d40:0x6e6 = file 0x22ce6, writes GSTATE cells 0x3c10:0x1b/0x1d/0x1f, not GNAME slots; the Fight handler's pushed [VMCFG+0x1b/0x1d] words are those GSTATE cells) (accum untouched) |
| 0x80 GetRange a, b | A = engine_call(a, b) |
| 0x0C Changemoney v | engine money service |
| 0x3D Readorders S | reads the in-flight request-table slot S into the accum (RETVAL-safe for this reason) |
| 0x62 Wait N / 0x32 Fetch | enqueue a UI/dialog request; Wait pumps a modal dialog (the cooperative scheduler runs inside that overlay, not in the VM) |
| 0x30 Passtime N | adds N*60 seconds to the 32-bit game clock at VM:0x35b (RESOLVED 2026-10-07, port-digs-2026-10-07.md 3: the body was readable all along through the segtab, DS2 stub 11 of ovr26 / DS1 stub 11 of ovr30: five instructions, `ax = N*60; add dword [es:0x35b],eax; retf`. The clock cell is inside the VM state segment; reset to 0 at session init, +60 per combat round init, saved by the save module) |
| 0x2B Continue | bare overlay stub call (stub 0x20 in both games) |

The debug family is confirmed residue in the retail build: 0x23
SourceTrace (consumes a string), 0x28 TraceVar (2 evals + a
string), 0x2E SourceLineNum (1 eval), 0x4B LocalSubTrace (3
params) all just set the trace flag VM:0x32b and consume their
operands; a filter function executes them transparently before
expression reads, which is why they can appear anywhere in a
stream. 0x0D Setvar is not a bytecode opcode at all: it is a
console/cheat loop over the debug-input service.

## 5. RETVAL context

Token 0x8C (GPL_RETVAL) inside an expression: save the 0x40-byte
param block to one of TWO save slots (nesting limit 2: libgff's
"double paren"), execute one fetched opcode through the main
dispatch table, restore the param block, and take the accum as
the operand value. The engine enforces nothing beyond the depth
limit; libgff's "safe in RETVAL context" whitelist is a static-
analysis safety net for opcodes that produce no accum value.

## 6. Divergences and the question ledger

DS1 vs DS2 semantics: NO divergence found anywhere in the VM
(tables, evaluator, handlers, allocation sizes, limits). All
differences are addresses, plus DS1's dispatcher having an extra
`mov bx,ax`, and both games carrying the per-opcode trace hook at
different DGROUP cells.

The 2026-10-07 closure pass (port-digs-2026-10-07.md 3 and 4)
drove every remaining question in this section to a verdict; the
section title is now historical. The eight "honest gaps" of the
wave-3 era, as they closed: the raw RNG range behind Rand
(Borland LCG, 0..32767, `gpl rand N` = 0..N inclusive; the srand
correction is in the 0x52 row); the complex-variable grammar
(RESOLVED as section 7's 0xB1 subsection: the grammar is VB in
both games, only the runtime-built field numbering remains a
capture question); GNAME producers (none exist; the slots are
static file-backed pointers, section 2's corrected row); the
string reader's sub-types (RESOLVED 2026-09-19, the 0x2C Log
row); when the second stream selector switches (pure fast-path
key mismatch, two write sites per game, section 2's corrected
0x195/0x197 row); Passtime's and Continue's overlay bodies (the
0x30 row and port-digs-2026-10-07.md 3: clock add and
press-any-key pump); whether any overlay writes the stop flag
directly (no: four resident direct writers, overlays stop the VM
through the resident setter, some printing "BAD GPL EXIT"); and
the resume path's caller (there is none: chunk 0 is a state
reset that executes nothing, every run is synchronous inside
RunGplScript's frame, and the complete caller inventory is in
the dig).

## 7. World-interaction, UI, and string opcodes (wave 4)

The rest of the table, same conventions. `stub N` = overlay stub
in the stub segment (DS1 0x4251 / DS2 0x4702, order-identical
tables); engine-service segments DS1 0x1a0a / DS2 0x1d40.
Selectors seen across the family: 0x7FFE = whole party (the
engine iterates the four 49-byte party records), 0x7FFF = no-op/
self, negative = object-group enumeration, 32766 = the party
selector in Tport.

World-object ops:

| op | semantics |
|---|---|
| 0x22 Request code, obj, arg2, arg3 | dispatches into an overlay-local table: DS1 bounds 20 codes, DS2 bounds 53. P1 is the object selector, P2/P3 dword args, result to accum. The full per-code map is in the wave-4 ledger (roadmap); highlights: 1/4 rest (with the NO RESTING DURING COMBAT strings), 5 activate, 9 set state (also rewrites the visible-object record owner), 17 coordinate-place, 37 elevator-operate (3-case), 39 = a literal byte write to the elevator-state cell in overlay data, 49 set quantity; DS2 arms 5/18/22/23/24/40/41/49 apply per-object applier services (CORRECTED 2026-10-07, port-digs-2026-10-07.md 4: the old arm list named 32 instead of 41 and omitted 5; the "resident function pointers" are overlay-stub pointers through module 35's per-module relocations, eight module-35 stubs plus a ninth module-32 service on arm 53; arms 31/32 call genuinely resident bit-set/clear functions on the per-chunk flag matrix) |
| 0x25 Clone obj, count, a, b, c, d | clones `count` copies; accum = success count |
| 0x5E Tport a, b, c, d, flag | a == 32766: party teleport via stub 0xac(b, c, d); a < 0: enumerate the group and stub 0xa7 per handle; else single stub 0xa7(a, b, c, d, 0, flag). Limbo is region 255 |
| 0x32 Fetch / 0x08 Hunt / 0x37 Follow / 0x3A Go / 0x3C Goxy / 0x36 Flee | all enqueue movement/orders through the same dialog-module service with per-opcode kind codes (Fetch 0x0A, Follow 0x0B, Go 0x0D, Goxy 0x0F, Hunt 0x12, Flee 1) |
| 0x33 Search target, fA, fB, {quals...} | the query engine: iterate target (party via 32766, group via negative, single otherwise); per object resolve field selectors through the engine field resolver; per-entry type byte picks an aggregate: 0 min, 1 max, 2/3 sum, 4/5/6 or; types 4..6 also parse a conditional operand. DS1 has 5 conditional operator forms, DS2 10 (the one other semantic divergence besides Request) |
| 0x40 Setrecord | mode 0: complex write, then re-write walking the party; negative mode: write to consecutive handles; mode > 0x8000: single complex write |
| 0x41 Setother v | sets the OTHER-object register (VM:0x361; NAME(-N) resolved via the engine resolver); accum 1 on success |
| 0x49 Setthing a, b | engine pair-setter; accum = (result != 9999) |
| 0x47 Lockdoor | sets the VM flag byte 0x325; nothing else |
| 0x34 Getparty | party enumerator (seed 9999 = first); also sets the VM:0x363 register |
| 0x45/0x46 Join/Leaveparty | stubs 0x2f / 0x34 |
| 0x1A Nextto a, b | engine distance <= 1 |
| 0x35 Fight | enters combat at the precomputed tile (the GSTATE words the Getxy service writes) |
| 0x24 Shop | stub 0x98 |
| 0x21 Award who, amount | 0x7FFE awards the FULL amount to EACH party member (no split); 0x7FFF no-op |
| 0x39 Give / 0x5C Take / 0x2F Drop | inventory transfer stubs; Take with 0x7FFE sums across the party up to the count; Drop retries per member while unsuccessful |
| 0x0B PDamage / 0x2D Damage who, n | NO dice evaluation in the VM: n is passed as a plain value to the combat stubs (0x3e / 0x39); dice live overlay-side or in the caller's expressions |

UI and strings:

| op | semantics |
|---|---|
| 0x48 Menu | title string, then up to 24 entries of (label, jump-target expression, enable expression); terminator byte 0x4A; asks until a valid pick; CORRECTED 2026-10-07 (port-digs-2026-10-07.md 3): the chosen entry's target expression is evaluated at parse time (stored to VM:0x27d+2i) and on selection is RING-PUSHED LocalSub-style (through the same helper LocalSub uses; cursor VM:0x192, value at VM:0x295+2*cursor), so execution continues at that offset; the accumulator is NOT written (the old "accum = the chosen entry's target" was wrong in mechanism). An invalid pick re-invokes the UI stub without a re-parse; the label/enable arrays are never cleaned, just overwritten by the next Menu |
| 0x38 Getyn | yes/no prompt; accum = answer |
| 0x42 InputString | up to 40 chars into the variable's result sink (no-op when the sink is the accum) |
| 0x43/0x44 InputNumber/Money | numeric inputs into the sink |
| 0x2C Log | decode packed string, display via stub 0x89 (sub-types RESOLVED 2026-09-19: 5 = the 16-bit-window codec with output sanitized to 0x20..0x7e (control codes render as spaces) and the 0x03 terminator replaced by NUL, cap 299 bytes; 2 = uncompressed with each payload byte ROTATED LEFT 2 bits, terminator = stored 0xC0; 1 = INTRODUCE: appends the current combatant's name (combat_array[idx]+0x28 of VM:0x369) into the sink) |
| 0x4F/0x50/0x51 prints | style + text (0x4F passes the SINK pointer, not the value); 0x51 newline |
| 0x2A/0x54 Clearpic/Showpic | picture slot management; id space overlay-side |
| 0x5D/0x5F Sound/Music | one word argument to the audio services (DS1 0x1a0a:0x663/0x672, DS2 0x1d40:0xb00/0xb0f) |
| 0x58/0x59 Skillroll/Statroll who, a, b | overlay dice; 0x7FFE = any party member succeeds |
| 0x0A StringCopy dst, src | copies between the two result sinks (string variables) |
| 0x5A StringCompare a, b | equality 0/1 (0 if either operand is the accum) |
| 0x5B MatchString a, b | pattern match between the two operand strings; no third pool involved |

### The complex-variable grammar (0xB1)

`access_complex := base_selector, count:byte, field_id:byte x count`.
The base selector is an expression: values < 0x8000 are NAME ids
(negated, resolved to handles); `0x8000 | k` selects one of six
current-object registers (VM words 0x369/0x367/0x365/0x363/
0x361/0x35f; 0x363 is written by Getparty, 0x361 by Setother).
Each field id walks one structure deeper (chained). The walk
resolves through runtime-built tables: a 3-byte-per-object
region/struct table, per-region record-array bases and strides,
a field-offset table holding **198 fields per structure group**,
a datatype table (widths 1/2/4; datatype >= 0x80 returns a far
pointer, so string fields redirect the expression sink exactly
like IMMED_STRING). All those tables are BSS on disk: the
concrete field numbering is runtime-initialized and remains a
runtime-capture question; the grammar itself is VB in both games.

### Divergences (wave 4, completing section 6)

Exactly two semantic divergences exist in the VM: the Request
code space (20 DS1 vs 53 DS2 codes, renumbered) and the Search
conditional-operator count (5 vs 10). Everything else, including
the stub offsets for shared services, is identical modulo
addresses.

Wave-4 question ledger, all closed 2026-10-07
(port-digs-2026-10-07.md 3 and 4): the DS2 request arms' eight
applier services (resolved: eight module-35 stubs plus the
module-32 arm-53 service, see the 0x22 row); the runtime
field-table initializers (closed as runtime-built, the 0xB1
subsection's standing disposition); producers of four of the six
current-object registers (resolved: all six enumerated, port-digs
section 4); the Skillroll/Statroll/Damage dice bodies (resolved:
Skillroll = rand()%100 vs rating+adj, Statroll = d20 0..19 with
natural-19 auto-fail and target>roll, Damage passes the plain
value through, no VM dice, see the dig for tables and strides);
Log string sub-types 2 and 5 (resolved 2026-09-19, the 0x2C
row); the Menu post-selection tail (resolved: ring push, the
0x48 row).
