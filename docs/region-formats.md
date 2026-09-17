# Region formats: maps, placements, and triggers

The geography layer of the world dump (wave 3 of the mining
campaign, 2026-09-16), verified corpus-wide on all 33 DS1 and 20
DS2 region files. The generated per-game dumps live in
[`world-dump-ds1.md`](world-dump-ds1.md) /
[`world-dump-ds2.md`](world-dump-ds2.md); the generator is
`tools/gff-edit/scripts/extract-catalogue.py`. Region geometry
(128 x 98 tiles, 16 x 16 px, 2048 x 1568 px) is in
[`file-formats.md`](file-formats.md).

## 1. RMAP / MAP (the tile layer)

Exactly 12,544 bytes = 128 x 98, row-major `map[y*128 + x]`.
Each byte is the region's TILE resource id for that tile;
missing ids render as nothing. DS1 calls the type `RMAP`, DS2
`MAP ` (identical layout).

## 2. GMAP (walls and passability)

Same 12,544-byte grid. Bit layout:

| Bits | Meaning |
|---|---|
| 0-4 (0x1F) | wall/overlay sprite index, DS1 ONLY (0 = none): `w` selects `WALL[region_id*100 + w - 1]` from GPLDATA.GFF (664 WALL chunks). DS2's low five bits are zero on all 250,880 tiles of all 20 regions, and DS2 ships no WALL chunks: the wall layer is DS1-only |
| 5 (0x20) | runtime actor occupancy (set on exactly 1 DS1 tile, 0 DS2 tiles on disk) |
| 6 (0x40) | **MAP_BLOCK: impassable** |
| 7 (0x80) | **MAP_LOS: blocks line of sight** |

Only four values occur on disk: 0x00, 0x40, 0x80, 0xC0 (plus
one stray 0x60 editor artifact in DS1 RGN1E). Verification:
creature placements sit on 0x00 tiles (624/645 DS1, 528/544
DS2); region borders are blocked; Limbo (255) is ~100%
walkable with open borders, exactly what a staging void should
be; 0x80-only tiles read as walk-under overhangs. DS1 wall
sprites never sit on 0xC0 tiles: they are bottom-anchored on
the tile in front of the solid geometry, and the BLOCKING is
carried by the flag bits, not the sprite index. (soloscuro's
MAP_DANGER 0x07 overlaps the DS1 wall-index bits; that reading
belongs to DSO's runtime map, not these offline games.)

## 3. ETAB (entity placements)

8 bytes per record, count = chunk length / 8 (all 53 region
files are exact multiples; the region's chunk id = the region
id, shared with RMAP/MAP and GMAP):

| Off | Type | Field |
|---:|---|---|
| 0 | s16 | xpos, 0..2047 px |
| 2 | s16 | ypos, 0..1567 px |
| 4 | s8 | zpos (small vertical nudge; libgff's name, region-render subtracts it from y; corpus values 0/10/30/32/36/64/85 in a handful of regions) |
| 5 | u8 | flags (below) |
| 6 | s16 | object id: **DS1 always negative, DS2 always positive**; abs() = the OJFF/RDFF id (13,028 DS1 + 13,559 DS2 placements, 100% resolve) |

Flags: bits 0-2 draw priority (creatures carry 5/6/7; in DS2 it
is a per-OBJECT constant), bit 3 OBJECT_EXISTS (DS1 sets it on
every record, DS2 never), bit 4 DONT_DRAW (never on disk),
bit 5 ONE_OBJECT/"aliased" (DS2 sets it on 60%; exact runtime
meaning unconfirmed), bit 6 REDRAW (never), bit 7 X-mirror.

Resolution chain: placement -> abs(id) -> OJFF (16 bytes:
xoffset, yoffset, zpos, bmp_id@12, script_id@14) -> BMP sprite
and SCMD animation script (DS1 uses SCMD on 703 objects; DS2's
OJFF script_ids are all 0 with 538 SCMD chunks unused). Draw
position = `(x - ojff.xoffset, y - ojff.yoffset - zpos)`,
horizontally flipped when bit 7. Data-quality notes: DS1 RGN02
carries 93 off-grid staging placements (y up to 2016, the -90xx
band); a few DS2 records exceed x = 2047. Keep and flag them.

## 4. Triggers (the region's MAS chunk)

**MAS chunk id == region id, in BOTH games** (the roadmap's DS2
finding extended to DS1's 33 regions). MAS 99 exists in both
games as the global master with no region file; region 255
(Limbo) has no master. Trigger-registering opcodes (shapes
verified against handler code and instruction boundaries):

- Entity triggers, `(handler_offset, gpl_chunk_id,
  NAME(-object_id) [, extra])`: 0x65 attacktrigger, 0x66
  looktrigger, 0x6C pickup itemtrigger, 0x6D usetrigger, 0x6E
  talktotrigger, 0x6F noorderstrigger; 0x70 usewithtrigger
  carries TWO object operands; 0x1B/0x1C (not)inlostrigger
  carry a radius.
- Area triggers on the 128 x 98 tile grid: 0x68/0x69
  move/door tiletrigger = `(x, y, handler_offset, gpl_chunk_id,
  flag)`; 0x6A/0x6B move/door boxtrigger = `(x, y, w, h,
  handler_offset, gpl_chunk_id, flag)`. Verified against the
  roadmap's MAS-57 anchor: `move boxtrigger 26, 90, 5, 2, 1689,
  268, 0` is the 5 x 2 elevator-area trigger.

The generated world dumps carry every registration per region
(kind, object ids, target chunk@offset, raw operands); objects
with no ETAB placement are script-spawned (GPL `clone`) or live
elsewhere. Mines1/Mines3/Volcano-2/UnderTyr place zero creatures
in ETAB by design: their monsters arrive via MONR random
encounters and GPL `clone`.

## 5. The world-dump schema

`world-dump-dsN.md` (machine-generated): per region, a summary
line (placement counts by kind, tile count, walkable/blocked/
los-only/wall-indexed tile counts, trigger count and source),
the full placement table (`x, y, tile, object id, kind, name,
priority, flags`; kinds: creature/item/mini resolved through the
bestiary/item catalogues, otherwise a sprite labelled by its
BMP), and the trigger table. The grids themselves are summarized
(not 12,544 rows each); a converter regenerates full grids from
the game files with the layouts above or by reusing the
generator's `extract_world`.
