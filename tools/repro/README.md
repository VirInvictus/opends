# repro

DOSBox-Staging repro harness for OpenDS. v0.1.0.

Drives a per-bug fixture under `bugs/<id>/` against a working
DOS install, validates pass/fail by elapsed time and scratch-dir
artifacts, and never writes to the game install. The "any bug
reproducible in five minutes" plumbing from
[`roadmap.md`](../../roadmap.md) Phase 2.

## What it ships in v0.1.0

- A bash entry-point (`repro.sh`) and a Python driver
  (`repro.py`, stdlib-only).
- DOSBox-Staging config templates for both games
  (`configs/ds1.conf`, `configs/ds2.conf`). They opt the user's
  primary config in (for MT-32 ROMs etc.) but explicitly
  override audio settings the engine cares about.
- The `bug.toml` schema and one working fixture, `ds1-smoke`:
  DS1 boots, lives 25+ seconds, harness SIGTERMs DOSBox, PASS.
- Overlay-mount hygiene: every write the engine issues during
  the run lands in `/tmp/repro-<id>-XXXX/c-overlay/`. The
  `.games/` install stays byte-identical (`verify-install` is
  the canary; run it before / after if you want proof).

What's deliberately not in v0.1.0:

- A `ds2-smoke` fixture. DS2 boots through the same harness in
  principle (CD-image imgmount is wired); the missing piece is a
  validated DS2 `SOUND.CFG` checked in. Queued for v0.2.0.
- Input automation. Every v0.1.0 bug is timed-window only: did
  DOSBox crash in the budget, did expected sentinel files
  appear? Real bug repros that need keystrokes (the DS2 mines
  elevator etc.) are v0.2.0 work.
- Video capture (`scratch/<bug-id>/repro.mp4`).
- Differential capture (run-with-patch vs run-without-patch).

## Quick start

```
python3 tools/repro/repro.py ds1-smoke
# or
./tools/repro/repro.sh ds1-smoke
```

DOSBox-Staging opens a window on your Wayland (or X) session,
DS1 boots into the main menu, the harness keeps it alive for the
30-second budget, then SIGTERMs the process and reports PASS.

Add `--keep-scratch` to retain `/tmp/repro-<id>-XXXX/` for
post-mortem (`c-overlay/` shows every engine write, `d/` carries
sentinel and log artifacts).

## Requirements

- Fedora 44 (or any Wayland / X Linux) with `dosbox-staging`
  installed and reachable as `dosbox` on `$PATH`. On Fedora
  the binary is `/usr/bin/dosbox` from the `dosbox-staging`
  package.
- A real graphical session. DOSBox-Staging probes OpenGL at
  init; `SDL_VIDEODRIVER=dummy` aborts during config-load and
  there is no headless mode.
- A clean GOG 1.10 install under `.games/ds1/` (and `.games/ds2/`
  for DS2 fixtures). The harness reads from this path; nothing
  is written to it.
- Python 3.11 or newer (the script uses `tomllib`).

## Adding a new bug fixture

1. `mkdir tools/repro/bugs/<bug-id>/`.
2. Write `bug.toml`. The schema:

   ```toml
   id          = "<matches dir name>"
   target_game = "ds1"            # or "ds2"
   description = "..."

   [setup]
   # Files copied from this directory into the C: overlay
   # before launch. `dst` is the DOS-side path inside C:\.
   copy_files = [
     { src = "...", dst = "..." },
   ]

   [trigger]
   # DOS commands the harness runs after mounts. Each becomes
   # one `-c <cmd>` argument to dosbox-staging. The harness
   # always issues the standard mounts and `c:` before these.
   commands = [
     "DSUN.EXE > d:\\dsun.log",
   ]

   [expected]
   timeout_seconds     = 30
   min_runtime_seconds = 25   # null disables the check
   require_files       = []   # globs under D: (must match)
   forbid_files        = []   # globs under D: (must not match)
   ```

3. If the bug needs a save mid-game, drop the `CHARSAVE.GFF` /
   `DARKSAVE.GFF` in this directory and reference them from
   `[setup].copy_files` with `dst = "CHARSAVE.GFF"` (etc.); they
   land in the C: overlay at boot.
4. Run `python3 tools/repro/repro.py <bug-id>` and iterate.

The harness always populates `__support/save/*.GFF` from the
game install into the overlay first, so a bare fixture inherits
the factory saves. Per-fixture `copy_files` entries override on
name collision (factory `DARKSAVE.GFF` will be replaced if your
fixture provides one).

## The audio gotcha (read this before adding a fixture)

DSUN.EXE on both games links the MEL real-mode audio library
(Miles Audio Library, vendor of the modern Miles Sound System).
On launch, MEL reads `SOUND.CFG` and probes for the configured
MIDI and digital devices. With the factory `SOUND.CFG` (shipped
in `.games/ds[12]/SOUND.CFG`, byte-identical to the GOG
installer payload), MEL probes for a Roland MT-32 over MPU-401
and a Sound Blaster Pro DSP. If either probe fails, MEL prints

```
Mel Fatal Error #: 25 Trap #: 16     ; MIDI Detect Fail
Mel Fatal Error #: 26 Trap #: 16     ; DSP Detect Fail
```

and the engine exits. This is the same error family as
[`docs/known-bugs.md`](../../docs/known-bugs.md) §2.6 ("MEL DSP
detect fail").

DOSBox-Staging emulates SB16 + MPU-401, but the factory probe
sequence rejects them. Running `sound_ds.exe` inside DOSBox once
(the real installer flow most players hit) writes a `SOUND.CFG`
that gets MEL through detect. The `ds1-smoke` fixture ships such
a `SOUND.CFG` (originally captured from a Wine-side sound_ds
run, 59 bytes; no game IP, just driver-id + integer settings)
and stages it into the overlay before launch.

If you add a new fixture and see MEL Fatal Errors in
`d/DSUN.LOG`, the fixture is missing `SOUND.CFG` in its
`[setup].copy_files`. Crib the one from `bugs/ds1-smoke/`.

## What the harness does, step by step

1. Loads `bugs/<id>/bug.toml` and validates the schema.
2. Picks `configs/<target_game>.conf`.
3. Creates `/tmp/repro-<id>-XXXX/c-overlay/` and `.../d/`.
4. Copies `<game-dir>/__support/save/*.GFF` into the overlay
   (engine expects them at C:\\ root).
5. Stages every `[setup].copy_files` entry into the overlay.
6. Spawns `dosbox` with:
   - `--nolocalconf --conf configs/<game>.conf` (user's primary
     config inherits; the local `dosbox.conf` does not).
   - `-c "mount c <game-dir>"` + `-c "mount c <overlay> -t overlay"`.
   - `-c "mount d <scratch>/d"`.
   - For DS2: `-c "imgmount e <game-dir>/game.ins -t iso"` for
     the CD-audio cue sheet.
   - `-c "c:"` and one `-c` per `[trigger].commands` entry.
   - `--exit`.
7. Enforces `expected.timeout_seconds` with `subprocess.wait`;
   on timeout, SIGTERMs DOSBox (3-second grace, then SIGKILL).
8. Evaluates `min_runtime_seconds`, `require_files`,
   `forbid_files`. Globs run against `d/` only.
9. Prints PASS / FAIL and tears down the scratch dir unless
   `--keep-scratch` is set.

## Out of scope (and why)

- **DOSBox-X**. Pick one and stay there. Plain DOSBox-Staging
  is what Fedora ships and what Brandon uses; that's the
  contract.
- **Cross-platform**. The harness is Linux-only by spec. macOS /
  Windows ports happen never.
- **CI / headless**. DOSBox-Staging needs a real OpenGL surface;
  the harness is a local-development tool, not a GitHub Actions
  step.
- **Screenshot-based assertions**. v0.2.0+. The roadmap mentions
  `repro.mp4` capture; that lands when we have a real bug that
  needs it.
- **Repro graph / per-bug catalog**. v0.1.0 has one bug. The
  catalogue (cross-linking `bugs/<id>/` to `docs/known-bugs.md`
  entries) is folded into v0.2.0 when there are more than one.
