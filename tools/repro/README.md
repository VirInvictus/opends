# repro

DOSBox-Staging repro harness for OpenDS. v0.3.0.

Drives a per-bug fixture under `bugs/<id>/` against a working
DOS install, validates pass/fail by elapsed time and scratch-dir
artifacts, and never writes to the game install. The "any bug
reproducible in five minutes" plumbing from
[`roadmap.md`](../../roadmap.md) Phase 2.

## What v0.3.0 adds

`--play` becomes a real, resumable thing. v0.2.1 invented the
mode but every invocation created a fresh `/tmp/repro-XXXX/`
scratch dir; in-game saves vanished between runs. v0.3.0 adds
session continuity via a stable scratch path under
`$XDG_STATE_HOME` (or `~/.local/state/opends-repro/`).

### `--session <name>` + persistent overlays

`python3 repro.py ds1-smoke --play --session main` always uses
`~/.local/state/opends-repro/play-ds1-main/`. The `c-overlay/`
inside that path holds the C: drive state from every previous
run; in-game saves persist automatically. Default session name
when `--session` is omitted on `--play` is the bug id itself,
so the simplest invocation (`repro.py ds1-smoke --play`) keeps
its own saves.

The harness reports whether the session is `fresh` (just
created) or `resumed` (existing dir reused). Factory-save
staging only fires when the overlay is empty; existing saves
are never overwritten.

### `--list-sessions`

Enumerate every session dir under the state root with its
last-played mtime (the timestamp of the overlay's
`DARKRUN.GFF`, so it tracks the most recent in-game activity
rather than just dir-creation):

```
sessions in /home/.../.local/state/opends-repro:
  play-ds1-main      2026-05-17 16:45
  play-ds2-mines     2026-05-17 15:13
```

### `--reset-session <name>`

Force a fresh start for a session id. Needs a `bug_id`
positional so it can resolve the target game; prompts for
explicit `yes` before deleting.

### Regression mode unchanged

Without `--play`, the harness still uses `tempfile.mkdtemp` so
test runs don't accumulate stale state. Sessions only apply
to `--play`.

### Out of scope (queued for v0.3.x / v0.4.0+)

- **Input automation** (ydotool integration). Requires
  approval to add `ydotool` as a system dep. When added,
  per-fixture `[trigger].keystrokes` lets the harness feed
  in-game keystrokes at scheduled times.
- **Video capture**. Requires a GNOME-Wayland-compatible
  recorder (no wf-recorder on Mutter). Output to
  `<session>/repro.webm`.
- **Differential capture** (run-with-patch vs without).

## What v0.2.1 adds

`--play` mode. Same setup recipe the regression test uses, but
the wall-clock budget is dropped and pass/fail evaluation is
skipped, so you can actually *play* through the harness instead
of just verifying that the engine doesn't crash in 30 seconds.

### Why this exists

A bare `dosbox DSUN.EXE` invocation against the GOG install
hits two engine-side gotchas:

1. **`DARKSAVE.GFF` is not at C:\\**. DSUN.EXE on launch copies
   `C:\DARKSAVE.GFF` -> `C:\DARKRUN.GFF`. GOG ships those files
   under `__support/save/`, so the copy fails and the engine
   exits with `DARKSAVE.GFF to DARKRUN.GFF failed. path = C:\`.
2. **The factory `SOUND.CFG` fails MEL DSP detect**. MEL aborts
   with `Mel Fatal Error #26 trap #16, DSP Detect Fail` (same
   bug family as `docs/known-bugs.md` §2.6) and the engine
   exits inside a second.

The regression harness sidesteps both by staging the factory
saves and a `sound_ds`-generated `SOUND.CFG` into a writable
C: overlay before launching. `--play` reuses that exact recipe
without the timeout enforcement, so the same workaround that
makes the test PASS lets you actually sit at the main menu and
play.

### Usage

```sh
python3 tools/repro/repro.py ds1-smoke --play
python3 tools/repro/repro.py ds2-smoke --play
```

DOSBox opens. You play. Quit the game in-engine; DOSBox closes
itself (the harness keeps `--exit` in the command line, so a
clean DSUN.EXE exit propagates through to DOSBox quitting).

In-game saves land in `<scratch>/c-overlay/CHARSAVE.GFF` and
friends. The harness prints the scratch dir path at the end of
the run and tells you which files to copy out if you want to
keep your progress; the directory itself isn't auto-resumable
(each `--play` invocation creates a fresh scratch dir under
`/tmp`).

### Limitations (intentional, v0.2.1)

- Each run starts from the factory saves staged by
  `populate_factory_saves`. To continue an existing playthrough
  you'd copy your saved `CHARSAVE.GFF` / `DARKRUN.GFF` etc.
  into the bug fixture's directory and add them to the
  fixture's `[setup].copy_files` list (they'll then overlay on
  top of the factory copies on next run). A `--scratch-dir`
  flag for stable session paths is queued for v0.3.0.
- No video / screenshot capture; that's still v0.3.0+ alongside
  input automation.

## What v0.2.0 adds

Quality-of-life on top of the v0.1.0 harness pattern. No new
"shape" features (input automation, video, differential capture
all still v0.3.0+); v0.2.0 is the breadth-and-polish release.

- **`ds2-smoke` fixture**. Mirror of `ds1-smoke` for DS2. Same
  shape: factory saves staged into the C: overlay, a
  `sound_ds`-generated `SOUND.CFG` (newer MEL 2.2.7, same DSP
  Detect Fail story), `DSUN -W0 -L` per RAVAGER.BAT. Boots into
  the WotR main menu, survives 25+ seconds.
- **DOSBox stderr captured to `<scratch>/dosbox.log`**. The
  DOSBox-side log (CONFIG / SDL / MOUNT / MAPPER / RENDER /
  CAPTURE lines) is now an artifact of every run instead of
  inheriting the harness terminal. First place to look when a
  fixture fails for non-MEL reasons.
- **`python3 repro.py --list`**. Enumerates available fixtures
  with target game and one-line description; great for tab-
  completing the next argument.
- **DSUN.LOG preview on early-exit FAIL**. When DOSBox quits on
  its own before the budget, the harness prints the first
  three lines of `<scratch>/d/DSUN.LOG`. MEL Fatal Errors land
  in your face instead of behind a `--keep-scratch` flag.
- **`bugs/README.md` catalogue**. One row per fixture mapping
  to `docs/known-bugs.md` once real-bug fixtures land. The v1
  rows are smokes; future real-bug fixtures join the index as
  they ship.
- **Clearer FAIL line**. "DOSBox quit on its own (game exited
  or never launched)" vs "SIGTERM after timeout (game was
  still running)".

## What v0.1.0 ships

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
