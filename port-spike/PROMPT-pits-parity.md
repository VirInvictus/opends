# PROMPT: pits-parity close-out — the prompt for tomorrow's session

Read this whole file before doing anything. It is the mission, the
state, the open work, and the rules. Today (2026-09-20) the arena and
slave pits demo reached full UI coverage and a working combat loop;
what remains is finish-and-verify work inside the pits lock. Nothing
is pushed. Head is 8eb6c80.

## 0. Session rules (Brandon's, non-negotiable)

- ALL progress notes and summaries in ENGLISH. He reads everything.
- No live DOSBox driving without asking. Tonight's pits capture used
  only the AUTOTYPE script (section 5); keep it that way. If a key
  lands wrong, accept the take and rerun the script — never correct
  mid-flight.
- Subagents: max 4 concurrent, research/read-only, no nesting.
- Never push. Commits are local. Informative messages, no em-dashes.
- Python stdlib-only in tools (Pillow/numpy allowed in port-spike
  exporters); ruff pin 0.15.20 (`uvx ruff@0.15.20`) for anything in
  the CI gate.
- `.games/` and the wine installs stay read-only; the DOSBox rig uses
  the /tmp scratch copy.
- Regenerated assets need `godot --headless --import --path
  port-spike` before any render.
- Git trap from tonight: the working tree is shared. Another session
  committed mid-day (f77c665, 73e4ec9, 2d07f09, 5c057cd). Check
  `git log --oneline -5` before AND after you commit.

## 1. Where the port stands (all committed, HEAD 8eb6c80)

The demo (port-spike/, Godot 4.7) plays: intro cinematic -> slave
pens -> arena gate -> announcer sequence -> bone-pit fight -> victory
-> yell-back choice -> repeat fight, all with engine-parity UI. Audit
sheets for 12+ surfaces live in port-spike/audit/ (rebuild with
`python3 audit_sidebyside.py`), and the open-items list is
audit/POLISH.md — read it first, then this file.

Built and oracle-verified: menu, creation (3011), inventory (13500:
OJFF item icons, 13007 slot glyphs, per-member centre figures, live
text), sheet VIEW/USE/EFFECTS (11500: per-class colored line, PSP
row, spell grid, class/LEVEL bars), spell info 15503 (SPIN text),
examine strip 15500 + view-item 15502, game menu 10500, load 3009,
prefs 16500, overhead map (O), popups 14000, dialog 3007 (real
GPL-2 lines, announcer portrait PORT 119), choice strip 3008 (arrow
paging), message box 10501, combat HUD, damage splats (BMP 5014).

Combat (main.gd): single-actor token machine, threshold 20 + d10 +
DEX reaction (rules-tables.md 0x7dc table) + act mods, d200
tie-break, blows parity alternator, nat-20/nat-1 d20, rear/flank
THAC0-2 with per-round direction memory, crit roll 4/1 doubles or
halves the blow budget, monster damage bonus [0x11ae]-1 wired to the
prefs text-speed value, move costs 10/14. The USE picker casts for
real: all ten party spells route to their mined ovr32 handler
behaviours (SPELL_EFFECTS in main.gd); SPST 39-138 fall through to
the engine's generic default (0xc90) model.

Two soft-locks were found and fixed tonight; do not regress them:
- `state = State.COMBAT` must be assigned in _begin_fight (it was
  never assigned in the whole history of the file).
- DialogScreen frees itself on its last page; _say_sequence's
  finished handler clears ui_screen/ui_open BEFORE deferring the
  follow-up. If a dialog leaves ui_open stuck, everything wedges.

## 2. Open work, in the order Brandon asked for it

1. **Pits audit video (Godot side exists, needs cutting).** The
   raw take is /home/bdkl/.local/share/opends-live/pits2.mp4 (also
   /tmp/pits2.mp4): the paced AUTOTYPE run — menu, story, fade,
   gate dialogs, bone-pit fight. Cut the in-game stretch (keys land
   from +31s at 3s/key: gate dialogs ~45-60s, walk-down ~60-85s,
   computer-control fight ~85s+) and stack it Godot-side against
   cast3.mp4 (also in ~/.local/share/opends-live/) with the ffmpeg
   hstack pattern from tonight's menu pair. Deliverable:
   port-spike/audit/videos/pits_live.mp4.
2. **Spell effects from the mined table are modelled, but the
   per-spell names/benefits are not surfaced in the UI.** The USE
   bars show the class family and LEVEL page; the engine also shows
   the spell name on hover/selection. Cheap parity win: wire
   spins.json names into the grid selection.
3. **Interact 3020 routes**: talk replays announcer patter, INFO
   opens nothing yet. Wire INFO to the entity's bestiary row
   (creature id from the ETAB dump) shown in an examine panel;
   steal/give need the thief skill check and a transfer path.
4. **Examine strip 15500**: arrow cycling works; the middle arrow
   (15302) semantics are unverified against the engine.
5. **Center figure art is per race/gender only** (BMP 20000-20013,
   race_i/gender_i formula). Per-character armour overlays would
   need another dig.
6. **Live DOSBox side-by-side for the in-game surfaces**: the
   AUTOTYPE single-command pacing worked (3s/key); a longer take
   with more story-page enters and a slower walk would capture the
   full announcer sequence live. See section 5.

## 3. The traps learned tonight (do not re-learn them)

- GDScript: `a + x if cond else y` parses as `a + (x if cond else
  y)`. Never inline a ternary inside accumulation; assign first.
- GDScript: const containers are read-only. PartyData.MEMBERS is a
  static var for a reason.
- GDScript: `var x := dict["k"]` on an untyped dict fails to infer;
  type it explicitly.
- pkill -f "dosbox" matches YOUR OWN script's command line if the
  heredoc mentions dosbox. Use `pkill dosbox` (name only) in
  scripts, or run the script from a file whose name does not
  contain the pattern.
- dosbox-staging AUTOTYPE: multiple AUTOTYPE lines replace each
  other's pending schedule; put the whole key list in ONE command
  and pace with -p. Only the first key lands if the menu
  transition overlaps the second key — space the list or accept
  the take.
- Movie Maker renders black for harness scenes that build their
  own board (wind_test combathud); use the SPIKE snap path there.
- After ANY exporter or asset change: `godot --headless --import
  --path port-spike` before rendering, or you photograph stale
  textures.
- git add from the repo root; a mid-work `git status --short | wc
  -l` of 0 with untracked dirs means you forgot `-A`.

## 4. Verification gates (run before you commit)

```
cd port-spike
godot --headless --import --path .        # parse check
python3 audit_sidebyside.py               # rebuild all sheets
SPIKE_UI=sheet SPIKE_OUT=/tmp/smoke.png timeout 60 \
  godot --path . res://main.tscn         # live smoke
uvx ruff@0.15.20 check export_items.py audit_sidebyside.py
```

For a combat take: SPIKE_DEMO=1 SPIKE_REGION=42 SPIKE_AT=30,20
godot --path . res://main.tscn --write-movie out.avi --fixed-fps
30 --quit-after 1600, then ffmpeg scale/cut. The scripted run casts
once (first known spell) then attacks.

## 5. The live DOSBox rig (hands-off, AUTOTYPE only)

Scratch rig already at /tmp/ds1-oracle (rebuild: rm -rf + cp -r
.games/ds1, copy __support/save/*.GFF and
tools/repro/bugs/ds1-smoke/SOUND.CFG into it; conf recipes are
committed in port-spike/live-capture/). Launch pattern:

```
dosbox --nolocalconf --conf /tmp/ds1-live.conf
```

AUTOTYPE is the ONLY input channel. One command per session
(a second line replaces the first's pending schedule); pace with
-p; pad the list with harmless repeats when a transition needs
time. Keys used tonight: enter (title), l / c / s (menu), escape,
v / i / u / tab (in-game screens), down (walk), space (computer
control). Record with wf-recorder -g "<window geom>" started
BEFORE the first key fires. Window is 14,54 939x1132 on this
desktop; the game area is the top 641px.

## 6. Completion bar for the pits lock

A surface is done when: it is built from the real WIND/chunk data,
renders at 320x200 against the oracle capture with elements within
a couple of px, uses the game's own art and font, is driven by the
real data model, and appears in a live or scripted capture. The
pits lock lifts only when Brandon says so — not when the checklist
looks done. Ask before going past the pens.
