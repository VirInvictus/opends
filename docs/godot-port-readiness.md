# Godot port readiness: the layer-by-layer checklist

The capstone of the port-mining campaign (2026-09-19, waves 1-3 across
twelve agents). It answers one question: what would a Godot port of Dark
Sun consume, and is it mined? The answer after this campaign: the
KNOWLEDGE side is mined out. What remains is engineering (exporters, a
Godot project) plus a short, explicit runtime-capture list of behaviors
that live in runtime-populated tables and cannot be read from the
binaries. Every claim below cites its layer document.

The port shape follows the toolkit's own rule: the port loads the
player's own GOG install and ships no assets. Nothing in this document
changes that.

## The layer checklist

| Layer | Source | Status |
|---|---|---|
| Formats and tooling | gff-edit, gpl-disasm (fully aligned corpus), gpl-asm (600/600 byte-identical), image-extract, region-render (palette cycling, multi-frame entities), ovr-map, exe-patch | READY (the toolkit) |
| Overlay/binary substrate | overlay-formats.md: segment load table, module table, relocation tables, INT 3Fh dispatcher, fully static far-pointer resolution | READY |
| World data | world-dump-ds{1,2}.md (13,028 + 13,559 placements, grids, every trigger), region-formats.md, container/inventory dumps | READY |
| Content databases | bestiary/item/spell catalogues, 22 anchor gates, instruction-pinned fields | READY |
| Rules math | rules-tables.md (rules block, saves + formula, THAC0, XP tables, ability tables) + chargen-flow.md (stat gen, dual/multi-class, level-up, caps) | READY |
| Combat | combat-flow.md (entry, rounds, probabilistic initiative, the parity alternator, hit/damage/death, XP, morale ordering) | READY |
| Spells and effects | spell-effects.md (cast engine, the active-effect list, dispatch surfaces, ~60-70 named behaviors of an ~0x50-live-id status space, saves, durations, special attacks) | READY, ~35 status bits unpinned |
| Dialogs and text | dialogs.md (531 aligned chunks, 46k strings, node-graph conversion shape) + gpl-vm.md's resolved string sub-types, menu polarity, INTRODUCE, random-name banks | READY |
| Scripting VM | gpl-vm.md (the complete VM spec) + the world dumps' trigger registrations; dialog/trigger logic runs as an interpreter or precompiled GDScript callables | READY (two BSS caveats below) |
| UI | screen-flow.md (window manager model, 27+28-row screen inventory, mode enum, input dispatch, dialog print service) + presentation-formats.md (WIND/BUTN/APFM/FONT layouts, byte-identical font) | READY at map level |
| Asset bindings | asset-bindings.md (item icons = OJFF bmp_id, spell icons = 20999+id, portraits as dialog-line state, CBMP boolean) | READY |
| Audio | audio-routing.md (DS2: the DJ.DAT state machine, fully decoded; DS1: sound id = BVOC id; music has NO static mapping, proved) | READY (DS1 music binds by ear) |
| Exploration | exploration-flow.md (click-to-move, greedy + wall-follow pathfinding, formation boxes, the gridlock quirk, LOS, step-on-tile triggers, Tport, pixel scroll) | READY |
| Cinematics | cinematics-ds1.md (the BMA codec, validated 708/708 + visually verified; ACF scripts; the player chain); DS2 = standard FLI | READY |

## The honest remainder

### A. Runtime-capture candidates (behavior in runtime-populated tables)

These cannot be read from the binaries; each needs one DOSBox capture
(opcode-fuzz's infrastructure exists) or a played session:

1. Walk speed, animation frame timing, and scroll hysteresis margins
   (BSS-installed per-object drivers and scroll config).
2. The cinematic tick rate in Hz (one timed intro run).
3. GNAME pseudo-array initialization (13 far pointers; Getxy writes
   GSTATE, not GNAME).
4. The memorized-slot-count model and where memorized state lives.
5. ~35 status/effect bit semantics beyond the ~15 pinned (spell-effects.md
   8).
6. The morale-failure -> flee transition.
7. Loot object creation inside the rec7 placement services.
8. Order kinds 2..9/12/14/16 and the negated-kind encoding.
9. Region-load save/restore contents (ovr21).
10. DS1 music id -> context bindings (proved absent statically; bind by
    listening).
11. Small fry: DS2's rest handler body, the wild-talent draw, DATA:1002's
    consumer, the DS2 Tport twin's extra call, per-frame input-callback
    registration.

None of these blocks STARTING the port; each blocks exactness in one
feature.

### B. Engineering (not mining)

1. image-extract: add the BMA row/record wrapper (the codec is fully
   specified) and fix the 19 CINE stills (they are BMA-codec
   single-frame containers, currently misparsed).
2. Asset exporters: PNG atlases / Godot tilemaps / sprite frames from
   image-extract + the asset bindings.
3. The Godot project itself: the VM interpreter (or precompiled
   callables), the rules layer, the combat scene, the UI coordinator
   (data-driven from WIND trees), the audio director (DS2 DJ machine is
   fully specified), the dialog system (the conversion shape is
   documented), the exploration layer.
4. A decision the port owner owns: GDScript vs C# for the VM/rules core.

### C. Where to start (zero new RE needed)

The proof-of-life spike: export one region's tiles/walls/sprites to
atlases, drop the world-dump placements into a Godot tilemap, and render
a static region with entities standing in it. Everything that spike
consumes is already decoded, generated, and anchor-gated.

DONE 2026-09-19: the spike exists and works. `port-spike/` exports DS1
RGN02 (the start region) to a Godot 4 TileMap scene; the render matches
region-render's composite of the same area, and the export counts
reconcile with the world dump (558 placements = 465 drawn + the 93
documented off-grid staging records; 6,598 blocked; 645 walls). The
next engineering step beyond it is the image-extract BMA extension and
the exporters' graduation from spike to tool.
