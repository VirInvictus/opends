# Capture sessions: the playbook

The three play sessions only a human at the keyboard can run,
written as turnkey cards. Everything here rides the `tools/repro/`
harness, so the installs are never writable (overlay mounts; see
`docs/engine-quirks.md` entry 4 for what a bare run does to
`DARKRUN.GFF`).

## Card A: played-save pairs (SAVE-id mapping)

Goal: convert `save-inspect`'s speculation rows into per-id
semantics, one in-game action at a time. The big two are decoded
structurally already (SAVE/1 = the 320-slot actor record array,
DS1 32-byte / DS2 37-byte records; SAVE/7 = the 1050x8 visible-
object array; `docs/engine-quirks.md` entry 12), so card-A pairs
now fill in the per-field map inside an actor record: position,
facing, sprite, HP. Then SAVE/2-4 and /7-9, the u16 scalar family
at 10..17, and the 51-byte SAVE/18 boolean array.

1. Launch a persistent session:

   ```sh
   python3 tools/repro/repro.py ds2-smoke --play --session savediff
   ```

2. In-game: reach a quiet spot, save to slot 1. Quit. The slot
   file is in the session overlay:
   `${XDG_STATE_HOME:-~/.local/state}/opends-repro/play-ds2-savediff/c-overlay/SAVE01.SAV`.
   Copy it out as `before.SAV`.
3. Relaunch (the session resumes), perform EXACTLY ONE action
   (pick up one item; kill one enemy; walk into one trigger;
   save immediately after), quit, copy the slot as `after.SAV`.
4. Diff:

   ```sh
   python3 tools/save-inspect/save-inspect.py save-diff before.SAV after.SAV
   python3 tools/save-inspect/scripts/save-semantic-diff.py before.SAV after.SAV
   ```

5. Clusters that print as UNKNOWN are the finding. Confirmed
   meanings become rows in `tools/save-inspect/syms/save-fields.toml`,
   so the next pair annotates automatically.

Repeat per action; small deltas only. A pair around each of the
five id families above maps the whole save surface in one sitting.

## Card B: the mines-elevator runtime capture

Goal: the one capture between the site report and complete
(`docs/engine-quirks.md` entry 6 has the full dossier). Two
routes, cheapest first.

Route 1, save-diff only (no debugger):

1. `--play --session elevator` on DS2 with a party save that is
   in the mines (region 57) with the elevator usable (Blick
   found: GNUM[58] bit 128 set).
2. Save to slot 1 immediately before using the elevator switch;
   copy `SAVE01.SAV` out as `before.SAV`.
3. Ride. If the freeze fires: quit, and copy the overlay's
   `DARKRUN.GFF` out untouched: its half-committed bytes at the
   freeze point are the evidence (the relocation does lseek/
   read/write on it through a close/reopen handle cycle).
4. If the ride succeeds, save to slot 2 and copy as `after.SAV`.
5. Run the semantic differ on the pair. The region-entry flag
   array and transition records serialize into the saves (ovr18
   trio: 0x70b66 / 0x709b8 / 0x71099), so the deltas show
   without a debugger.

Route 2, DOSBox debugger (if the diff is inconclusive): run under
`repro` as above, attach the Staging debugger, and set a
write-watchpoint on the transition-record array, whose layout and
base are known: `DGROUP:0x6874+(region_id-5)*37+0x16`, regions
56/57/58 for the mines (records are zero-on-disk BSS, populated
at runtime). Watch what writes when the switch flips.

Feed both routes' results into `known-bugs.md` 3a and the entry-6
dossier; that completes the site report, which Phase 7 assembles
into `ds2-patch/fixes/fix.ds2.mines-elevator.md`.

## Card C: the Phase 7-10 ladder

- Phase 7 (the fix): needs Card B's capture first; then the
  fix itself is GPL-layer (add the missing tport to GPL-287's
  handler), reproducible via `repro --diff` (FIX CONFIRMED =
  baseline FAIL, patched PASS), and verified over a full
  playthrough.
- Phase 8/9 (the sweeps): each bug in `known-bugs.md` needs the
  Card-A treatment (a pair around its trigger) before its fix
  is authorable; budget one session per two or three bugs.
- Phase 10: two full playthroughs with the patches on (no
  workaround needed) plus the announcement. Schedule only when
  the sweeps land.

All three cards assume the harness conventions in
`tools/repro/README.md`; the audio gotcha and session layout are
documented there.
