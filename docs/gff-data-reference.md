# GPL data reference: the complex-access keyword set

The `obj_name >= 0x8000` keywords our decoder renders inside
`COMPLEX(...)` operands (complex access rides `GPL_COMPLEX_*`
0xB0..=0xBF, the 0xb3 special case, `gpl_setrecord` 0x40, and the
complex-write path of `gpl_load_variable` 0x16). Landed 2026-11-17
(issue #26). Usage evidence lives in
[`gplx-field-map.md`](gplx-field-map.md); this table is the identity
record.

## The table

| Keyword | Raw gname index | Our display | yuan-ti display | Meaning | DS1 uses | DS2 uses |
|---------|-----------------|-------------|-----------------|---------|----------|----------|
| `POV` | 0x25 | `GNAME[37]` | `gname[5]` | the active character (the viewer) | 323 | 921 |
| `ACTIVE` | 0x26 | `GNAME[38]` | `gname[6]` | the actor slot (DGROUP `0x367`) | 166 | 260 |
| `PASSIVE` | 0x27 | `GNAME[39]` | `gname[7]` | the target slot (DGROUP `0x365`) | 219 | 552 |
| `OTHER` | 0x28 | `GNAME[40]` | `gname[8]` | the other slot (DGROUP `0x363`) | 132 | 215 |
| `THING` | 0x2B | `GNAME[43]` | `gname[11]` | SETTHING's current item (DGROUP `0x35F`) | 6 | 27 |
| `OTHER1` | 0x2C | `GNAME[44]` | `gname[12]` | SET_OTHER's result (DGROUP `0x361`) | 56 | 261 |

Counts: every `COMPLEX(tag, NAME)` occurrence across all `GPL `/`MAS `
chunks of each game's canonical `GPLDATA.GFF` (gpl-disasm 0.9.0
text listings, 2026-11-17). No other `>= 0x8000` value appears: the
six names are the complete shipped set.

## The notation bridge (read before comparing notes across projects)

The keywords are the gname registers themselves, flagged:
`keyword = 0x8000 | raw_gname_index`, and the raw gname index lives
in `0x25..0x2C`. Three projects display the same register three
ways:

- **Our gpl-disasm** keeps the raw byte and renders it as-is:
  raw 0x25 displays as `GNAME[37]` (the raw id is stored; libgff's
  `- 0x20` display shift is a render-time convention we documented
  but do not apply -- see `read_simple_num_var` in gpl-disasm).
- **yuan-ti** displays the raw index minus 0x20 (raw `0x25` renders
  as `gname[5]`), per the engine note in Calvin Rodo's
  `dsun-exe-reference.md`: gname is an engine variable over raw
  indices `0x20-0x2E`, "shown as 0-14".
- **libgff** names the keyword forms directly: POV, ACTIVE,
  PASSIVE, OTHER, THING, OTHER1 (`src/gpl/parse.c`
  `gpl_access_complex`, MIT, cited in `CREDITS.md`).

So `0x8025` / our `GNAME[37]` / yuan-ti's `gname[5]` are one
register. This resolves the wording in the Legcrusher fix record
(`known-bugs.md` 3.6 row 4 and the beta.3 notes): calling our
`GNAME[37]` a "correction" of yuan-ti's `gname[5]` overstates it --
the design was always POV; only the display conventions differ. The
shipped bytes read the POV register either way.

## Evidence

1. **libgff** `gpl_access_complex` (lines 235-288): the switch on
   `obj_name & 0x7FFF` naming 0x25 POV, 0x26 ACTIVE, 0x27 PASSIVE,
   0x28 OTHER, 0x2B THING, 0x2C OTHER1, erroring on any other
   value.
2. **yuan-ti** `dsun-exe-reference.md` (MIT, Calvin Rodo): the gname
   storage table -- raw index 6 = actor (`0x367`), 7 = target
   (`0x365`), 8 = other (`0x363`), 9/10 = the 32-bit clock and
   money, 11 = the "thing" (`0x35F`), 12 = SET_OTHER (`0x361`) --
   and `obj_special(n)`: "0x25 is the active member". SETTHING
   (`1A0A:261E`) walks a container making each item the thing, and
   SET_OTHER stores its first match, which is why THING and OTHER1
   exist as keyword forms.
3. **Our corpus** (the counts above): all six names appear; no
   fourth-housand value does; and the POV register read as a plain
   variable (`GNAME[37]`) does exactly the active-member work in
   367 DS1 `get range` alive-checks (e.g. GPL 139 @0x275).
4. **Our decoder** renders the keyword names from libgff's table
   (gpl-disasm `lib.rs`, the `0x25 => "POV"` match arm) and keeps
   raw ids for the plain-variable form.

## Residual

The engine's own keyword resolution is not yet read directly: the
working reading is mask-and-index (`value & 0x7FFF` indexes the
gname table directly, since the six values land exactly in the raw
index range), and that shape predicts no compare switch -- our
scans across all immediate-compare encodings, u16 value pairs,
0x8000 masks, and sign tests found no switch in the DS1 image.
A direct read of the complex-access reader would settle it; the
identity table above does not depend on it.
