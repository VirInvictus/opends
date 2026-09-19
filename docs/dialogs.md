# Dialogs and text: machinery, corpus, and the conversion shape

The conversational layer (wave 4 of the mining campaign,
2026-09-16). The working tool is `tools/dialog-extract` 0.7.1;
this document records what it produces, the full-corpus census,
and what a Godot dialog system takes from it.

## 1. The machinery

Dialogs ARE GPL chunks: every conversation is bytecode in
GPLDATA.GFF, and every string lives either inline (the 7-bit
packed-string codec: 16-bit sliding window, 0x03 terminator,
sub-type markers 1 introduce / 2 uncompressed / 5 compressed,
lossless since gpl-disasm 0.4.3) or as a reference:

- **GSTR[id]** resolves directly against a TEXT chunk (0
  unresolved corpus-wide).
- **LSTR[slot]** is one of 10 runtime slots written by
  `gpl string copy`; the table is GLOBAL across `global sub`
  calls (callers populate callee slots), which is the one
  genuinely hard resolution problem.

String-bearing opcodes: 0x2C log, 0x42 input string, 0x48 menu,
0x4F print string, 0x5A string compare, 0x0A string copy.
`gpl menu` (0x48) is the choice machine: a title, up to 24
entries of (label, same-chunk jump target, availability flag),
byte 0x4A terminates; the first entry carries the INTRODUCE
intro marker; availability flags are usually `LF[n]` (asked-once
gating; polarity unconfirmed) or literal 1 (always-on goodbye).

dialog-extract resolves strings in three tiers (last-write-wins
snapshot; a path-aware CFG walk per entry point; then
`possible_writers` arrays ranked by reverse-callgraph BFS
distance for the remainder) and builds a node graph per chunk:
entry points (chunk start + local subs + discovered block
leaders) -> block nodes (lines, gpl refs, terminator) with
if/ifcompare/loop/goto/cross-chunk children preserving the
GPL condition semantics. Speakers are tracked via
setother/setthing state and the curated `syms/speakers.toml`;
attribution is never invented.

## 2. The corpus (both games, full runs)

| Metric | DS1 | DS2 |
|---|---|---|
| String-bearing chunks (of total) | 215 of 250 | 316 of 350 |
| Aligned (full CFG) | 215/215 | 316/316 |
| Strings total | 17,699 | 28,354 |
| Decoded characters | 642,269 | 1,070,025 |
| Inline / GSTR / LSTR | 13,930 / 3,514 / 255 | 22,428 / 5,827 / 99 |
| Unresolved LSTR reads | 25 (all computed-writer sites) | 7 |
| Dialog-tree entry points | 5,571 | 8,000 |
| Block nodes / displayed lines | 29,028 / 19,420 | 44,956 / 31,952 |

Every chunk disassembles fully aligned, so every chunk gets a
tree. The 32 unresolved LSTR reads match the tool README's
number exactly; 30 of them have only computed writers
(accumulator-built strings, likely runtime-formatted text) and
2 have cross-chunk inline writers with no static call path (the
queued path-aware caller-picking backlog item).

Static text outside dialogs: TEXT pools (arena and NPC names:
ids 0..32, 100..118, 200..207; only 7 ids are ever read as
GSTR, the rest look engine-side for random naming), DS1 NAME id
1 (322 item names), DS2 TEXT-1000 (255 item names), SPIN spell
text, MERR (mostly "Unused..." stubs; DS1 duplicates the set in
CINE.GFF), ETME credits, DS2 RNME region names. Speaker census:
215 + 316 chunk-conversations; setother observed on 29 distinct
DS1 entities and 9 DS2 slots; creature names resolvable via
NAME(-N) into the bestiary.

## 3. The conversion shape

A Godot dialog system takes:

1. The `dialog_tree` node graph verbatim (blocks, line records
   with {opcode role, source, value, state snapshots},
   conditional children, cross-chunk expansions with their
   unresolved markers).
2. Menus as choice nodes: ordered (text, target offset,
   availability-expression) entries against an offset->node map.
3. Conditions/actions as gpl-disasm token trees: either a small
   evaluator or precompiled GDScript callables; actions are the
   non-string opcodes in each block (requests, flag writes,
   item ops) plus the sub/global call refs.
4. The state model: 10 global LSTR slots, GSTR backed by TEXT
   pools, LF/GF flags, LNUM/GNUM, GNAME handles, the
   setother/setthing speaker registers; the cross-chunk
   callgraph from `gpl-disasm --global-cfg`.
5. The static text assets (section 2), with the 19 packed
   strings that carry real control codes preserved.

RESOLVED 2026-09-19 (wave 3): menu availability polarity is `flag == 1`
(nonzero, literally 1) = show the entry, 0 = hide (DS1 0xcbcc, DS2
0xf21e; the evaluator only produces 0/1 in practice). INTRODUCE renders
as the current speaker's name: the sub-type-1 string arm appends the
combat-array name field of the VM:0x369 combatant into the sink at decode
time (gpl-vm.md 0x2C row has the details). The three unused TEXT-pool
bands are the engine's RANDOM-NAME banks: a three-case selector (arg 8 ->
1d8 + 199 -> ids 200..207; arg 1 -> 1d33 -> ids 0..32; else 1d19 + 99 ->
ids 100..118), position-identical in both games (DS1 ~0x67e8x in ovr19,
DS2 ~0x6fcdx in module 17). Still open: whether computed-writer strings
should be reproduced or frozen; speaker-mutating opcodes beyond setother.
