# Exploration: movement, blocking, line of sight, triggers, region transitions, viewport

The exploration-mode movement and region-interaction layer of both engines
(port-mining wave 3, 2026-09-19). A port reproduces this layer against the
region data that region-formats.md and the world dumps document. All
offsets are file offsets in DSUN.EXE (DS1 / DS2 = `.games/ds2/DSUN.EXE`);
every far-call resolution uses the static procedure of overlay-formats.md
section 6.

## 0. Runtime state this layer lives on (DS1; DS2 shifts in section 8)

| Cell | Meaning |
|---|---|
| DGROUP 0x4356:[0x556] | far ptr to the RUNTIME GMAP grid (alloc on region enter 0x19701, free 0x19721) |
| DGROUP [0x669d]/[0x669f], 32-byte stride | logical position, PIXELS (>>4 = tile); flags byte at +0x6694 (bit 0x20 = no-move); draw position +0x6697/+0x6699 |
| STATE 0x3972 +0x8a6 + slot*19 | the ORDER record: x@+0x8a6, y@+0x8a8, kind@+0x8aa (byte; may be stored NEGATED to flag a variant) |
| STATE +0x366 + slot*28 | the ANIM record: direction-queue bytes +0x00..0x0f (0..7 compass, 0xff terminator), queue index +0x10, facing +0x11, target tile +0x12/+0x14, path-start +0x16/+0x18, counter +0x1a |
| STATE +0xc36 | 320 x 3-byte slot table (0 empty, 1 party, 2 active) |
| GSTATE 0x377e +0x19 | combat-active word; +0x5/+0x7/+0x9/+0xb/+0xd/+0x11 = runtime-installed per-object sprite/trigger driver fn ptrs |
| VM 0x3781 0x363..0x369 | current-object registers; 0x369 = leader/active member |
| DGROUP [0x1178]/[0x117a] | viewport x/y pixel scroll offsets (320x200 window) |
| DGROUP [0x117c] | CURRENT REGION ID (identifies dsun-exe-re.md 3.3's ==42 guard as "region 42") |
| DGROUP [0x11b8] / [0x4c25] | interaction mode (0 none, 1 walk, 2 melee cursor, 3 spell, 4 ranged cursor, 5 other) / saved mode |
| DGROUP [0x4979] | active party-member slot, copied from VM:0x369 at region enter (0x1d536) |
| DGROUP [0x11d6] (dword) | master frame tick (incremented at 0x25d21) |
| VM:0x35b (dword) | game clock: +1 every 64 master ticks in mode 1, non-combat (0x25d42..0x25d62); SECONDS-scale (chargen-flow.md 4) |
| DGROUP [0x1650]/[0x1652] | formation half-width / height = desc&7 / desc>>8 of the leader's charrec+0x3d descriptor byte (0x21f54) |
| DGROUP [0x546]/[0x548] + 4*slot | party formation-destination tiles (0x142f:0x323) |
| DGROUP [0x42cc]:[0x42ce] | far ptr to the 13-byte-stride TRIGGER table |

## 1. Click-to-move pipeline

1. The event pump (screen-flow.md 5) routes exploration clicks to the mode
   router (ends 0x1af05; gates 0x1ae40), which dispatches on [0x11b8] via
   a 5-entry table at 0x1af06.
2. Cursor-mode clicks (melee/ranged/spell) run the click dispatcher
   0x1d66a: hit-test -> object slot or -1; then per mode: leader->target
   LOS (0x1d6da), distance (adjacency <= 1), item-usability, returning an
   action code 0x1771..0x1778.
3. Walk clicks (mode 1) enqueue through 0x1af0f (installed as an input
   callback via BSS; no static caller): validate the tile (0x142f:0xdc),
   scan STATE slots 5..0x2f for a monster whose tile-box contains the
   click, and if clear write ORDER {x, y, kind = 0x0f Goxy} (0x1b019),
   make the member active, set the movement-dirty flag.
4. GPL orders go through set_order 0x1f86a (0x1a0a:0x3ca): kinds 0x0f/0x11
   take literal (x,y); others take a target slot. Callers: the VM handlers
   for Fetch, Follow, Go, Goxy, Hunt, Flee (sites 0xabb4..0xb78a).
5. Execution is PER-TICK: the exploration tick 0x1587:0x1df1 (file
   0x1ca61) runs each frame; movement is two resident machines: move_step
   0x1ffaf (the 19-kind order interpreter, jump table 0x20655) and the
   all-slots mover loop 0x206bd.

THERE IS NO A*/BFS. The pathfinder is greedy straight-line + wall-follow
repair (section 3); each move_step consumes ONE direction byte from a
per-object queue of up to 15. Pixel motion is done by the sprite service
0x39d:0x1d1 through the GSTATE-installed per-object-kind drivers; per-frame
walk speed lives in those runtime-installed drivers (not statically
readable).

## 2. Blocking and occupancy

- blocked(x,y) = 0x142f:0xdc (file 0x197cc): null GMAP -> blocked; x >=
  0x80 or y >= 0x62 -> blocked; else GMAP[y*128 + x] & 0x40. ONLY bit
  0x40 is consulted for movement (GMAP bits 0..4 are never read by
  movement/LOS in either engine; the soloscuro MAP_DANGER caveat stands).
- GMAP bit API (module 0x142f, base 0x196f0): or/andnot/test at
  0x19742/0x19773/0x197a6; set-0x20 occupancy 0x198d0; clear-0x40 (door
  open) 0x198ff; clear-0x80 0x1992e; set-0x80 0x198b0.
- Passability for the pathfinder is the FORMATION-BOX check 0x1a0a:0x11db
  (file 0x2067b): every tile of the mover's (2w+1) x (h+1) box must be
  unblocked.
- Party reservations: formation-destination tiles are marked 0x60
  (occupied+blocked) by 0x1995d, released by 0x199a9; objects reserve
  their box via 0x21e2e/0x21ee9. Reserved tiles block other movers.
- GRIDLOCK ESCAPE (port-critical quirk): at the start of each member's
  move_step, 0x21daa collects every blocked tile inside the mover's OWN
  formation box and clears its 0x60 bits; at the step's end 0x21e2e
  re-ORs them (0x2063f). Party members can always path out of a crowd;
  the side effect is that a genuine wall tile inside the box is walkable
  for that one step, then restored.
- On a blocked step the engine does not slide: the wall-follower rotates
  the step direction (up to 4 x 45-degree turns, 0xe1bd..0xe224) and
  re-steps; if all rotations fail, move_step retries once, then cancels
  the Goxy order (0x20363..0x20387).

## 3. Pathfinding spec (port-reproducible)

Module 0x8bb (file 0xdfb0..0xeac2); direction helpers module 0x96c (file
0xeac0..0xec03). Directions 0..7 = N, NE, E, SE, S, SW, W, NW; delta
tables at 0x96c+0x02/+0x12. find_path (0x8bb:0x7f3, file 0xe7a3; args
include max_detours = 0x1e, diag flag, max_entries = 0x50):

1. path_build (0xdfb0): walk greedily toward the destination, re-asking
   dir_toward each tile; emits 6-byte records {x, y, dir}; 0xffff
   terminator.
2. validate/repair (0xe069): register a DETOUR POINT at each open<->blocked
   transition (0x12-byte ctx records).
3. detour walker (0xe185): wall-follow; when the next tile is blocked,
   rotate the direction (4-try dead-end check), step when free, rotate
   back; stop at a registered detour point.
4. Trim invalid trailing entries by re-querying passability from the end
   (0xe7e1); the destination becomes the last valid entry.

Caps: 80 path entries, 30 detour records. No cost field, no queue, no
optimality.

## 4. Line of sight

LOS walker = 0x898:0xa4 (file 0xde24; segtab record 4; entry local 0xa4;
the distance service is local 0xb = file 0xdd8b: integer sqrt of dx^2+dy^2,
999 sentinel on |delta| > 255). Args are TILE coords; sorts endpoints,
steps max(|dx|,|dy|) times with integer Bresenham; after each interior
step it calls the callback 0x150f:2 (file 0x1a4f2), which blocks on
`GMAP[y*128 + x] & 0x80`. Z is carried but NEVER consulted: LOS is purely
the 2D 0x80 bit. Adjacent tiles are always mutually visible. The DS1 wall
index (GMAP low bits) plays NO role in LOS or movement: render-only.

LOS gates found: click-attack validity, the enumerate service's optional
LOS flag (the same 0x898:0xa4 service; combat-flow.md 3), the on-approach
script prober (0x20db4), optional spawn-placement LOS (0x6ad92). RENDERING
IS NOT LOS-CULLED (entity culling is by Y-band only, the 0x23067 walker).

## 5. Party formation and followers

Formation dimensions come from the leader's charrec+0x3d descriptor byte:
w = desc & 7, h = desc >> 3 (file 0x21f54); the box is (2w+1) x (h+1)
tiles extending behind the reference tile. The follower/chase target
chooser (file 0x22339, used by order kinds 1/10/11/13/18/19) scans the
ring around the mover extended by both formation dims, rejects footprint
and formation-blocked tiles, and keeps the tile with minimum distance to
the target. Per-member formation destinations are maintained and 0x60-
marked. The leader's facing publishes to [0x165b] at the end of move_step.
The loop that assigns follower orders on a party walk is BSS-callback
wired (not statically visible); the machinery above is what a port
reproduces.

## 6. Triggers

Registration (GPL opcodes; DS1 dispatch-table addresses verified):
MoveTile 0xb7fa / DoorTile 0xb83f -> sorted-insert updater 0xcdd5 (5
params); MoveBox 0xb884 / DoorBox 0xb8c9 -> 0xcec0 (7 params); entity
triggers (Attack 0xb946 etc.) -> 0xcd25. One table (far ptr DGROUP
[0x42cc]:[0x42ce]), 13-byte records: +0 handler entry offset, +2 gpl
chunk id, +4 x, +6 y, +8 w (box) / spare (tile), +9 h (box), +0xa
mode-gate byte, +0xb next index (word, -1 terminates). (x,y)-ordered
insert with replace-on-match.

FIRING RIDES THE PIXEL-STEP DRIVER: 0x39d:0x1d1 -> the GSTATE-installed
twins (files 0x9247/0x938e) set the trigger context (seg 0x377b: +1
actor/mode, +3 x, +5 y; DGROUP 0x427a/0x427c) and scan: tile triggers
(0x92b9: x,y match and entry.[0xa] >= mode), box triggers (0x9400: inside
[x..x+w-1] x [y..y+h-1]), the door variant (0x91a5, either orientation);
fire = RunGplScript(chunk, offset, type=1) at 0x43d:1 (file 0x97d1);
FIRST MATCH ONLY: one trigger per step. Triggers are STEP-ON-TILE (fired
during the walk, per tile crossed), not per-tick scans; this mechanically
explains the known bug "walk through a firewall twice in one move, take
the damage twice". Doors: GMAP bit pairs (clear 0x40 + clear 0x80) at
0x23d58/0x23d8b etc.; GPL Lockdoor sets the VM flag consumed there.

## 7. Region transitions and encounters

Party Tport = ovr22 local 0x857 (file 0x6ac07): if [0x117c] != region ->
the region loader 0x560:0x98 (ovr21 local 0x98, file 0x68098); else
per-member reposition. All four party orders cleared, facings reset.
Object Tport = local 0x6df (0x6aa8f). Stairs/exits are NOT engine-native:
they are move/door triggers whose scripts call Tport. The spawn-spot
finder (0x6acb9) scans the formation box around a target tile: in-bounds,
formation-unblocked, optionally off-screen (>= 0x40 px outside the
viewport), optionally LOS-clear; spot pixel = tile*16 + 8.

Random encounters: the MONR selection is ovr38 REQUEST CODE 8 (jump table
cs:0x177, case 8 at file 0x7ffbb -> local 0xcb4 = file 0x80be4; correcting
combat-flow's 0x80bc4), whose ONLY caller is the GPL Request bridge at
0xa9aa. CONFIDENT NEGATIVE: there is NO engine-side per-step encounter
roll in DS1's resident movement code; encounter chance/conditions are
SCRIPT-side. Engine hooks that can lead to encounters: walk-over triggers,
the on-approach per-object script cells (order-adjacent +0x8b0/+0x8b4,
probed under LOS+distance by 0x20db4), and the mode-1 per-tick auto-combat
poll. The monster leash: distance > 24 tiles abandons the walk (0x203c8,
32-tick gate).

## 8. Viewport and frame loop

320x200 pixel window over the 2048x1568 world; offsets [0x1178]/[0x117a],
clamped to [0,1728] x [0,1368]. PIXEL SCROLL, not tile snap. Per tick in
mode 1: the leader's draw position vs viewport feeds scroll-needed
(0x27845): off-screen -> scroll; on-screen -> hysteresis margins (BSS
0x2f6f..0x2f75) gated by the current scroll direction. Scroll step: a
9-entry direction table scaled by [0x9b5c]/[0x9b5a] (set by the
scroll-config service 0x27a4f); the mode persists, so scrolling continues
while the leader stays outside the margin. Clicks convert viewport->world
as (click + offset) >> 4 (e.g. 0x1d821).

Master tick (0x25d18): [0x1f7e] = dirty; [0x11d6]++; every 8 ticks set
[0x1194] (the palette-pump request honored at 0x1a93c); every 64 ticks, in
mode 1, non-combat: VM:0x35b++ (the game clock). Main loop (0x1a5f0..
0x1a960): cursor latch, dialog service, cycle pump, exploration tick,
regen tick, loop while [0x11da] == 0. Region enter (0x1cda0..0x1cf29): mode
= 1, the four StartCycle registrations, party sprites placed, [0x4979] =
VM:0x369. The per-frame registration of the two mover machines and the
input callbacks is BSS-wired (runtime tables; same class as the pump's
scheduler slots).

## 9. DS1 vs DS2

Identical architecture; addresses shift: DGROUP 0x4356 -> 0x47e0 (GMAP ptr
:[0x556] -> :[0x538]); GSTATE/VM/STATE 0x377e/0x3781/0x3972 ->
0x3c10/0x3c13/0x3f49 (slot table +0xc33); order cells +0x8a6/+0x8a8/+0x8aa
-> +0x8a3/+0x8a5/+0x8a7 (kind literal 0x0f identical); anim records
STATE+0x366 stride 0x1c -> DGROUP+0x67bb stride 0x25 (facing +0x1); line
engine record 4 -> record 8; GMAP service 0x196f0 -> 0x1ad40; current
region [0x117c] -> [0x140c]; the DS2 party-Tport twin (0x73890) adds one
extra call (0x30:0xee) after the region load, body undecoded; trigger
scanners 0xbf85/0xc24f via GSTATE 0x3c10:0x5/0x7/0x9 (same 13-byte
records, 0xbc00..0xc500).

## 10. Open items

1. Order kinds 2..9, 12, 14, 16 have no resident producer found (they
   dispatch to the passive fall-through); kind 17 exists as a no-op exit.
2. The NEGATED-kind encoding (kinds stored negated, un-negated per pass
   with a "was negated" flag that skips arrival processing): producer and
   exact meaning open (presumably "run").
3. The DS2 Tport twin's extra 0x30:0xee call.
4. The full per-object script-trigger record layout beyond +0x8b0/+0x8b4.
5. GMAP-reload semantics on same-region Tport (do reservations persist?).
6. Whether STATE slots 48..319 ever receive movement orders.
7. Walk speed / animation timing / scroll margins (BSS, runtime-installed).
8. Trigger-table per-type head indices and capacity (runtime-built).
