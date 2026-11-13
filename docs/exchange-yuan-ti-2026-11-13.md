# Exchange briefs for yuan-ti (prepared 2026-11-13)

Four briefs for Calvin Rodo's [`yuan-ti`](https://github.com/CalvinRodo/yuan-ti),
prepared after the first cross-read and fingerprint verification
(see [`upstream-projects.md`](upstream-projects.md) §4 and
[`known-bugs.md`](known-bugs.md) §3.6). They are the concrete half
of the offer made in opends issue #13 ("our reassembler round-trips
the corpus byte-identical and we have a DOSBox differential harness").
Intended use: link or paste from the issue thread when the reply
lands; they are written to stand alone. Nothing here has been sent
yet.

## 1. DS2 script decoding: closing the 258/350 gap

Their state: `dsun-exe-reference.md` §5 notes DS2's
`dark_sun_2/data/GPLDATA.GFF` decodes 258/350 chunks, calling DS2 "a
later VM revision with extra opcodes".

What we can hand over: DS2's opcode set is not bigger than DS1's.
Both dispatch tables are 129 entries (0x00-0x80); the difference is
handler addresses and operand depth, not opcode count. Our
[`dispatch-table-ds2.md`](dispatch-table-ds2.md) resolves all 129
handler file addresses for DS2 (base 0xc4c0 / paragraph 0x72c,
confirmed by the interpreter's own MZ relocations), and proves the
15 opcode bytes that never appear in shipped DS2 code share the
single default entry 0x20a2: reserved and unimplemented in the DS2
engine.

Recipe for the gap, in the order we would run it:

1. Map every `??` row their `gpl_parser.py` emits onto our DS2
   table; anything their parser marks unknown that our table names
   is an operand-shape problem, not a missing opcode.
2. Run our disassembler over the same file:
   `gpl-disasm --json <ds2>/GPLDATA.GFF` emits one row per
   instruction for all 350 chunks. Diff their decode against ours
   per chunk; the first divergent address in each failing chunk is
   the desynchronization point.
3. Ground truth per chunk: our `gpl-asm` round-trips DS1+DS2
   `GPLDATA.GFF` byte-identical (600/600 at last count, part of
   `cargo test -p gpl-asm`). A chunk that reassembles
   byte-identical is fully decoded; a chunk that does not has a
   decode bug at the first round-trip mismatch. That test turns
   "258/350" into a per-chunk checklist with a binary signal.

If their parser's operand tables are the blocker, the two tables
worth copying semantics from (both MIT, both credited in our
CREDITS.md) are libgff's `gpl_read_number` expression grammar and
our own `PARAM_COUNTS` derivative of it.

## 2. The region-change machine (their M2 backlog item)

Their backlog (`.github/instructions/dsun-rewrite-roadmap.md` §10,
M2 row) asks: "find the GPL command that sets `DS:117C` and the
region change (`1587:1F83`)". That item is DS1-side; our decompiled
evidence so far is DS2-side, same machine family. What we have that
bears on it:

- DS2's region-change routine is decompiled end to end:
  `gpl_disk_change_region` (DS2 ovr18+0x1132), with the phase
  sequence confirmed by named calls, in
  [`engine-quirks.md`](engine-quirks.md) §6's addendum (commit
  cc93860). It also surfaced an undocumented despawn pump
  (`while head.flags & 8: FUN_31e0_05bb(0,1,0,0)`) worth knowing
  about before trusting region re-entry state.
- The GPL Request path that scripts use to reach engine services is
  pinned end to end for DS2: VM opcode 0x22 dispatch (resident arm
  0xd444 -> stub 0x4787:0x66 -> ovr35+0x169), in
  [`elevator-digs-2026-11-02.md`](elevator-digs-2026-11-02.md) §1,
  with the GPL-287 ride chain (§2) as a worked example of a script
  driving a world service through it.
- DS1's own region-change command (their `DS:117C` target) is still
  unpinned by us too. Our tooling flattens Borland overlays for
  decompilation (`ovr-carve`; workflow in
  [`re-tooling.md`](re-tooling.md)) and maps confirmed function
  entries per overlay (`ovr-map`, 935 DS1 entries); their
  `ovl_unpack.py` produces the equivalent flat image on their side.
  The shortest path to the answer either way: decompile around the
  DS1 dispatcher's region-write site and follow the one writer of
  `DS:117C`. Shared open question; whoever pins it first writes it
  down for both.

## 3. Symbol exchange

Their side: `tools/ghidra/symbols.tsv` holds 586 curated entries
(494 func, 81 data, 11 label, most with C prototypes), applied by
`ExportDecomp.java`; `gen_symbols.py` adds the ~115 GPL handlers
from the DS:00C0 table. Our side: `ovr-map` (Phase 5.5) emits 935
confirmed DS1 function entries from the FBOV segment table, via
`ovr-map --json`, each with its overlay and offset.

Offer: we export our 935 as a `seg:off` table in their TSV's
convention (EXE segments, load segment 0; their
`dsun-exe-reference.md` §1 states the same convention we use) so
both sets merge into one Ghidra naming pass. The union covers
different ground: their list is semantic (names + prototypes from
decompilation), ours is structural (every confirmed entry point,
including the overlays their 58 stubs imply). The GPL handler names
from their `gen_symbols.py` cross-check cleanly against our
[`gpl-opcodes.md`](gpl-opcodes.md) catalogue (same 129 entries,
same libgff ancestry).

Same offer runs to us: their curated function names are the best
public semantic layer over DSUN.EXE and would feed our
`gpl-disasm/syms/functions.toml` curation (today seeded from DSO's
3,530 DS2 symbols, which share the WotR codebase lineage).

## 4. Runtime QA over the repaired sites (offer + checklist)

Our darkfix lane has shipped fixes with no runtime confirmation
yet; their engine runs the same repairs live. A DOSBox session
over the shared sites would confirm both projects' work at once.
Rig notes from our side (the oracle rig in our port-digs docs):
sound ON (MEL DSP detect fails without it), overlay mounts so the
install never takes a write, native screenshots (Ctrl+F5), and
padded AUTOTYPE for hands-off flows.

Per-site checklist, pass criterion in parentheses:

1. Deadtriggers (shipped in darkfix-ds1 0.1.1/0.1.3, on by
   default): the Darkhold wyvern keeps look text (look at the
   creature: text, not silence); the portcullis guard fights when
   attacked; the queen's chamber creatures keep look text.
2. Ranger/linara/gate (shipped 0.1.2/0.1.3): Lava Rifts ranger
   talks once, no duplicate Iron Necklace (approach, leave, return:
   no loop); Linara's menu opens after the extract delivery
   (Jasmine's spellbook topic discussable); the final battle's next
   stage starts after a stage clears inside the time window (no
   permanent strand).
3. Tracking chain (yuan-ti, unconfirmed): a ranger in the party
   reads the region 8 tracks (roll succeeds with plausible
   frequency).
4. Grate hack (yuan-ti, unconfirmed): a weapon in hand offers "hack
   the lock off"; a successful hack opens the grate; attacking it
   breaks the lock on a Strength-sized roll, not always.
5. Mindhome XP (yuan-ti, unconfirmed): talk to the leader twice
   after the spiders die; +5000 XP once.
6. Messenger (yuan-ti, unconfirmed; our triage site): stay in
   region 9 through the elves' departure; the messenger arrives
   without a re-entry.
7. Serf (yuan-ti, balance-class, their default off): with the fix
   enabled, a serf left >14 cells behind still follows to region 10
   (and no second obelisk gem).
8. Legcrusher guards (yuan-ti, dialog-inventing): kill Legcrusher,
   then talk to Kurzak and Dinos; substitute lines play, no lines
   address him as present.

Our side owes the same pass over our shipped rows (items 1-2);
their engine makes items 3-8 observable without any patch file at
all, which is the neat part. Results from either side feed both:
whatever a session confirms goes into our known-bugs rows as the
runtime column, and their `GplRepairs.cs` what-lines get confirmed
or corrected.
