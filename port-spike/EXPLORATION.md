# Slave Pens / Arena exploration record

Observations from the scripted tour (SPIKE_TOUR movie capture) cross-
referenced with the world dump and the cluebook shipped in the install.
Tile coords are (col,row) on the 128x98 grid; world px = tile*16.
The demo start is the arrival zone (79,70).

## The Slave Pens (region 41, RGN29.GFF)

The pens are a maze of brown-brick rooms around three main corridors:
a wide north-south hall on the east side, a central hall, and the west
monster-pen block. Landmarks from the tour:

| area | tiles | what the tour shows |
|---|---|---|
| Arrival zone | (79,65)..(79,70) | the party's arrival pen; the "doors slam shut" story beat fires here |
| Fountain court | (60..75, 74..84) | the big templar-built fountain (dark pool, two pink sprays) in an open court; benches and planters |
| Pehtucl's quarters | (22..40, 82..92) | the red-carpet room in the southwest corner: tables, chairs, a green psionic-splash decoration (the templar Pehtucl's room per the cluebook) |
| Monster pens (west) | (8..30, 40..60) | cells with the big black spider creatures, bones and skeletal remains scattered in the pens; the cells open onto the central hall |
| Mirlon's corner | (80..90, 60..70) | center-east nook; Mirlon (creature 88) is placed nearby with his gang |
| Dinos' kitchen | (92..104, 90..98) | southeast corner: the kitchen props (barrels, tables); Dinos (creature 183) placed here |
| Scar's corner | (80..90, 74..82) | south-center nook; Scar (creature 87) and his henchmen (229) hold it |
| The arena stair | (112..114, 27) | the door in the east hall's north end; its trigger asks "Enter the arena?" and leads to region 42 |

Doors: the cell/room doors are ETAB items named "Door" (object ids
2141..2176+) placed at doorways (e.g. (81,19)/(81,21), (95,27)/(95,29),
(36..53, 49)); their leaves are drawn as entities anchored by OJFF
offsets, and the GMAP carries only the block/LOS bits. Door wall
indices at those gaps (e.g. index 1/12/13 on the walkable tile south of
the solid block) are the frame/lintel sprites.

Guards: half-giant and Drajian guard creatures patrol the main halls
(placements in the world dump); several stand near the stair and the
templar quarters.

## The Arena (region 42, RGN2A.GFF)

A single large ring: sand floor enclosed by the crowd stands (repeated
spectator sprites along the top rows), the Announcer's booth on the
north wall (the green-robed Announcer, item 1203 placed at tile
(29,7)), the central monster grate (dark stone square), and tusks/bone
props scattered as cover. Venyz is staked out at the west side; weapon
racks line the east. The party enters from the pens at tile (30,13)
and the fight zone is the ring's center band.

Fight spawns (from the shipped spawn scripts, request 7 with
NAME(-2039)): tiles (59,15), (53,21), (6,18), (11,23) - the demo
converges them to ring distance 3-6 from the party instead, since the
shipped stats for object 2039 are a pool reference rather than inline
data.

## Loop mapping (demo flow)

intro -> pens (79,70) -> arena stair (113,27) -> arena (30,13) ->
fight zone (center band) -> combat -> victory -> holding gate
(28..32,11) -> pens (113,27) -> repeat (each fight +1 monster).
Break-out (escape tunnel, west tiles (5..7,30..32)) and guard attacks
are gated out of this build.
