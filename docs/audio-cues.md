# Audio cues: what plays, and who asks for it

Companion to audio-routing.md (the routing model: which service and
chunk kind answers an id) and file-formats.md 5 (the chunk formats).
This document owns the cue evidence: which sounds and music the
shipped scripts actually request, with ids, call-site counts, sample
durations, and context-derived meaning guesses.

Method (2026-10-06, mineout wave 1): `gpl-disasm --json` over every
GFF container in both GOG installs via
`tools/audio-extract/scripts/audio-cue-sweep.py`, collecting every
`gpl sound` (0x5D) and `gpl music` (0x5F) instruction with its
operand and the nearest inline strings from the same script chunk.
Regenerate with:

    python3 tools/audio-extract/scripts/audio-cue-sweep.py <GFF files> -o cues.json

Durations come from audio-extract's decoded inventory
(port-spike/generated/audio/, gitignored). Meaning is a context
guess from the calling script's own strings; every guess is exactly
as good as its example context, and the 111-sample ear pass
(mineout Phase A deliverable 5) remains the confirmation step.

## 1. Music: no static cue exists (proved negative, twice)

`gpl music` (0x5F) is never emitted in shipped bytecode of either
game (0 sites across the full sweep; first proved 2026-09-19,
audio-routing.md 2). DS1's music service exists and works (the VM
stub at 0x1a0a:0x672 calls MEL sequence play), but nothing static
binds track ids 1..23 to regions or events: music id selection is
runtime/engine-driven, and per audio-routing.md 2 the engine will
not contradict a port's choice of binding. Track names therefore
remain an ear-pass item.

What static mining DID recover for music:

- The 27 DS1 tracks' adaptive structure (RBRN branch tables; see
  file-formats.md 5 and port-digs-2026-10-06.md 2). Branch counts:
  tracks 5, 13, 14 are the most-branched cues (7-8 branch points);
  most tracks carry 2-6; tracks 7 and 17 (short stings) and all
  four CINE.GFF themes (26..29) are linear.
- CSEQ 1000 (both games, ~75 bytes) is the tiny clock sequence the
  engine keeps resident: FORM XDIR + CAT XMID + EVNT with a single
  FOR/NEXT/Callback loop and no notes.
- DS2 has no GPL music at all; its director is the DJ.DAT state
  machine over CD redbook (audio-routing.md 1).

## 2. DS1 script-referenced sounds

The engine plays many sounds without GPL (UI, combat resolution);
the table below is the script-reachable subset: 251 call sites,
55 distinct ids, every one in GPLDATA.GFF (DS1 region files carry
no GPL chunks). 56 of the 111 shipped BVOCs are never referenced by
any script: engine-driven or dead. Four scripted ids point at BVOCs
the corpus does not ship (19, 30, 87, 127): the engine's GFF-first,
file-fallback lookup (audio-routing.md 3) finds neither, so those
sites are silent in a stock install.

### DS1 script-referenced sounds

sound id = BVOC chunk id (audio-routing.md 3). 55 distinct ids across 251 call sites, all in GPLDATA.GFF.

| sound | BVOC | sites | chunks | s | meaning (context guess) | example context |
|---|---|---|---|---|---|---|
| 72 | 72 | 73 | 14 | 1.90 | ethereal fade / apparition waver (generic arcane sting) | As you step toward the body, it wavers a bit, as if it weren... |
| 53 | 53 | 19 | 15 | 1.67 | reward / coin jingle (give-and-take contexts) | Tell me about the flushing tunnels. |
| 76 | 76 | 18 | 2 | 2.14 | crowd jeer / spirit voices | Only the unworthy would retreat from the spirits. You are no... |
| 62 | 62 | 10 | 3 | 1.38 | flames roar (fire circle) | No! I know I'm doing this right! |
| 4 | 4 | 8 | 7 | 0.73 | sand work (dig/shovel) | You oaf! That's enough! Shovel the sand into bags! |
| 92 | 92 | 7 | 5 | 1.97 | ground rumble (arcane recitation) | Balkazar recites several arcane passages. The ground rumbles... |
| 36 | 36 | 6 | 2 | 2.98 | crowd cheers / money thrown | That's enough for me. I'm leaving. I'll go find more members... |
| 59 | 59 | 5 | 5 | 2.99 | dismissal hiss / serpent shimmer | Vrock, you are dismissed! |
| 124 | 124 | 5 | 2 | 1.45 | incantation blast (villain cast) | Fools! I swear I'll make your deaths painful! |
| 75 | 75 | 4 | 4 | 2.22 | unlabeled (ear pass pending) | Aargh! You traitorous worm! I will crush you beneath my heel... |
| 30 | 30 | 4 | 4 | none | gate bashed open | bashes the lock and the gate swings open. |
| 26 | 26 | 4 | 3 | 1.71 | cry for help / alarm | tries to yell for help but the roar of the fountain masks hi... |
| 67 | 67 | 4 | 4 | 0.73 | door battered down | bashes down the door! |
| 38 | 38 | 4 | 2 | 0.86 | rock removal | Remove a piece of rock? |
| 101 | 101 | 4 | 3 | 2.11 | elemental rift opening | Oh, great genie! I command you to open a rift to the element... |
| 93 | 93 | 4 | 2 | 2.13 | rush of wind (cleansing) | he touches the wall. |
| 37 | 37 | 4 | 2 | 2.82 | crowd murmur (Alliance scenes) | That's enough for me. I'm leaving. I'll go find more members... |
| 100 | 100 | 4 | 2 | 2.07 | dazzling flash (warded door) | The eyes on the door glow brightly, the light dazzling your ... |
| 78 | 78 | 3 | 3 | 0.52 | unlabeled (ear pass pending) | The wall to the north shimmers as you walk past. |
| 8 | 8 | 3 | 2 | 2.82 | unlabeled (ear pass pending) | Aargh! You traitorous worm! I will crush you beneath my heel... |
| 19 | 19 | 3 | 3 | none | unlabeled (ear pass pending) | Do you pull the lever? |
| 60 | 60 | 3 | 2 | 2.79 | unlabeled (ear pass pending) | Wait here while we open the portcullis. With luck, the castl... |
| 45 | 45 | 3 | 2 | 1.10 | unlabeled (ear pass pending) | here, but I'm afraid it's too technical for you barbarians. ... |
| 70 | 70 | 3 | 1 | 34.73 | long ambient (34.7 s): victory/theme-length cue | The guard |
| 103 | 103 | 3 | 2 | 2.04 | unlabeled (ear pass pending) | notices a slight movement beneath the sand. |
| 74 | 74 | 3 | 3 | 2.05 | unlabeled (ear pass pending) | You must be near the steam tank to use the powder in it. |
| 29 | 29 | 3 | 2 | 2.48 | unlabeled (ear pass pending) | Congratulations! The party gains 1,000 experience! |
| 115 | 115 | 2 | 1 | 1.92 | unlabeled (ear pass pending) | will escort you to the palace gates. |
| 57 | 57 | 2 | 2 | 2.81 | unlabeled (ear pass pending) | won't be alerted. |
| 1 | 1 | 2 | 2 | 0.04 | unlabeled (ear pass pending) | finds the button on the north wall. |
| 3 | 3 | 2 | 1 | 0.57 | unlabeled (ear pass pending) | This door is too strong to bash open. |
| 87 | 87 | 2 | 1 | none | unlabeled (ear pass pending) | The forge is too cold to heat the rod properly. |
| 58 | 58 | 2 | 1 | 47.31 | long ambient (47.3 s): victory/theme-length cue | That's enough for me. I'm leaving. I'll go find more members... |
| 39 | 39 | 2 | 1 | 2.05 | unlabeled (ear pass pending) | There's nothing like a successful hunt to make you feel aliv... |
| 97 | 97 | 2 | 2 | 1.90 | unlabeled (ear pass pending) | You must be near the steam tank to use the powder in it. |
| 108 | 108 | 2 | 2 | 0.09 | unlabeled (ear pass pending) | Goburnix is still waiting for you to get out of the way. |
| 91 | 91 | 1 | 1 | 1.98 | unlabeled (ear pass pending) |  |
| 21 | 21 | 1 | 1 | 0.63 | unlabeled (ear pass pending) | scrambles over the wall with ease. |
| 2 | 2 | 1 | 1 | 2.05 | unlabeled (ear pass pending) | The door is jammed open! |
| 56 | 56 | 1 | 1 | 2.60 | unlabeled (ear pass pending) | as her body is hopelessly dispersed. |
| 22 | 22 | 1 | 1 | 1.58 | unlabeled (ear pass pending) | 'A curse on my sister! So long as my bones endure, so shall ... |
| 85 | 85 | 1 | 1 | 2.88 | unlabeled (ear pass pending) | the fungus grove disappears |
| 12 | 12 | 1 | 1 | 2.03 | unlabeled (ear pass pending) | be able to stand tommorrow! Heh heh heh.... |
| 127 | 127 | 1 | 1 | none | unlabeled (ear pass pending) | now. Goodbye. |
| 71 | 71 | 1 | 1 | 2.24 | unlabeled (ear pass pending) | You must be near the steam tank to use the powder in it. |
| 84 | 84 | 1 | 1 | 0.22 | unlabeled (ear pass pending) | You must be near the steam tank to use the powder in it. |
| 77 | 77 | 1 | 1 | 0.69 | unlabeled (ear pass pending) | You must be near the steam tank to use the powder in it. |
| 34 | 34 | 1 | 1 | 1.22 | unlabeled (ear pass pending) | recites the passages in the book! |
| 32 | 32 | 1 | 1 | 2.12 | unlabeled (ear pass pending) | of damage! |
| 86 | 86 | 1 | 1 | 1.55 | unlabeled (ear pass pending) | Balkazar recites an |
| 109 | 109 | 1 | 1 | 0.08 | unlabeled (ear pass pending) | If you survive, come back here and destroy this blasted city... |
| 96 | 96 | 1 | 1 | 0.86 | unlabeled (ear pass pending) | A voice emanates from the chamber: |
| 50 | 50 | 1 | 1 | 1.28 | unlabeled (ear pass pending) | Every Search, Not Warranted, Earns Naught. -- Nilragor |
| 52 | 52 | 1 | 1 | 2.01 | unlabeled (ear pass pending) | by anyone. |
| 6 | 6 | 1 | 1 | 2.82 | unlabeled (ear pass pending) | Congratulations! The party gains 5,000 experience! |

### DS2 script-referenced sounds

BVOC chunk id = sound id + 1 (audio-routing.md 3). 128 distinct ids across 433 call sites, all in GPLDATA.GFF.

| sound | BVOC | sites | chunks | s | meaning (context guess) | example context |
|---|---|---|---|---|---|---|
| 221 | 222 | 29 | 22 | 2.99 | boss awareness / threat sting | learns of your presence. He is infinitely more powerful than... |
| 12 | 13 | 28 | 11 | 1.28 | elemental gate surge | The gate radiates powerful energies from the elemental spher... |
| 8 | 9 | 24 | 15 | 2.08 | templar retreat / jump | Soldiers, cover my retreat! |
| 7 | 8 | 17 | 10 | 2.01 | Draxan templar challenge yell | From across the bridge, a Draxan templar yells over at you. |
| 40 | 41 | 14 | 6 | 2.22 | secret stairs grinding open | deep inside clicks as the statue moves to reveal narrow stai... |
| 34 | 35 | 11 | 6 | 2.21 | switch / mechanism | Combine the two pieces of the flute. |
| 10 | 11 | 11 | 7 | 1.28 | unlabeled (ear pass pending) | The portal no longer radiates magic. |
| 30 | 31 | 11 | 4 | none | crypt exit / switch | The stairs lead back to Tyr. Do you leave the crypt? |
| 41 | 42 | 11 | 3 | 2.21 | railhead switch | The railhead switch is set to |
| 35 | 36 | 11 | 3 | 2.21 | switch / mechanism | The railhead switch is set to |
| 61 | 62 | 8 | 4 | 0.24 | mushroom lady sinks underground | The Mushroom Lady is sucked underground, out of harm's way! |
| 21 | 22 | 7 | 2 | 2.13 | mushroom lady sinks underground | The Mushroom Lady is sucked underground, out of harm's way! |
| 48 | 49 | 7 | 4 | 2.15 | unlabeled (ear pass pending) | You are too far away to move the rock. |
| 6 | 7 | 7 | 5 | 2.11 | ruby lost to magma | Your precious Ruby is sinking! It will burn in the magma for... |
| 32 | 33 | 6 | 3 | none | nest approach | You need to be closer to the nest before you can do that. |
| 47 | 48 | 6 | 3 | 2.21 | unlabeled (ear pass pending) | Soldiers, cover my retreat! |
| 99 | 100 | 6 | 5 | 0.26 | missile weapon fire | missile |
| 9 | 10 | 5 | 3 | 1.54 | huge rocks sinking | You're not close enough to use the plank. |
| 67 | 68 | 5 | 3 | 2.19 | unlabeled (ear pass pending) | rolls over in pain |
| 94 | 95 | 5 | 3 | 1.74 | unlabeled (ear pass pending) | go back to the upper level of the mines. Continue? |
| 14 | 15 | 5 | 3 | 1.24 | unlabeled (ear pass pending) | fails to dodge |
| 63 | 64 | 4 | 4 | 2.22 | unlabeled (ear pass pending) | Change it to what? |
| 19 | 20 | 4 | 4 | 2.22 | unlabeled (ear pass pending) | I'm not going anywhere with you! |
| 100 | 101 | 4 | 3 | 1.52 | unlabeled (ear pass pending) | money are soon parted. |
| 224 | 225 | 4 | 2 | 2.00 | unlabeled (ear pass pending) | of the four elements are carved all along its length, along ... |
| 183 | 184 | 4 | 4 | 2.15 | unlabeled (ear pass pending) | As you place your foot on the steps, you hear the cries of y... |
| 18 | 19 | 4 | 4 | 1.91 | unlabeled (ear pass pending) | It is no doubt just another ghost story, but now is not the ... |
| 17 | 18 | 4 | 3 | 1.85 | unlabeled (ear pass pending) | descend. Continue? |
| 62 | 63 | 4 | 3 | 2.20 | unlabeled (ear pass pending) | Rap eight times. |
| 1 | 2 | 4 | 1 | none | unlabeled (ear pass pending) | We're here. Step forward and ring the bell. |
| 59 | 60 | 3 | 3 | 0.84 | unlabeled (ear pass pending) | You are too far from the house to use the crowbar. |
| 75 | 76 | 3 | 3 | 1.40 | unlabeled (ear pass pending) | You need to be closer to the nest before you can do that. |
| 44 | 45 | 3 | 2 | none | unlabeled (ear pass pending) | You're not close enough to use the plank. |
| 60 | 61 | 3 | 3 | 0.32 | unlabeled (ear pass pending) | Do I take the busts? |
| 11 | 12 | 3 | 3 | 2.17 | unlabeled (ear pass pending) | The portal no longer radiates magic. |
| 223 | 224 | 3 | 3 | 1.98 | unlabeled (ear pass pending) | chalice |
| 28 | 29 | 3 | 3 | 1.70 | unlabeled (ear pass pending) | though many of the words have been defaced. |
| 31 | 32 | 3 | 2 | 0.59 | unlabeled (ear pass pending) | Your answer suffices. I leave you now, but do not doubt that... |
| 22 | 23 | 3 | 2 | 0.30 | unlabeled (ear pass pending) | Part of the ceiling collapses, sending a large chunk of rock... |
| 222 | 223 | 3 | 1 | 1.20 | unlabeled (ear pass pending) | the Ruby! |
| 79 | 80 | 3 | 3 | 2.21 | unlabeled (ear pass pending) | The guard sees you and motions for you to get back into the ... |
| 95 | 96 | 3 | 1 | 0.92 | unlabeled (ear pass pending) | The door is closed and locked. |
| 80 | 81 | 3 | 2 | none | unlabeled (ear pass pending) | Be patient -- I'm on my way! |
| 69 | 70 | 3 | 2 | 0.48 | unlabeled (ear pass pending) | hears some voices from the room up ahead. They don't sound |
| 97 | 98 | 3 | 3 | 0.73 | unlabeled (ear pass pending) | You are too far away from the switch to use it. |
| 178 | 179 | 3 | 3 | 2.18 | unlabeled (ear pass pending) | The one templar points an accusing finger at the other. |
| 92 | 93 | 3 | 1 | 2.21 | unlabeled (ear pass pending) |  |
| 56 | 57 | 3 | 3 | 0.89 | unlabeled (ear pass pending) | strength, but the door does not budge. |
| 26 | 27 | 2 | 2 | 1.71 | unlabeled (ear pass pending) | broken bodies squirm. |
| 134 | 135 | 2 | 1 | 2.22 | unlabeled (ear pass pending) | Many of the air drakes turn and run from the screeching soun... |
| 135 | 136 | 2 | 1 | none | unlabeled (ear pass pending) | Many of the air drakes turn and run from the screeching soun... |
| 39 | 40 | 2 | 2 | 2.21 | unlabeled (ear pass pending) | Remove the bust from the pedestal? |
| 23 | 24 | 2 | 2 | 2.21 | unlabeled (ear pass pending) | Khildril |
| 89 | 90 | 2 | 2 | none | unlabeled (ear pass pending) | brings Promere's Hammer crashing down on El's Drinker. The s... |
| 70 | 71 | 2 | 2 | 1.67 | unlabeled (ear pass pending) | I need a break. The sun'll be the death of me! |
| 74 | 75 | 2 | 2 | none | unlabeled (ear pass pending) | The scepter has no effect on the gate. |
| 160 | 161 | 2 | 2 | 2.12 | unlabeled (ear pass pending) |  |
| 137 | 138 | 2 | 2 | 2.43 | unlabeled (ear pass pending) | ...misses its sting. |
| 24 | 25 | 2 | 2 | none | unlabeled (ear pass pending) | You were fools to follow me! And now you will pay the price ... |
| 218 | 219 | 2 | 2 | 2.05 | unlabeled (ear pass pending) | Your answer suffices. I leave you now, but do not doubt that... |
| 151 | 152 | 2 | 2 | 2.22 | unlabeled (ear pass pending) | Your answer suffices. I leave you now, but do not doubt that... |
| 4 | 5 | 2 | 2 | 2.21 | unlabeled (ear pass pending) | touches the lightning rod to the door, a surge of power knoc... |
| 27 | 28 | 2 | 2 | 2.21 | unlabeled (ear pass pending) | carefully reaches into the brazier and pulls out an ember of... |
| 65 | 66 | 2 | 2 | 0.87 | unlabeled (ear pass pending) | strength, |
| 132 | 133 | 2 | 2 | 1.09 | unlabeled (ear pass pending) | The ruby! Where is it?! You must get the ruby! Hurry! |
| 42 | 43 | 2 | 2 | 1.96 | unlabeled (ear pass pending) | I don't care. |
| 96 | 97 | 2 | 2 | 0.87 | unlabeled (ear pass pending) | You are too far away from the switch to use it. |
| 36 | 37 | 2 | 2 | 2.21 | unlabeled (ear pass pending) | wound around the drum. |
| 101 | 102 | 2 | 2 | 1.02 | unlabeled (ear pass pending) |  |
| 57 | 58 | 2 | 2 | 1.89 | unlabeled (ear pass pending) | As the body of the miner dies, a hideous beast springs out o... |
| 93 | 94 | 2 | 1 | 2.21 | unlabeled (ear pass pending) |  |
| 115 | 116 | 2 | 1 | none | unlabeled (ear pass pending) |  |
| 90 | 91 | 2 | 2 | none | unlabeled (ear pass pending) | ...misses its sting. |
| 98 | 99 | 2 | 1 | 0.44 | unlabeled (ear pass pending) | missile |
| 88 | 89 | 2 | 2 | none | unlabeled (ear pass pending) | found some tracks in the dirt! |
| 91 | 92 | 2 | 2 | 2.22 | unlabeled (ear pass pending) | The lock opens with a click. |
| 64 | 65 | 2 | 1 | 0.11 | unlabeled (ear pass pending) | The Erdlu Blood soaks into the baya leaves. |
| 136 | 137 | 1 | 1 | 1.23 | unlabeled (ear pass pending) | Many of the air drakes turn and run from the screeching soun... |
| 55 | 56 | 1 | 1 | 1.71 | unlabeled (ear pass pending) | You are too far from the house to use the crowbar. |
| 50 | 51 | 1 | 1 | 2.21 | unlabeled (ear pass pending) | You are too far away to use the switch. |
| 76 | 77 | 1 | 1 | none | unlabeled (ear pass pending) | Climb the path? |
| 71 | 72 | 1 | 1 | none | unlabeled (ear pass pending) | Enter the tunnel? |
| 37 | 38 | 1 | 1 | 2.22 | unlabeled (ear pass pending) | Change it to what? |
| 38 | 39 | 1 | 1 | 2.21 | unlabeled (ear pass pending) | Change it to what? |
| 194 | 195 | 1 | 1 | 0.80 | unlabeled (ear pass pending) |  |
| 130 | 131 | 1 | 1 | 1.36 | unlabeled (ear pass pending) | rest, the large rock begins to move! |
| 198 | 199 | 1 | 1 | 2.19 | unlabeled (ear pass pending) | The sarcophogus is empty. |
| 173 | 174 | 1 | 1 | 2.23 | unlabeled (ear pass pending) |  |
| 227 | 228 | 1 | 1 | 1.97 | unlabeled (ear pass pending) | is struck by jolt of electricity! |
| 109 | 110 | 1 | 1 | 1.88 | unlabeled (ear pass pending) | 's clothes suddenly erupt into flames as an elemental |
| 219 | 220 | 1 | 1 | 1.95 | unlabeled (ear pass pending) | into the philtre device. |
| 150 | 151 | 1 | 1 | 0.28 | unlabeled (ear pass pending) | From across the bridge, a Draxan templar yells over at you. |
| 199 | 200 | 1 | 1 | 2.11 | unlabeled (ear pass pending) | Were he to become keeper, the volcano would surely erupt, an... |
| 3 | 4 | 1 | 1 | 2.04 | unlabeled (ear pass pending) | cannot use the staris while in combat! |
| 45 | 46 | 1 | 1 | none | unlabeled (ear pass pending) | has canceled the field. You may kill me, but not before I de... |
| 66 | 67 | 1 | 1 | 2.21 | unlabeled (ear pass pending) | broken bodies squirm. |
| 83 | 84 | 1 | 1 | 0.90 | unlabeled (ear pass pending) | You have saved Athas from the scourge of El! The party recei... |
| 122 | 123 | 1 | 1 | 2.23 | unlabeled (ear pass pending) | The Mushroom Lady is sucked underground, out of harm's way! |
| 205 | 206 | 1 | 1 | none | unlabeled (ear pass pending) | The Mushroom Lady is sucked underground, out of harm's way! |
| 114 | 115 | 1 | 1 | 2.06 | unlabeled (ear pass pending) | played out. |
| 25 | 26 | 1 | 1 | 2.21 | unlabeled (ear pass pending) | gets experience! |
| 197 | 198 | 1 | 1 | 1.07 | unlabeled (ear pass pending) |  |
| 191 | 192 | 1 | 1 | 1.11 | unlabeled (ear pass pending) |  |
| 138 | 139 | 1 | 1 | 2.23 | unlabeled (ear pass pending) |  |
| 139 | 140 | 1 | 1 | 2.07 | unlabeled (ear pass pending) |  |
| 149 | 150 | 1 | 1 | 1.57 | unlabeled (ear pass pending) |  |
| 158 | 159 | 1 | 1 | none | unlabeled (ear pass pending) |  |
| 145 | 146 | 1 | 1 | none | unlabeled (ear pass pending) |  |
| 180 | 181 | 1 | 1 | none | unlabeled (ear pass pending) |  |
| 184 | 185 | 1 | 1 | 0.60 | unlabeled (ear pass pending) |  |
| 112 | 113 | 1 | 1 | 1.70 | unlabeled (ear pass pending) |  |
| 148 | 149 | 1 | 1 | 2.14 | unlabeled (ear pass pending) |  |
| 82 | 83 | 1 | 1 | 2.21 | unlabeled (ear pass pending) | Just being a small cog in the Great Engine of the Mines... t... |
| 102 | 103 | 1 | 1 | none | unlabeled (ear pass pending) |  |
| 200 | 201 | 1 | 1 | 1.26 | unlabeled (ear pass pending) |  |
| 110 | 111 | 1 | 1 | 1.46 | unlabeled (ear pass pending) | Humpf. Not so bad, was it? Now, what was you findin' out dow... |
| 111 | 112 | 1 | 1 | 1.29 | unlabeled (ear pass pending) | Give me all your ore. |
| 29 | 30 | 1 | 1 | 2.20 | unlabeled (ear pass pending) | Thank you for your help, and never cease your vigilance agai... |
| 49 | 50 | 1 | 1 | 2.23 | unlabeled (ear pass pending) | Did you hear something? I thought I heard something. |
| 147 | 148 | 1 | 1 | 1.88 | unlabeled (ear pass pending) | But when I present him your heads arranged most prettily on ... |
| 2 | 3 | 1 | 1 | none | unlabeled (ear pass pending) |  |
| 177 | 178 | 1 | 1 | 2.23 | unlabeled (ear pass pending) | Oh thank you. Please, let's leave this place immediately. |
| 140 | 141 | 1 | 1 | 0.80 | unlabeled (ear pass pending) | Thank you again for getting rid of that thing. We can all re... |
| 72 | 73 | 1 | 1 | 2.15 | unlabeled (ear pass pending) | does not make a sound. |
| 209 | 210 | 1 | 1 | 1.35 | unlabeled (ear pass pending) | groans in protest under |
| 54 | 55 | 1 | 1 | 2.21 | unlabeled (ear pass pending) | brings Promere's Hammer crashing down on El's Drinker. The s... |
| 46 | 47 | 1 | 1 | 0.45 | unlabeled (ear pass pending) |  |
| computed (lnum[1]) | - | 1 | - | - | operand computed at runtime | |


## 3. Notes and open items

- DS1 ids 58 and 70 are 47.3 s and 34.7 s BVOCs: theme-length
  ambients, most likely the victory/level stings played through the
  sound channel. Prime ear-pass candidates.
- DS2's sample set is heavily uniform at ~2.2 s (a large batch of
  voice-length cues); DS2 speech proper routes through SPCH/INTR
  .VOC files, not BVOC (audio-routing.md 3).
- The 0x5F negative and the two tables above close the static half
  of mineout Phase A deliverable 3. What static mining cannot do:
  name the 56 unreferenced DS1 BVOCs and bind DS1 music ids to
  contexts. Both need the ear pass (DOSBox rig or local playback),
  which is a Brandon-assisted session, not an agent task.
