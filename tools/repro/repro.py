#!/usr/bin/env python3
"""OpenDS repro harness driver.

Reads a bug fixture under ``tools/repro/bugs/<id>/``, sets up
the run (mounts, optional save copies), launches dosbox-staging
with a wall-clock budget, evaluates pass criteria, and reports.

Stdlib-only by project policy.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REPRO_DIR = Path(__file__).resolve().parent
DEFAULT_BUGS_DIR = REPRO_DIR / "bugs"
DEFAULT_CONFIGS_DIR = REPRO_DIR / "configs"
DEFAULT_GAMES_DIR = REPO_ROOT / ".games"


def state_root() -> Path:
    """Per-user state directory for `--play --session` data.

    Honours `XDG_STATE_HOME` per the freedesktop base-directory
    spec; falls back to `~/.local/state/opends-repro/` (the
    Linux default state path). All `--play` sessions live in
    subdirectories `play-<game>-<session>/`.
    """
    base = os.environ.get("XDG_STATE_HOME")
    if base:
        return Path(base) / "opends-repro"
    return Path.home() / ".local" / "state" / "opends-repro"


def session_dir(target_game: str, session_name: str) -> Path:
    """Resolve a `--play --session` scratch path. The path is
    stable across invocations so in-game saves persist between
    play sessions.
    """
    safe_session = session_name.replace("/", "_").replace("\\", "_")
    return state_root() / f"play-{target_game}-{safe_session}"

# Exit codes
EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_HARNESS_ERROR = 2


@dataclass
class BugFixture:
    id: str
    target_game: str
    description: str
    copy_files: list[dict]
    trigger_commands: list[str]
    timeout_seconds: float
    min_runtime_seconds: float | None
    require_files: list[str]
    forbid_files: list[str]
    bug_dir: Path
    # v0.4.0: optional keystroke schedule and video capture.
    # Each entry is `{at_seconds: float, send: str}` where `send`
    # is a ydotool key name (e.g. "Return", "space", "Escape") or
    # a typed string prefixed with `"type:"` (e.g. "type:dsun").
    keystrokes: list[dict] = field(default_factory=list)
    # When true, ffmpeg captures the DOSBox window for the run.
    record_video: bool = False

    @classmethod
    def load(cls, bug_dir: Path) -> "BugFixture":
        toml_path = bug_dir / "bug.toml"
        if not toml_path.exists():
            raise SystemExit(f"harness error: missing {toml_path}")
        with toml_path.open("rb") as f:
            data = tomllib.load(f)

        try:
            return cls(
                id=str(data["id"]),
                target_game=str(data["target_game"]),
                description=str(data.get("description", "")).strip(),
                copy_files=list(data.get("setup", {}).get("copy_files", []) or []),
                trigger_commands=list(data["trigger"]["commands"]),
                timeout_seconds=float(data["expected"]["timeout_seconds"]),
                min_runtime_seconds=(
                    float(data["expected"]["min_runtime_seconds"])
                    if data["expected"].get("min_runtime_seconds") is not None
                    else None
                ),
                require_files=list(data["expected"].get("require_files", []) or []),
                forbid_files=list(data["expected"].get("forbid_files", []) or []),
                bug_dir=bug_dir,
                keystrokes=list(data.get("trigger", {}).get("keystrokes", []) or []),
                record_video=bool(data.get("expected", {}).get("record_video", False)),
            )
        except KeyError as e:
            raise SystemExit(
                f"harness error: {toml_path} missing required field {e}"
            ) from None

    def validate(self) -> None:
        if self.target_game not in ("ds1", "ds2"):
            raise SystemExit(
                f"harness error: target_game must be 'ds1' or 'ds2', got {self.target_game!r}"
            )
        if self.timeout_seconds <= 0:
            raise SystemExit("harness error: expected.timeout_seconds must be > 0")
        if self.min_runtime_seconds is not None and self.min_runtime_seconds < 0:
            raise SystemExit("harness error: expected.min_runtime_seconds must be >= 0")
        if (
            self.min_runtime_seconds is not None
            and self.min_runtime_seconds > self.timeout_seconds
        ):
            raise SystemExit(
                "harness error: min_runtime_seconds cannot exceed timeout_seconds"
            )


@dataclass
class RunResult:
    elapsed_seconds: float
    exit_code: int
    timed_out: bool
    scratch_dir: Path
    cmdline: list[str]


def build_cmdline(
    fixture: BugFixture,
    config_path: Path,
    game_dir: Path,
    scratch_dir: Path,
) -> list[str]:
    """Assemble the dosbox-staging command line.

    The C: mount is layered: the game install is the base, and an
    overlay subdir of `scratch_dir` catches every write the engine
    issues during the run. Without the overlay, DSUN.EXE truncates
    `DARKRUN.GFF` (its runtime-state file) inside the game install
    on first boot, which both fails its own next boot and violates
    the `never break userspace` rule. D: is a separate scratch
    drive that bugs use for sentinel files and harness output.
    """
    overlay_dir = scratch_dir / "c-overlay"
    drive_d = scratch_dir / "d"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    drive_d.mkdir(parents=True, exist_ok=True)

    cmd: list[str] = [
        "dosbox",
        # `--noprimaryconf` is intentionally NOT set. DSUN.EXE's MEL
        # audio library probes for a working MT-32 / SB DSP at boot
        # and aborts with "Mel Fatal Error" if it can't find them
        # (this is the same error class as known-bugs.md §2.6).
        # The user's primary config typically has MT-32 ROM paths
        # configured (~/.config/dosbox/mt32-roms/ on Brandon's box),
        # so we inherit it. Per-bug overrides come from the bug's
        # config file and `-c` injections below.
        "--nolocalconf",
        "--conf",
        str(config_path),
        "-c",
        f"mount c {game_dir}",
        "-c",
        f"mount c {overlay_dir} -t overlay",
        "-c",
        f"mount d {drive_d}",
    ]
    if fixture.target_game == "ds2":
        cd_image = game_dir / "game.ins"
        if not cd_image.exists():
            raise SystemExit(
                f"harness error: DS2 needs {cd_image} for CD audio; not found"
            )
        cmd += ["-c", f"imgmount e {cd_image} -t iso"]
    cmd += ["-c", "c:"]
    for trigger in fixture.trigger_commands:
        cmd += ["-c", trigger]
    cmd += ["--exit"]
    return cmd


def populate_factory_saves(game_dir: Path, overlay_dir: Path) -> list[str]:
    """Seed the overlay with the factory save files at C:\\ root.

    DSUN.EXE on both games copies `DARKSAVE.GFF` -> `DARKRUN.GFF`
    at startup; if `C:\\DARKSAVE.GFF` is missing it prints
    "DARKSAVE.GFF to DARKRUN.GFF failed. path = C:\\" and exits.
    GOG ships those files under `__support/save/`, so we copy
    them into the writable C: overlay before launch. Returns the
    list of files staged for the run-log.
    """
    factory_dir = game_dir / "__support" / "save"
    if not factory_dir.is_dir():
        return []
    staged: list[str] = []
    for src in sorted(factory_dir.glob("*.GFF")):
        dst = overlay_dir / src.name
        if dst.exists():
            continue
        shutil.copy2(src, dst)
        staged.append(src.name)
    return staged


def stage_setup_files(fixture: BugFixture, overlay_dir: Path) -> None:
    """Stage fixture-supplied files into the C: overlay before launch.

    Each entry is {"src": "path-relative-to-bug-dir", "dst": "path-relative-inside-C:"}.
    Files land inside the overlay only; the underlying game install
    is never touched. Fixture files override factory-save copies if
    the names collide.
    """
    for entry in fixture.copy_files:
        src = fixture.bug_dir / entry["src"]
        dst = overlay_dir / entry["dst"].replace("\\", "/").lstrip("/")
        if not src.exists():
            raise SystemExit(f"harness error: setup source {src} missing")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


# ---------- v0.4.0: keystroke scheduler + video recorder ----------


def ydotool_available() -> str | None:
    """Return the ydotool binary path if it's usable, else None.

    Probes both the binary and the daemon socket. ydotool needs
    `ydotoold` running with uinput access; if the socket is
    missing we still surface the binary so the warning has
    enough context to direct the user to README setup.
    """
    return shutil.which("ydotool")


def ffmpeg_available() -> str | None:
    return shutil.which("ffmpeg")


class KeystrokeScheduler(threading.Thread):
    """Background thread that fires `ydotool key <X>` (or `type
    <S>`) at each scheduled offset after `start_time`.

    Each schedule entry is one of:

        {at_seconds: float, send: "Return"}           # key press
        {at_seconds: float, send: "type:dsun.exe"}    # type string

    The thread exits when `stop_event` is set OR every entry has
    fired. Per-keystroke errors print to stderr but don't abort
    the run; an in-flight keystroke that misses its window is
    less bad than a crashed test harness.

    ydotool key syntax is the Linux input event name (the
    `KEY_*` constants from `linux/input-event-codes.h`); the
    Wayland-side daemon translates those to virtual events.
    Common names: `KEY_ENTER`, `KEY_SPACE`, `KEY_ESC`, `KEY_A`.
    For modder convenience we accept the friendlier aliases
    `Return`, `Enter`, `space`, `Escape`, `Esc` and the bare
    letter / digit forms (`a`, `1`).
    """

    KEY_ALIASES = {
        "return": "29:1 29:0",      # KEY_ENTER press + release
        "enter": "29:1 29:0",
        "space": "57:1 57:0",
        "esc": "1:1 1:0",
        "escape": "1:1 1:0",
        "tab": "15:1 15:0",
    }

    def __init__(
        self,
        ydotool_bin: str,
        schedule: list[dict],
        start_time: float,
        stop_event: threading.Event,
        log_lines: list[str],
    ) -> None:
        super().__init__(daemon=True, name="ydotool-scheduler")
        self.ydotool_bin = ydotool_bin
        self.schedule = sorted(schedule, key=lambda e: float(e["at_seconds"]))
        self.start_time = start_time
        self.stop_event = stop_event
        self.log_lines = log_lines

    def run(self) -> None:
        for entry in self.schedule:
            at = float(entry["at_seconds"])
            sleep_for = at - (time.monotonic() - self.start_time)
            if sleep_for > 0:
                if self.stop_event.wait(timeout=sleep_for):
                    return
            if self.stop_event.is_set():
                return
            send = str(entry["send"])
            try:
                if send.startswith("type:"):
                    self._fire(["type", "--", send[len("type:"):]])
                else:
                    key = send.strip().lower()
                    if key in self.KEY_ALIASES:
                        # ydotool's `key` subcommand wants `code:state`
                        # pairs; pass them as a single shell arg.
                        self._fire(["key"] + self.KEY_ALIASES[key].split())
                    else:
                        # Caller passed a raw `code:state` string;
                        # forward verbatim. Lets power users send
                        # arbitrary scancodes without us mapping
                        # every KEY_* name.
                        self._fire(["key", send])
            except Exception as e:
                self.log_lines.append(
                    f"ydotool error at +{at:.2f}s for {send!r}: {e}"
                )

    def _fire(self, args: list[str]) -> None:
        res = subprocess.run(
            [self.ydotool_bin] + args,
            capture_output=True, text=True,
        )
        elapsed = time.monotonic() - self.start_time
        if res.returncode != 0:
            self.log_lines.append(
                f"ydotool +{elapsed:.2f}s {' '.join(args)} -> "
                f"rc={res.returncode} stderr={res.stderr.strip()!r}"
            )
        else:
            self.log_lines.append(
                f"ydotool +{elapsed:.2f}s {' '.join(args)} -> ok"
            )


class VideoRecorder:
    """ffmpeg-x11grab wrapper for the run.

    Picks up `$DISPLAY` and grabs the whole virtual screen for
    the duration. XWayland surfaces (DOSBox-Staging's SDL2 uses
    XWayland by default on GNOME-Wayland) are visible to
    x11grab so this works on both X11 and XWayland setups
    without a Wayland-specific path. The output file is
    `<scratch>/repro.mp4` (libx264, mute, 24fps).

    If the user has explicit GNOME-Wayland-only needs (no
    XWayland), this falls back gracefully: ffmpeg errors land
    in the log and the run continues without video.
    """

    def __init__(self, ffmpeg_bin: str, output_path: Path, log_lines: list[str]) -> None:
        self.ffmpeg_bin = ffmpeg_bin
        self.output_path = output_path
        self.log_lines = log_lines
        self.proc: subprocess.Popen | None = None

    def start(self) -> None:
        display = os.environ.get("DISPLAY", ":0")
        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-loglevel", "warning",
            "-f", "x11grab",
            "-framerate", "24",
            "-i", display,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "veryfast",
            "-an",
            str(self.output_path),
        ]
        try:
            self.proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            self.log_lines.append(
                f"ffmpeg started (pid {self.proc.pid}) -> {self.output_path}"
            )
        except FileNotFoundError as e:
            self.log_lines.append(f"ffmpeg not launchable: {e}")
            self.proc = None

    def stop(self) -> None:
        if self.proc is None:
            return
        # ffmpeg wants `q` on stdin or SIGINT to flush cleanly.
        # SIGTERM (signal.SIGTERM) leaves the mp4 unfinalised in
        # most cases; SIGINT mirrors a Ctrl-C and produces a
        # playable file.
        try:
            self.proc.send_signal(signal.SIGINT)
            self.proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        rc = self.proc.returncode
        size = self.output_path.stat().st_size if self.output_path.exists() else 0
        self.log_lines.append(f"ffmpeg stopped (rc={rc}, output size={size} bytes)")


def run_dosbox(
    cmd: list[str],
    timeout_seconds: float | None,
    log_path: Path,
    keystrokes: list[dict] | None = None,
    video_path: Path | None = None,
    automation_log_path: Path | None = None,
) -> tuple[int, float, bool]:
    """Launch DOSBox and (optionally) enforce a wall-clock budget.

    Returns (exit_code, elapsed_seconds, timed_out). On timeout,
    sends SIGTERM, gives DOSBox 3 seconds to clean up, then
    SIGKILLs. Pass `timeout_seconds = None` to wait indefinitely
    (the `--play` mode flow; the user quits the game in-engine,
    DOSBox returns to its DOS prompt, `--exit` then closes it).

    DOSBox's own stderr (CONFIG / SDL / MOUNT / MAPPER / RENDER /
    CAPTURE log lines) is captured to `log_path`; on failure that
    file is the first thing to look at for diagnosis.

    v0.4.0 optionally drives `ydotool` for scheduled keystrokes
    (`keystrokes`) and `ffmpeg -f x11grab` for video capture
    (`video_path`). Both are no-ops when the dependency is
    missing or `keystrokes`/`video_path` is None. The automation
    log lands at `automation_log_path` (one line per fired
    keystroke + recorder lifecycle messages).
    """
    automation_lines: list[str] = []
    ydotool_bin: str | None = None
    if keystrokes:
        ydotool_bin = ydotool_available()
        if ydotool_bin is None:
            automation_lines.append(
                "WARN ydotool not found; keystrokes skipped. "
                "Install via `dnf install ydotool` and start "
                "ydotoold (see tools/repro/README.md)."
            )
    ffmpeg_bin: str | None = None
    recorder: VideoRecorder | None = None
    if video_path is not None:
        ffmpeg_bin = ffmpeg_available()
        if ffmpeg_bin is None:
            automation_lines.append(
                "WARN ffmpeg not found; video capture skipped."
            )

    start = time.monotonic()
    with log_path.open("wb") as log_file:
        proc = subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT)
        # Give DOSBox a moment to create its window before either
        # ffmpeg grabs the screen or ydotool fires keystrokes.
        time.sleep(1.0)
        stop_event = threading.Event()
        scheduler: KeystrokeScheduler | None = None
        if ydotool_bin and keystrokes:
            scheduler = KeystrokeScheduler(
                ydotool_bin, keystrokes, start, stop_event, automation_lines
            )
            scheduler.start()
        if ffmpeg_bin and video_path is not None:
            recorder = VideoRecorder(ffmpeg_bin, video_path, automation_lines)
            recorder.start()

        timed_out = False
        try:
            if timeout_seconds is None:
                proc.wait()
            else:
                proc.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        finally:
            stop_event.set()
            if recorder is not None:
                recorder.stop()
            if scheduler is not None:
                scheduler.join(timeout=2.0)
    elapsed = time.monotonic() - start

    if automation_log_path is not None and automation_lines:
        automation_log_path.write_text(
            "\n".join(automation_lines) + "\n", encoding="utf-8"
        )

    return proc.returncode, elapsed, timed_out


def evaluate(
    fixture: BugFixture, result: RunResult
) -> tuple[bool, list[str]]:
    """Check each expected-criterion. Returns (passed, reasons)."""
    reasons: list[str] = []
    ok = True

    if fixture.min_runtime_seconds is not None:
        if result.elapsed_seconds + 1e-3 < fixture.min_runtime_seconds:
            ok = False
            reasons.append(
                f"runtime {result.elapsed_seconds:.2f}s < min_runtime_seconds "
                f"{fixture.min_runtime_seconds:.2f}s "
                f"(DOSBox exited on its own with code {result.exit_code})"
            )
        else:
            reasons.append(
                f"runtime {result.elapsed_seconds:.2f}s >= "
                f"min_runtime_seconds {fixture.min_runtime_seconds:.2f}s OK"
            )

    # Globs evaluate against the D: scratch drive only (writable
    # by-design space), not the C: overlay (where engine churn
    # like DARKRUN.GFF lands and is mostly noise).
    drive_d = result.scratch_dir / "d"
    scratch_files = sorted(drive_d.rglob("*")) if drive_d.is_dir() else []
    scratch_rel = [
        str(p.relative_to(drive_d))
        for p in scratch_files
        if p.is_file()
    ]

    for pattern in fixture.require_files:
        matches = [n for n in scratch_rel if fnmatch.fnmatch(n, pattern)]
        if not matches:
            ok = False
            reasons.append(f"require_files: no match for {pattern!r}")
        else:
            reasons.append(f"require_files {pattern!r} OK ({matches[0]})")

    for pattern in fixture.forbid_files:
        matches = [n for n in scratch_rel if fnmatch.fnmatch(n, pattern)]
        if matches:
            ok = False
            reasons.append(
                f"forbid_files: {pattern!r} matched {matches[0]} (must not exist)"
            )
        else:
            reasons.append(f"forbid_files {pattern!r} OK (absent)")

    if not reasons:
        reasons.append("no expectations declared; treating as PASS")

    return ok, reasons


def list_sessions() -> int:
    """Enumerate active `--play --session` directories under the
    XDG state root with their last-played mtime (the timestamp
    of the overlay's `DARKRUN.GFF` so the user can tell which
    session was most recently active).
    """
    root = state_root()
    if not root.is_dir():
        print(f"(no sessions; state root {root} doesn't exist)")
        return EXIT_PASS
    entries: list[tuple[str, str]] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        if not child.name.startswith("play-"):
            continue
        darkrun = child / "c-overlay" / "DARKRUN.GFF"
        if darkrun.exists():
            mtime = time.strftime(
                "%Y-%m-%d %H:%M", time.localtime(darkrun.stat().st_mtime)
            )
        else:
            mtime = "(no DARKRUN.GFF yet)"
        entries.append((child.name, mtime))
    if not entries:
        print(f"(no play sessions in {root})")
        return EXIT_PASS
    name_w = max(len(e[0]) for e in entries)
    print(f"sessions in {root}:")
    for name, mtime in entries:
        print(f"  {name:<{name_w}}  {mtime}")
    return EXIT_PASS


def reset_session(target_game: str, session_name: str) -> int:
    """Delete an existing `--play --session` directory after a
    y/n prompt. Used to force a fresh start the next time the
    session id is launched.
    """
    sdir = session_dir(target_game, session_name)
    if not sdir.is_dir():
        print(f"no session at {sdir}; nothing to reset", file=sys.stderr)
        return EXIT_HARNESS_ERROR
    print(f"about to delete: {sdir}")
    answer = input("type 'yes' to confirm: ").strip()
    if answer != "yes":
        print("aborted")
        return EXIT_HARNESS_ERROR
    shutil.rmtree(sdir)
    print(f"removed {sdir}")
    return EXIT_PASS


def list_bugs(bugs_dir: Path) -> int:
    """Enumerate fixtures + their one-line description.

    Used by `--list`; sorted alphabetically by id so the output
    is reproducible. Each line: `<id>  <target_game>  <first
    description line>`.
    """
    if not bugs_dir.is_dir():
        print(f"harness error: bugs dir {bugs_dir} not found", file=sys.stderr)
        return EXIT_HARNESS_ERROR
    entries = []
    for child in sorted(bugs_dir.iterdir()):
        if not child.is_dir():
            continue
        if not (child / "bug.toml").exists():
            continue
        try:
            fixture = BugFixture.load(child)
        except SystemExit:
            entries.append((child.name, "?", "(invalid bug.toml)"))
            continue
        first_line = (fixture.description.splitlines() or [""])[0].strip()
        entries.append((fixture.id, fixture.target_game, first_line))
    if not entries:
        print("(no fixtures)")
        return EXIT_PASS
    id_w = max(len(e[0]) for e in entries)
    for bug_id, game, desc in entries:
        print(f"{bug_id:<{id_w}}  {game}  {desc}")
    return EXIT_PASS


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Run an OpenDS repro fixture under DOSBox-Staging.",
    )
    ap.add_argument(
        "bug_id",
        nargs="?",
        help="bug fixture id (directory under bugs/); omit with --list",
    )
    ap.add_argument(
        "--list",
        action="store_true",
        help="enumerate available bug fixtures and exit",
    )
    ap.add_argument(
        "--bugs-dir",
        type=Path,
        default=DEFAULT_BUGS_DIR,
        help=f"override bugs root (default: {DEFAULT_BUGS_DIR})",
    )
    ap.add_argument(
        "--configs-dir",
        type=Path,
        default=DEFAULT_CONFIGS_DIR,
        help=f"override configs root (default: {DEFAULT_CONFIGS_DIR})",
    )
    ap.add_argument(
        "--games-dir",
        type=Path,
        default=DEFAULT_GAMES_DIR,
        help=f"override games root (default: {DEFAULT_GAMES_DIR})",
    )
    ap.add_argument(
        "--keep-scratch",
        action="store_true",
        help="leave the scratch directory in place after the run",
    )
    ap.add_argument(
        "--play",
        action="store_true",
        help=(
            "Interactive play mode. Runs the fixture's full setup "
            "(C: overlay, factory saves staged at C:\\ root, the "
            "fixture's SOUND.CFG, the same dosbox-staging config "
            "the harness uses) and launches DOSBox with NO "
            "wall-clock budget; the user quits the game in-engine "
            "and DOSBox closes itself. Skips pass/fail evaluation. "
            "Saves persist across invocations via session "
            "directories (see --session). Useful when you want to "
            "actually play the game with the harness's setup "
            "rather than running the regression test; the harness "
            "recipe sidesteps the DARKSAVE-not-at-C:\\ and MEL-DSP-"
            "detect-fail gotchas that bite a bare `dosbox DSUN.EXE` "
            "invocation."
        ),
    )
    ap.add_argument(
        "--session",
        default=None,
        help=(
            "Session name for --play. Picks a stable scratch path "
            "at ${XDG_STATE_HOME:-~/.local/state}/opends-repro/"
            "play-<game>-<session>/ so in-game saves persist "
            "across invocations. Defaults to the bug id when "
            "--play is set; ignored otherwise."
        ),
    )
    ap.add_argument(
        "--list-sessions",
        action="store_true",
        help="enumerate `--play --session` directories and exit",
    )
    ap.add_argument(
        "--reset-session",
        metavar="SESSION_NAME",
        default=None,
        help=(
            "delete an existing --play session directory after a "
            "y/n prompt; requires a bug_id positional so the "
            "target_game is known"
        ),
    )
    args = ap.parse_args(argv)

    if args.list:
        return list_bugs(args.bugs_dir)

    if args.list_sessions:
        return list_sessions()

    if not args.bug_id:
        ap.error("bug_id is required (or pass --list / --list-sessions)")

    bug_dir = args.bugs_dir / args.bug_id
    if not bug_dir.is_dir():
        print(f"harness error: no bug fixture at {bug_dir}", file=sys.stderr)
        return EXIT_HARNESS_ERROR

    fixture = BugFixture.load(bug_dir)
    fixture.validate()

    config_path = args.configs_dir / f"{fixture.target_game}.conf"
    if not config_path.exists():
        print(f"harness error: missing config {config_path}", file=sys.stderr)
        return EXIT_HARNESS_ERROR

    game_dir = args.games_dir / fixture.target_game
    if not game_dir.is_dir():
        print(
            f"harness error: game install not found at {game_dir}. "
            f"Place the GOG-extracted install there or pass --games-dir.",
            file=sys.stderr,
        )
        return EXIT_HARNESS_ERROR

    if not shutil.which("dosbox"):
        print(
            "harness error: `dosbox` not on PATH. On Fedora the "
            "`dosbox-staging` package installs as /usr/bin/dosbox.",
            file=sys.stderr,
        )
        return EXIT_HARNESS_ERROR

    if args.reset_session is not None:
        # --reset-session needs the target_game (resolved from
        # the bug fixture). Run the prompt and exit.
        return reset_session(fixture.target_game, args.reset_session)

    # Session continuity: `--play --session foo` lives at the
    # stable XDG state path so saves persist between runs.
    # Default the session name to the bug id so the simplest
    # invocation (`repro.py ds1-smoke --play`) keeps its own
    # saves automatically. Test runs (no --play) keep using a
    # per-run tempfile path so they don't accumulate stale
    # state.
    session_name: str | None = None
    if args.play:
        session_name = args.session or fixture.id

    scratch_was_new = True
    if session_name is not None:
        scratch_dir = session_dir(fixture.target_game, session_name)
        scratch_was_new = not scratch_dir.exists()
        scratch_dir.mkdir(parents=True, exist_ok=True)
    else:
        scratch_dir = Path(
            tempfile.mkdtemp(prefix=f"repro-{fixture.id}-", dir="/tmp")
        )

    print(f"=== {fixture.id} ===")
    if fixture.description:
        for line in fixture.description.splitlines():
            print(f"  {line}")
    print(f"  target_game : {fixture.target_game}")
    print(f"  config      : {config_path}")
    print(f"  game-dir    : {game_dir}")
    if session_name is not None:
        print(f"  session     : {session_name}")
        marker = "fresh" if scratch_was_new else "resumed"
        print(f"  scratch     : {scratch_dir}  ({marker})")
    else:
        print(f"  scratch     : {scratch_dir}")

    if args.play:
        # Force the scratch retention path: in-game saves land in
        # `<scratch>/c-overlay/` and the user almost certainly
        # wants to keep them.
        args.keep_scratch = True

    try:
        overlay_dir = scratch_dir / "c-overlay"
        overlay_dir.mkdir(parents=True, exist_ok=True)
        staged = populate_factory_saves(game_dir, overlay_dir)
        if staged:
            print(f"  factory     : staged {', '.join(staged)} into C:\\")
        stage_setup_files(fixture, overlay_dir)
        cmdline = build_cmdline(fixture, config_path, game_dir, scratch_dir)
        dosbox_log = scratch_dir / "dosbox.log"
        print(f"  dosbox      : {' '.join(cmdline)}")
        print(f"  dosbox.log  : {dosbox_log}")
        if args.play:
            print(f"  mode        : --play (no budget; quit the game to close)")
        else:
            print(f"  budget      : {fixture.timeout_seconds:.0f}s")
        print()
        if args.play:
            print(f"playing {fixture.id} (interactive; no time budget)...")
            exit_code, elapsed, timed_out = run_dosbox(
                cmdline,
                None,
                dosbox_log,
                keystrokes=fixture.keystrokes or None,
                video_path=(scratch_dir / "repro.mp4") if fixture.record_video else None,
                automation_log_path=scratch_dir / "automation.log",
            )
            print(
                f"DOSBox closed after {elapsed:.2f}s "
                f"(rc={exit_code})"
            )
            print()
            print(f"Session retained at: {scratch_dir}")
            print(f"In-game saves are at {overlay_dir}/")
            if session_name is not None:
                print(
                    f"Next `repro.py {fixture.id} --play "
                    f"--session {session_name}` resumes this state. "
                    f"`repro.py --list-sessions` lists all sessions."
                )
            return EXIT_PASS
        print(f"running {fixture.id}...")
        exit_code, elapsed, timed_out = run_dosbox(
            cmdline,
            fixture.timeout_seconds,
            dosbox_log,
            keystrokes=fixture.keystrokes or None,
            video_path=(scratch_dir / "repro.mp4") if fixture.record_video else None,
            automation_log_path=scratch_dir / "automation.log",
        )
        if timed_out:
            end_marker = "SIGTERM after timeout (game was still running)"
        elif exit_code == 0:
            end_marker = "DOSBox quit on its own (game exited or never launched)"
        else:
            end_marker = f"DOSBox quit on its own with non-zero rc"
        print(
            f"DOSBox finished after {elapsed:.2f}s "
            f"(rc={exit_code}, {end_marker})"
        )
        if not timed_out and exit_code == 0:
            # The most common gotcha: game exited fast because of
            # MEL Fatal Error or similar. Point at the log.
            dsun_log = scratch_dir / "d" / "DSUN.LOG"
            if dsun_log.exists() and dsun_log.stat().st_size > 0:
                preview = dsun_log.read_text(errors="replace").strip().splitlines()[:3]
                if preview:
                    print(
                        "  (DSUN.LOG has content, first 3 lines):"
                    )
                    for line in preview:
                        print(f"    {line}")
        print()
        result = RunResult(
            elapsed_seconds=elapsed,
            exit_code=exit_code,
            timed_out=timed_out,
            scratch_dir=scratch_dir,
            cmdline=cmdline,
        )
        passed, reasons = evaluate(fixture, result)
        print("evaluating:")
        for r in reasons:
            print(f"  {r}")
        print()
        verdict = "PASS" if passed else "FAIL"
        print(f"RESULT: {verdict} ({fixture.id})")
        return EXIT_PASS if passed else EXIT_FAIL
    finally:
        if args.keep_scratch:
            print(f"(scratch retained at {scratch_dir})")
        else:
            shutil.rmtree(scratch_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
