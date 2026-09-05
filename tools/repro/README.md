# repro

- **Version**: see [`VERSION`](VERSION).

Drives a per-bug fixture under `bugs/<id>/` against a working
DOS install, validates pass/fail by elapsed time and scratch-dir
artifacts, and never writes to the game install: the "any bug
reproducible in five minutes" plumbing from

Drives a per-bug fixture under `bugs/<id>/` against a working
DOS install, validates pass/fail by elapsed time and scratch-dir
artifacts, and never writes to the game install. The "any bug
reproducible in five minutes" plumbing from
[`roadmap.md`](../../roadmap.md) Phase 2.

## Input automation and video capture

**Scheduled keystrokes (ydotool) + video capture (ffmpeg).**
A bug fixture can now drive the game with a scripted input
schedule and capture the full run as MP4. The dependent half of
`opcode-fuzz v0.3.0`'s automated discovery loop and the
deterministic-execution piece for any "click through this menu,
then trigger the bug" fixture.

### Scheduled keystrokes

Add a `[[trigger.keystrokes]]` array to `bug.toml`:

```toml
[[trigger.keystrokes]]
at_seconds = 8
send = "Return"            # KEY_ENTER

[[trigger.keystrokes]]
at_seconds = 12
send = "type:dsun"         # type a string

[[trigger.keystrokes]]
at_seconds = 15
send = "16:1 16:0"          # raw KEY_Q press + release
```

`send` accepts:

- Friendly aliases: `Return` / `Enter`, `space`, `Escape` /
  `Esc`, `Tab`.
- `type:<string>` for arbitrary typed input.
- Raw `<code>:<state> <code>:<state> ...` pairs (Linux input
  event codes from `linux/input-event-codes.h`; `1` = press,
  `0` = release).

The scheduler runs as a daemon thread; keystrokes that miss
their window log to `<scratch>/automation.log` but never abort
the run.

### Video capture

Set `record_video = true` in `[expected]`:

```toml
[expected]
timeout_seconds = 30
record_video = true
```

`ffmpeg -f x11grab` captures `$DISPLAY` to
`<scratch>/repro.mp4` (libx264, 24fps, mute, `veryfast`
preset). GNOME-Wayland users get capture via DOSBox-Staging's
XWayland surface automatically; no Wayland-native screencast
portal needed.

### One-time setup (Fedora)

```sh
# ydotool: virtual-input daemon for the Wayland-friendly
# keystroke path. Brandon-approved dep (2026-05-17).
sudo dnf install ydotool
# Run ydotoold as a user systemd unit (ydotool 1.x ships
# this; if your build doesn't, run `sudo ydotoold &`).
systemctl --user enable --now ydotoold

# ffmpeg is already in the toolchain.
sudo dnf install ffmpeg
```

After the first install you may need to log out + back in for
group / udev rules to take effect.

The harness detects both binaries via `$PATH`:

- If `ydotool` is missing or `ydotoold` isn't running,
  keystrokes are skipped with a warning line in
  `automation.log`.
- If `ffmpeg` is missing, video capture is skipped (warning).

The bug run still completes either way; missing automation is
a degraded-mode signal, not a hard fail.

### Output artefacts

In addition to `dosbox.log`, v0.4.0 adds:

- `automation.log`: per-keystroke timestamps and the
  recorder's lifecycle messages.
- `repro.mp4`: captured video (only when
  `record_video = true` and ffmpeg succeeded).

---

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
- **Screenshot-based assertions**. Not built; the video capture
  path records `repro.mp4` when a fixture enables it, but
  pixel-diff assertions remain a maybe.
- **Repro graph / per-bug catalog**. The catalogue
  (cross-linking `bugs/<id>/` to `docs/known-bugs.md` entries)
  grows with the bug count.
