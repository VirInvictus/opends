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
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REPRO_DIR = Path(__file__).resolve().parent
DEFAULT_BUGS_DIR = REPRO_DIR / "bugs"
DEFAULT_CONFIGS_DIR = REPRO_DIR / "configs"
DEFAULT_GAMES_DIR = REPO_ROOT / ".games"

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


def run_dosbox(cmd: list[str], timeout_seconds: float) -> tuple[int, float, bool]:
    """Launch DOSBox and enforce the wall-clock budget.

    Returns (exit_code, elapsed_seconds, timed_out).
    On timeout, sends SIGTERM, gives DOSBox 3 seconds to clean up,
    then SIGKILLs.
    """
    start = time.monotonic()
    proc = subprocess.Popen(cmd)
    timed_out = False
    try:
        proc.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    elapsed = time.monotonic() - start
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Run an OpenDS repro fixture under DOSBox-Staging.",
    )
    ap.add_argument("bug_id", help="bug fixture id (directory under bugs/)")
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
    args = ap.parse_args(argv)

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
    print(f"  scratch     : {scratch_dir}")

    try:
        overlay_dir = scratch_dir / "c-overlay"
        overlay_dir.mkdir(parents=True, exist_ok=True)
        staged = populate_factory_saves(game_dir, overlay_dir)
        if staged:
            print(f"  factory     : staged {', '.join(staged)} into C:\\")
        stage_setup_files(fixture, overlay_dir)
        cmdline = build_cmdline(fixture, config_path, game_dir, scratch_dir)
        print(f"  dosbox      : {' '.join(cmdline)}")
        print(f"  budget      : {fixture.timeout_seconds:.0f}s")
        print()
        print(f"running {fixture.id}...")
        exit_code, elapsed, timed_out = run_dosbox(
            cmdline, fixture.timeout_seconds
        )
        end_marker = "SIGTERM after timeout" if timed_out else "exit on its own"
        print(
            f"DOSBox finished after {elapsed:.2f}s "
            f"(rc={exit_code}, {end_marker})"
        )
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
