# Engine quirks

Surprising behaviors of the Dark Sun engines that bit us during
RE / modding. Each entry: what happens, when we noticed, where it
matters for OpenDS tooling.

## 1. Stats above 25 produce +0 damage bonus

**What**: Setting a PC's STR (or DEX, presumably) above the
top of the D&D 2e exceptional-strength table causes the engine
to return a `+0` damage bonus instead of the expected high
bonus. The character sheet correctly displays the raw STR byte
value (e.g. 99), but combat damage doesn't reflect it.

**Noticed**: 2026-05-18 while editing Gerakis in Brandon's DS1
save. His stats all set to 99 displayed as 99 on the sheet,
but he did 1 damage per hit. The cached weapon was `1d1`; STR
99 → bonus +0; damage = 1d1 + 0 = 1.

**Why**: 2e's STR table tops out at STR 25 (with the
`18/00`-`18/100` "exceptional strength" sub-range from 18 to
19). The engine indexes that table by the STR byte. Above
the top index, the lookup likely returns 0 or hits whatever's
at that memory location (which evaluated to 0 in this case).

**Where it matters**:
- `ds1-party-edit.py` documents this in the cookbook.
- `save-inspect edit-pc` could grow a warning if a stat flag is
  > 25 (not implemented yet; pure docs for now).
- Modders who want "godmode": prefer editing weapon damage
  fields directly (`num_dice` / `num_sides` / `num_bonuses`)
  over inflating stats.

## 2. DS1 active party lives in DARKRUN.GFF, not CHARSAVE.GFF

**What**: `CHARSAVE.GFF` in DS1 contains 8 PC records that
**are not the active party**. The active party (e.g. Brandon's
Gerakis / K'ratchek / Cermak / Cilla) is stored inside
`DARKRUN.GFF` as records in `SAVE/5` (combat sub-blocks) and
`SAVE/6` (character sub-blocks).

**Noticed**: 2026-05-18 when `save-inspect list-pcs` on
Brandon's DS1 save returned 8 unrecognised names and the
modder said "those aren't my party."

**Why**: Speculation. The 8 records in DS1 CHARSAVE may be
character-creation templates, recruitable NPCs, or hard-coded
roster entries we haven't identified. Whatever they are,
they're not the active party.

**Where it matters**:
- DS1 active-party edits go through `ds1-party-edit.py`
  (DARKRUN-based), not `save-inspect edit-pc` (CHARSAVE-based).
- DS2 by contrast *does* keep its active party in CHARSAVE.
  `save-inspect edit-pc` works for DS2.
- `docs/file-formats.md` §3 documents the file-role split.

## 3. SAVE0N.SAV is byte-identical to DARKRUN.GFF at save time

**What**: When the engine writes a save (file menu → save),
the on-disk save slot file (`SAVE01.SAV` etc.) is a verbatim
copy of `DARKRUN.GFF`'s contents at that moment.

**Noticed**: save-inspect v0.6.0 (2026-05-16) on
DS2 played save; reconfirmed v0.9.x on DS1.

**Why**: The engine appears to use `DARKRUN.GFF` as the live
in-memory snapshot of world state, then writes it verbatim
to the chosen slot file on Save. On Load, the engine reads
the slot file into memory and (presumably) writes
`DARKRUN.GFF` back from the load.

**Where it matters**:
- Persistent save edits must hit BOTH files together; a write
  to only `DARKRUN.GFF` gets wiped on next reload because the
  engine reads from `SAVE0N.SAV`.
- `ds1-party-edit.py` writes both files automatically.
- `save-inspect roundtrip` works on either file directly
  (both are valid GFFs with the same content).

## 4. DARKRUN.GFF auto-overwrites on game launch

**What**: Launching `DSUN.EXE` overwrites `DARKRUN.GFF` (zeros
it out, or reverts to a fresh state) before any save is
loaded. Modders who edit `DARKRUN.GFF` and then start the game
without loading a save will lose their edits.

**Noticed**: `tools/repro/`'s overlay-mount discipline grew out
of an early loss of `DARKRUN.GFF` content on a non-overlay
DOSBox run. Documented in repro v0.1.0 patchnote.

**Why**: The engine probably initializes new-game state on
launch and writes it to `DARKRUN.GFF` as the starting point.

**Where it matters**:
- Always either use `tools/repro/`'s overlay-mount harness
  (DOSBox writes go to an overlay dir, not the install) OR
  load a save immediately after launch (which restores from
  `SAVE0N.SAV`).
- `ds1-party-edit.py`'s edits to `DARKRUN.GFF` only matter if
  the user loads a save before doing anything else; the
  `SAVE01.SAV` edit is the persistent one. The DARKRUN edit
  is essentially a hot-cache poison for the in-memory state
  on next load.

## 5. SAVE/5 records put NAME at offset 40, not offset 0

**What**: The 58-byte DS1 combat sub-block layout (per libgff's
`ds1_combat_t`) places the NAME field at byte offset 40 of
each record, not at the start. A naive scan of the chunk for
"Gerakis" returns offset 40 (the start of his name) but
treating that as the start of his record yields nonsense
field values and writes to the wrong PC.

**Noticed**: 2026-05-18 when Brandon's edit to "Gerakis's
stats" (computed from name-offset + 52..57) ended up setting
K'ratchek's stats to 99. The 6-byte slot 52..57 of "record
starting at Gerakis's name" is actually bytes 12..17 of
K'ratchek's record-1 header.

**Why**: libgff schema. Stats[6] at offset 34..39; name[18]
at offset 40..57. Records are 58 bytes. Records start at
SAVE/5 offset 0; names are 40 bytes into each record.

**Where it matters**:
- `ds1-party-edit.py` parses records by stride (58 bytes from
  chunk start), not by name search.
- `docs/file-formats.md` §3.3 documents the full layout.

## See also

- [`file-formats.md`](file-formats.md) §3 — save-file layout
  details
- [`cookbook/edit-ds1-party.md`](cookbook/edit-ds1-party.md)
  — modder-facing workflow that touches all of these
