#!/usr/bin/env python3
"""OpenDS opcode-fuzz harness.

v0.1.0 ships the **chunk-patchwork pipeline** that opcode-fuzz
needs to build on: extract a GPL chunk into a work directory,
edit its disassembly, repack it back into the GFF. Plus a
corpus-level round-trip self-test that verifies every chunk in
a GFF survives extract -> disasm -> reasm -> replace
byte-identical.

The eventual Phase 5 vision (DOSBox debugger IPC, per-tick
state capture, opcode-discovery loop per roadmap.md Phase 5) is
queued for v0.2.0+. This version is the foundation those
versions build on, not the discovery loop itself.

Shells out to:

- `target/release/gff-cat` (gff-edit's CLI) for GFF I/O.
- `target/release/gpl-disasm` for byte -> JSON / text.
- `target/release/gpl-asm` for JSON / text -> byte.

Stdlib-only; no third-party Python deps.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HERE = Path(__file__).resolve().parent
VERSION = (HERE / "VERSION").read_text().strip()

GFF_CAT = REPO_ROOT / "target" / "release" / "gff-cat"
GPL_DISASM = REPO_ROOT / "target" / "release" / "gpl-disasm"
GPL_ASM = REPO_ROOT / "target" / "release" / "gpl-asm"
REPRO_DIR = REPO_ROOT / "tools" / "repro"
REPRO_PY = REPRO_DIR / "repro.py"

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_HARNESS_ERROR = 2


def require_built() -> None:
    """Bail if the Rust binaries we depend on aren't built."""
    missing = [
        p
        for p in (GFF_CAT, GPL_DISASM, GPL_ASM)
        if not p.is_file()
    ]
    if missing:
        names = ", ".join(p.name for p in missing)
        raise SystemExit(
            f"opcode-fuzz: missing release binaries ({names}). "
            "Run `cargo build --release` from the repo root."
        )


def is_script_chunk(kind: str) -> bool:
    """Returns True for chunk kinds that hold GPL bytecode.

    `GPL ` and `MAS ` are the two; both have trailing-space
    FOURCCs. gpl-disasm handles them identically.
    """
    return kind in ("GPL ", "MAS ")


@dataclass
class ChunkRef:
    kind: str
    id: int

    def safe_name(self) -> str:
        """Filename-safe rendering of `<kind>-<id>`."""
        clean_kind = self.kind.strip().replace(" ", "_")
        return f"{clean_kind}-{self.id}"


def list_chunks(gff: Path) -> list[ChunkRef]:
    """Run `gff-cat list <gff>` and parse the output.

    Output looks like:
        kind            id      offset      length
        'GFFI'           0     1370114          12
        'GPL '           1     1363280        6834
        'MAS '           2      877556         371

    Kind is wrapped in single quotes and may carry a trailing
    space inside the quotes (4 chars total). Subsequent
    columns are space-separated.
    """
    result = subprocess.run(
        [str(GFF_CAT), "list", str(gff)],
        capture_output=True,
        text=True,
        check=True,
    )
    out: list[ChunkRef] = []
    for raw in result.stdout.splitlines():
        line = raw.lstrip()
        if not line.startswith("'"):
            continue
        # Find the matching close-quote 5 bytes after the open
        # (4-char FOURCC + the close-quote).
        if len(line) < 6 or line[5] != "'":
            continue
        kind = line[1:5]
        rest = line[6:].strip()
        parts = rest.split()
        if not parts:
            continue
        try:
            chunk_id = (
                int(parts[0], 16) if parts[0].startswith("0x") else int(parts[0])
            )
        except ValueError:
            continue
        out.append(ChunkRef(kind=kind, id=chunk_id))
    return out


def extract_chunk(gff: Path, ref: ChunkRef, out_path: Path) -> None:
    """Extract a single chunk's bytes to `out_path`."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            str(GFF_CAT),
            "extract",
            str(gff),
            ref.kind,
            str(ref.id),
            "-o",
            str(out_path),
        ],
        check=True,
    )


def disasm_to_json(gff: Path, ref: ChunkRef, out_path: Path) -> None:
    """Disassemble a single chunk from a GFF to JSON."""
    subprocess.run(
        [
            str(GPL_DISASM),
            str(gff),
            "--kind",
            ref.kind.strip(),
            "--id",
            str(ref.id),
            "--json",
            "-o",
            str(out_path),
        ],
        check=True,
    )


def disasm_to_text(gff: Path, ref: ChunkRef, out_path: Path) -> None:
    """Disassemble a single chunk from a GFF to text listing."""
    subprocess.run(
        [
            str(GPL_DISASM),
            str(gff),
            "--kind",
            ref.kind.strip(),
            "--id",
            str(ref.id),
            "-o",
            str(out_path),
        ],
        check=True,
    )


def asm_from_json(json_path: Path, out_path: Path) -> None:
    subprocess.run(
        [str(GPL_ASM), str(json_path), "-o", str(out_path)],
        check=True,
    )


def replace_chunk(
    gff: Path, ref: ChunkRef, bytes_path: Path, out_gff: Path
) -> None:
    subprocess.run(
        [
            str(GFF_CAT),
            "replace",
            str(gff),
            ref.kind,
            str(ref.id),
            str(bytes_path),
            "-o",
            str(out_gff),
        ],
        check=True,
    )


def cmd_extract(args: argparse.Namespace) -> int:
    """Stage a chunk for editing.

    Output directory layout (created at `--output`):
        original.bin   exact chunk bytes; reference for diff
        chunk.json     gpl-disasm JSON; edit this for surgical changes
        chunk.asm      gpl-disasm text listing; edit for hand-written work
        meta.json      {"gff": "...", "kind": "...", "id": N}
    """
    require_built()
    ref = ChunkRef(kind=args.kind, id=args.id)
    work_dir = args.output
    work_dir.mkdir(parents=True, exist_ok=True)
    chunk_bin = work_dir / "original.bin"
    extract_chunk(args.gff, ref, chunk_bin)
    disasm_to_json(args.gff, ref, work_dir / "chunk.json")
    disasm_to_text(args.gff, ref, work_dir / "chunk.asm")
    meta = {
        "gff": str(args.gff.resolve()),
        "kind": ref.kind,
        "id": ref.id,
    }
    (work_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(
        f"extracted {ref.kind!r}/{ref.id} from {args.gff}\n"
        f"  work-dir: {work_dir}\n"
        f"  edit chunk.json or chunk.asm; then `opcode-fuzz pack {work_dir} -o <new.gff>`"
    )
    return EXIT_OK


def cmd_pack(args: argparse.Namespace) -> int:
    """Rebuild a GFF from an edited work-dir.

    Reads `meta.json` to find the source GFF and the chunk
    coordinate, encodes the (possibly edited) `chunk.json` via
    gpl-asm, and writes the resulting GFF to `--output`. The
    original chunk's bytes are left in `original.bin` for diff.
    """
    require_built()
    meta_path = args.work_dir / "meta.json"
    if not meta_path.is_file():
        print(f"opcode-fuzz: no meta.json at {meta_path}", file=sys.stderr)
        return EXIT_HARNESS_ERROR
    meta = json.loads(meta_path.read_text())
    ref = ChunkRef(kind=meta["kind"], id=int(meta["id"]))
    source_gff = args.source_gff or Path(meta["gff"])
    if not source_gff.is_file():
        print(
            f"opcode-fuzz: source GFF {source_gff} not found "
            f"(meta.json points at {meta['gff']!r}; pass --source-gff to override)",
            file=sys.stderr,
        )
        return EXIT_HARNESS_ERROR
    chunk_json = args.work_dir / "chunk.json"
    if not chunk_json.is_file():
        print(f"opcode-fuzz: no chunk.json at {chunk_json}", file=sys.stderr)
        return EXIT_HARNESS_ERROR
    with tempfile.TemporaryDirectory(prefix="opcode-fuzz-pack-") as tmp:
        new_bin = Path(tmp) / "chunk.bin"
        asm_from_json(chunk_json, new_bin)
        replace_chunk(source_gff, ref, new_bin, args.output)
    print(f"packed -> {args.output}")
    return EXIT_OK


def repro_session_dir(target_game: str, session_name: str) -> Path:
    """Mirror of `repro.session_dir`. Keeps opcode-fuzz independent
    of how repro is packaged while honouring the same XDG state
    layout so `--list-sessions` finds these too.
    """
    base = os.environ.get("XDG_STATE_HOME")
    if base:
        root = Path(base) / "opends-repro"
    else:
        root = Path.home() / ".local" / "state" / "opends-repro"
    safe = session_name.replace("/", "_").replace("\\", "_")
    return root / f"play-{target_game}-{safe}"


def infer_target_game(gff_path: Path) -> str | None:
    """Best-effort: pull `ds1` / `ds2` out of the GFF path. The
    standard layout is `.games/ds1/GPLDATA.GFF` /
    `.games/ds2/GPLDATA.GFF`, so this is usually unambiguous.
    """
    parts = gff_path.resolve().parts
    for p in parts:
        if p in ("ds1", "ds2"):
            return p
    return None


def gff_replace(
    gff: Path, kind: str, id_: int, bytes_path: Path, out_gff: Path
) -> None:
    """Wrap `gff-cat replace` against an explicit kind / id (the
    `replace_chunk` helper takes a ChunkRef; this one is called
    from `cmd_run` where we already have the kind / id in hand)."""
    subprocess.run(
        [
            str(GFF_CAT),
            "replace",
            str(gff),
            kind,
            str(id_),
            str(bytes_path),
            "-o",
            str(out_gff),
        ],
        check=True,
    )


def synthesise_fixture(
    work_dir: Path,
    target_game: str,
    patched_gff: Path,
    fixture_root: Path,
) -> tuple[Path, str]:
    """Build a temporary repro bug fixture rooted at
    `fixture_root / opcode-fuzz`. The fixture stages the patched
    GPLDATA.GFF on top of the factory install via the standard
    `[setup].copy_files` path. SOUND.CFG is cribbed from the
    matching `ds[12]-smoke` fixture (the sound_ds-derived file
    that gets MEL through detect).

    Returns the (fixture_dir, fixture_id) pair so the caller can
    pass `--bugs-dir <fixture_root> <fixture_id>` to repro.py.
    """
    smoke_dir = REPRO_DIR / "bugs" / f"{target_game}-smoke"
    sound_cfg_src = smoke_dir / "SOUND.CFG"
    if not sound_cfg_src.is_file():
        raise SystemExit(
            f"opcode-fuzz: no SOUND.CFG at {sound_cfg_src}; "
            f"opcode-fuzz needs the {target_game}-smoke fixture to "
            "crib audio config from."
        )

    fixture_id = "opcode-fuzz"
    fdir = fixture_root / fixture_id
    fdir.mkdir(parents=True, exist_ok=True)

    # Copy the patched GFF + SOUND.CFG into the fixture dir so
    # [setup].copy_files can stage them.
    fixture_gff = fdir / "GPLDATA.GFF"
    fixture_sound = fdir / "SOUND.CFG"
    shutil.copy2(patched_gff, fixture_gff)
    shutil.copy2(sound_cfg_src, fixture_sound)

    trigger_cmd = "DSUN -W0 -L > d:\\dsun.log" if target_game == "ds2" else "DSUN.EXE > d:\\dsun.log"
    bug_toml = f"""# Synthesised by opcode-fuzz from {work_dir}
# This fixture replaces GPLDATA.GFF with a patched version
# carrying the modified chunk; the harness mounts it via the
# standard `[setup].copy_files` path, so the original install
# stays untouched.

id          = "{fixture_id}"
target_game = "{target_game}"
description = "opcode-fuzz synthesised fixture (patched GPLDATA.GFF)"

[setup]
copy_files = [
  {{ src = "GPLDATA.GFF", dst = "GPLDATA.GFF" }},
  {{ src = "SOUND.CFG",   dst = "SOUND.CFG" }},
]

[trigger]
commands = [
  "{trigger_cmd}",
]

[expected]
# Generous budget; `--play` ignores it anyway. Used only if the
# user invokes the fixture without --play (regression mode).
timeout_seconds     = 120
min_runtime_seconds = 0
require_files       = []
forbid_files        = []
"""
    (fdir / "bug.toml").write_text(bug_toml)
    return fdir, fixture_id


def snapshot_darkrun(path: Path) -> bytes | None:
    """Read DARKRUN.GFF bytes if present, else None."""
    if not path.is_file():
        return None
    return path.read_bytes()


def diff_darkrun(pre: bytes | None, post: bytes | None) -> dict:
    """Byte-level summary of pre/post DARKRUN.GFF. Counts bytes
    that differ + lists the offsets of the first 10 differing
    bytes. For richer structural diff users can shell to
    `save-inspect diff` against the snapshotted files.
    """
    if pre is None and post is None:
        return {"status": "no_pre_no_post"}
    if pre is None:
        return {"status": "no_pre_only_post", "post_bytes": len(post)}
    if post is None:
        return {"status": "no_post_only_pre", "pre_bytes": len(pre)}
    if pre == post:
        return {"status": "identical", "bytes": len(pre)}
    n = max(len(pre), len(post))
    diff_offsets: list[int] = []
    same = 0
    for i in range(n):
        a = pre[i] if i < len(pre) else None
        b = post[i] if i < len(post) else None
        if a == b:
            same += 1
        else:
            if len(diff_offsets) < 10:
                diff_offsets.append(i)
    return {
        "status": "changed",
        "pre_bytes": len(pre),
        "post_bytes": len(post),
        "bytes_same": same,
        "bytes_different": n - same,
        "first_diff_offsets": diff_offsets,
    }


def cmd_run(args: argparse.Namespace) -> int:
    """Pack a work-dir, stage it as a synthesised repro fixture,
    launch DOSBox via `repro.py --play --session`, snapshot
    DARKRUN.GFF before and after, emit a JSON state diff.

    The session continuity inherited from repro v0.3.0 means the
    session dir persists between invocations. `--reset-session`
    forces a fresh-from-factory start; without it, each run
    builds on the prior run's state (useful for iterative
    fuzzing of an already-running playthrough).
    """
    require_built()
    if not REPRO_PY.is_file():
        print(f"opcode-fuzz: missing {REPRO_PY}", file=sys.stderr)
        return EXIT_HARNESS_ERROR

    meta_path = args.work_dir / "meta.json"
    if not meta_path.is_file():
        print(f"opcode-fuzz: no meta.json at {meta_path}", file=sys.stderr)
        return EXIT_HARNESS_ERROR
    meta = json.loads(meta_path.read_text())
    chunk_json = args.work_dir / "chunk.json"
    if not chunk_json.is_file():
        print(f"opcode-fuzz: no chunk.json at {chunk_json}", file=sys.stderr)
        return EXIT_HARNESS_ERROR

    source_gff = Path(meta["gff"])
    if not source_gff.is_file():
        print(f"opcode-fuzz: source GFF {source_gff} not found", file=sys.stderr)
        return EXIT_HARNESS_ERROR
    target_game = args.target_game or infer_target_game(source_gff)
    if target_game not in ("ds1", "ds2"):
        print(
            f"opcode-fuzz: couldn't infer target_game from {source_gff}; "
            "pass --target-game ds1|ds2",
            file=sys.stderr,
        )
        return EXIT_HARNESS_ERROR

    session_name = args.session or f"opcode-fuzz-{args.work_dir.name}"

    with tempfile.TemporaryDirectory(prefix="opcode-fuzz-run-") as tmp:
        tmp_root = Path(tmp)
        # 1. Encode the chunk via gpl-asm (validator runs).
        new_bin = tmp_root / "chunk.bin"
        asm_from_json(chunk_json, new_bin)
        # 2. Replace in a copy of the source GFF.
        patched = tmp_root / "patched.gff"
        gff_replace(
            source_gff, meta["kind"], int(meta["id"]), new_bin, patched
        )
        # 3. Synthesise a repro fixture.
        bugs_root = tmp_root / "bugs"
        bugs_root.mkdir(parents=True, exist_ok=True)
        fdir, fixture_id = synthesise_fixture(
            args.work_dir, target_game, patched, bugs_root
        )

        # 4. Pre-snapshot of DARKRUN.GFF: take from the existing
        # session dir if present, else from the factory location.
        # We compute the session path the same way repro v0.3.0
        # does (XDG-aware) so `repro --list-sessions` finds the
        # session we create.
        sdir = repro_session_dir(target_game, session_name)
        overlay_darkrun = sdir / "c-overlay" / "DARKRUN.GFF"
        factory_darkrun = source_gff.parent / "__support" / "save" / "DARKRUN.GFF"
        if overlay_darkrun.is_file():
            pre_bytes = snapshot_darkrun(overlay_darkrun)
            pre_source = str(overlay_darkrun)
        elif factory_darkrun.is_file():
            pre_bytes = snapshot_darkrun(factory_darkrun)
            pre_source = str(factory_darkrun)
        else:
            pre_bytes = None
            pre_source = None

        # 5. Invoke repro.py --play --session.
        repro_argv = [
            "python3",
            str(REPRO_PY),
            fixture_id,
            "--play",
            "--session",
            session_name,
            "--bugs-dir",
            str(bugs_root),
        ]
        print(f"opcode-fuzz: launching repro with synthesised fixture")
        print(f"  work-dir       : {args.work_dir}")
        print(f"  source GFF     : {source_gff}")
        print(f"  patched chunk  : {meta['kind']!r}/{meta['id']}")
        print(f"  target_game    : {target_game}")
        print(f"  session        : {session_name}")
        if pre_source is not None:
            print(f"  pre-snapshot   : {pre_source} ({len(pre_bytes)} bytes)")
        else:
            print(f"  pre-snapshot   : (no factory or session DARKRUN.GFF)")
        print()
        rc = subprocess.run(repro_argv).returncode
        print()

        # 6. Post-snapshot of DARKRUN.GFF from the session dir.
        post_bytes = snapshot_darkrun(overlay_darkrun)
        diff = diff_darkrun(pre_bytes, post_bytes)
        diff["session_dir"] = str(sdir)
        diff["target_game"] = target_game
        diff["chunk"] = {"kind": meta["kind"], "id": int(meta["id"])}
        diff["repro_rc"] = rc

        print(f"opcode-fuzz: DARKRUN.GFF diff:")
        print(json.dumps(diff, indent=2))
        return EXIT_OK if rc == 0 else EXIT_FAIL


def cmd_roundtrip(args: argparse.Namespace) -> int:
    """End-to-end self-test on a GFF.

    For every GPL / MAS chunk in the input GFF:
      1. Extract bytes (gff-cat extract).
      2. Disassemble to JSON (gpl-disasm).
      3. Reassemble to bytes (gpl-asm).
      4. Replace the chunk in the GFF (gff-cat replace).
      5. Verify the resulting GFF byte-equals the input.

    Three things this catches:
      - gpl-disasm / gpl-asm round-trip regressions on a real
        GFF (the gpl-asm corpus test already covers this against
        chunks-in-isolation; this exercises the full GFF path).
      - gff-cat replace regressions (chunk relocation, TOC
        rewrite, etc).
      - Any non-aligned / unencodable chunk that the per-chunk
        tests skip but would surface here as a mismatch.
    """
    require_built()
    src = args.gff
    if not src.is_file():
        print(f"opcode-fuzz: {src} not found", file=sys.stderr)
        return EXIT_HARNESS_ERROR

    chunks = [c for c in list_chunks(src) if is_script_chunk(c.kind)]
    if not chunks:
        print(f"no GPL / MAS chunks in {src}", file=sys.stderr)
        return EXIT_OK

    src_bytes = src.read_bytes()
    print(f"roundtrip: {len(chunks)} chunks in {src}")

    mismatched: list[str] = []
    skipped: list[str] = []
    encode_failures: list[str] = []
    tested = 0

    with tempfile.TemporaryDirectory(prefix="opcode-fuzz-rt-") as tmp:
        tmp_root = Path(tmp)
        for ref in chunks:
            slot = tmp_root / ref.safe_name()
            slot.mkdir(parents=True, exist_ok=True)
            chunk_json = slot / "chunk.json"
            new_bin = slot / "rebuilt.bin"
            new_gff = slot / "patched.gff"
            try:
                disasm_to_json(src, ref, chunk_json)
            except subprocess.CalledProcessError:
                skipped.append(ref.safe_name())
                continue
            # gpl-asm refuses to encode non-aligned chunks
            # (the disassembler couldn't reach instruction
            # boundaries). Skip those explicitly so they don't
            # show up as encode failures.
            try:
                meta = json.loads(chunk_json.read_text())
            except json.JSONDecodeError:
                skipped.append(ref.safe_name())
                continue
            if not meta.get("aligned", True):
                skipped.append(ref.safe_name() + " (non-aligned)")
                continue
            try:
                asm_from_json(chunk_json, new_bin)
            except subprocess.CalledProcessError:
                encode_failures.append(ref.safe_name())
                continue
            try:
                replace_chunk(src, ref, new_bin, new_gff)
            except subprocess.CalledProcessError:
                encode_failures.append(ref.safe_name() + " (replace)")
                continue
            tested += 1
            if new_gff.read_bytes() != src_bytes:
                mismatched.append(ref.safe_name())

    print(
        f"  tested={tested}  matched={tested - len(mismatched)}  "
        f"mismatched={len(mismatched)}  encode_failures={len(encode_failures)}  "
        f"skipped={len(skipped)}"
    )
    if mismatched:
        print("  first 5 mismatches:")
        for s in mismatched[:5]:
            print(f"    {s}")
    if encode_failures:
        print("  first 5 encode failures:")
        for s in encode_failures[:5]:
            print(f"    {s}")
    if skipped:
        print(f"  ({len(skipped)} non-aligned / non-encodable chunks skipped)")

    return EXIT_OK if not mismatched and not encode_failures else EXIT_FAIL


def cmd_boot_chunks(args: argparse.Namespace) -> int:
    """Identify GPL chunks the engine invokes "from the outside."

    A chunk is a boot-chunk candidate iff nothing else in the GFF
    calls it via `gpl global sub` (0x14). Those chunks are pure
    entry points: the engine's main loop must dispatch them
    directly (since no other chunk does). Whenever the fuzz
    harness needs a chunk to swap out, a boot-chunk is the
    safest target because the engine guarantees it'll fire.

    Drives `gpl-disasm --global-cfg --json` against the input
    GFF, parses the resulting CFG, and reports the inbound-edge
    count for every chunk. Output is JSON for downstream
    consumption (the future `fuzz --auto-pick` path) plus a
    summary line on stderr.
    """
    require_built()
    gff: Path = args.gff
    if not gff.is_file():
        print(f"opcode-fuzz: {gff} not found", file=sys.stderr)
        return EXIT_HARNESS_ERROR

    with tempfile.TemporaryDirectory(prefix="opcode-fuzz-cfg-") as tmp:
        out_path = Path(tmp) / "gcfg.json"
        try:
            subprocess.run(
                [
                    str(GPL_DISASM), str(gff),
                    "--global-cfg", str(out_path),
                    "--json",
                ],
                check=True, capture_output=True, text=True,
            )
        except subprocess.CalledProcessError as e:
            print(f"opcode-fuzz: gpl-disasm --global-cfg failed: {e.stderr}",
                  file=sys.stderr)
            return EXIT_HARNESS_ERROR
        gcfg = json.loads(out_path.read_text())

    # gpl-disasm --global-cfg already counts inbound / outbound
    # per node, so we just read those directly.
    boot_candidates: list[dict] = []
    callable_chunks: list[dict] = []
    for node in gcfg.get("nodes", []):
        row = {
            "kind": node["kind"],
            "chunk_id": node["chunk_id"],
            "inbound_calls": int(node.get("inbound_calls", 0)),
            "outbound_calls": int(node.get("outbound_calls", 0)),
            "entry_count": int(node.get("entry_count", 0)),
            "block_count": int(node.get("block_count", 0)),
        }
        if row["inbound_calls"] == 0:
            boot_candidates.append(row)
        else:
            callable_chunks.append(row)

    boot_candidates.sort(key=lambda r: (r["kind"], r["chunk_id"]))
    callable_chunks.sort(key=lambda r: (-r["inbound_calls"], r["kind"], r["chunk_id"]))

    report = {
        "tool": "opcode-fuzz",
        "version": VERSION,
        "mode": "boot-chunks",
        "gff": str(gff),
        "summary": {
            "node_count": len(gcfg.get("nodes", [])),
            "edge_count": len(gcfg.get("edges", [])),
            "boot_candidate_count": len(boot_candidates),
        },
        "boot_candidates": boot_candidates,
        "most_called": callable_chunks[:20],
    }
    print(json.dumps(report, indent=2))
    print(
        f"opcode-fuzz boot-chunks: {len(boot_candidates)} entry-point "
        f"candidates out of {len(gcfg.get('nodes', []))} chunks "
        f"({len(gcfg.get('edges', []))} edges in the global CFG)",
        file=sys.stderr,
    )
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="OpenDS opcode-fuzz harness (v0.3.0: chunk-patchwork + boot-chunks)."
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_ext = sub.add_parser(
        "extract",
        help="Stage a chunk for editing.",
        description=(
            "Extract a single GPL / MAS chunk into a work "
            "directory ready for surgical edits. Produces "
            "original.bin + chunk.json + chunk.asm + meta.json."
        ),
    )
    p_ext.add_argument("gff", type=Path, help="source GFF file")
    p_ext.add_argument("kind", help="chunk kind (e.g. 'GPL ' with trailing space, or 'MAS ')")
    p_ext.add_argument("id", type=int, help="chunk id (decimal)")
    p_ext.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="work directory to populate",
    )
    p_ext.set_defaults(handler=cmd_extract)

    p_pack = sub.add_parser(
        "pack",
        help="Re-encode an edited work-dir and write the patched GFF.",
        description=(
            "Reads meta.json from the work-dir, encodes chunk.json "
            "via gpl-asm, replaces the chunk in the source GFF, "
            "writes the result to --output."
        ),
    )
    p_pack.add_argument("work_dir", type=Path, help="work directory from `extract`")
    p_pack.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="output GFF path",
    )
    p_pack.add_argument(
        "--source-gff",
        type=Path,
        default=None,
        help="override the source GFF (defaults to meta.json's `gff`)",
    )
    p_pack.set_defaults(handler=cmd_pack)

    p_rt = sub.add_parser(
        "roundtrip",
        help="Corpus self-test: every GPL/MAS chunk extracts + reassembles + replaces back byte-identical.",
    )
    p_rt.add_argument("gff", type=Path, help="GFF to round-trip")
    p_rt.set_defaults(handler=cmd_roundtrip)

    p_run = sub.add_parser(
        "run",
        help="Pack a work-dir, stage it as a synthesised repro fixture, launch DOSBox via repro.py --play --session, snapshot DARKRUN.GFF pre/post, emit a state diff.",
        description=(
            "Pack the edited chunk in <work-dir> back into the "
            "source GFF, synthesise a temporary repro fixture "
            "that stages it on top of the factory install, and "
            "launch DOSBox via `repro.py --play --session`. The "
            "session dir is reused across invocations (resumable) "
            "so in-game state accumulates; the harness snapshots "
            "c-overlay/DARKRUN.GFF before and after and emits a "
            "byte-level diff at the end of the run. The full "
            "opcode-discovery loop needs input automation (queued "
            "for `repro` v0.3.x) plus knowledge of which chunks "
            "the engine invokes on boot; v0.2.0 ships the run + "
            "observe scaffolding the discovery loop sits on."
        ),
    )
    p_run.add_argument("work_dir", type=Path, help="work directory from `extract`")
    p_run.add_argument(
        "--session",
        default=None,
        help=(
            "session name (defaults to `opcode-fuzz-<work-dir-name>`). "
            "Sessions live in the same XDG state root as repro --play, "
            "so `repro.py --list-sessions` finds them."
        ),
    )
    p_run.add_argument(
        "--target-game",
        choices=["ds1", "ds2"],
        default=None,
        help="override target_game inference from the source GFF path",
    )
    p_run.set_defaults(handler=cmd_run)

    p_boot = sub.add_parser(
        "boot-chunks",
        help="Identify GPL chunks the engine invokes directly (no inbound gpl global sub calls).",
        description=(
            "Drives `gpl-disasm --global-cfg --json` against the "
            "input GFF and reports per-chunk inbound-edge counts. "
            "Chunks with zero inbound edges are pure entry points: "
            "the engine's main loop must dispatch them directly, "
            "so they're the safest swap target for fuzz runs."
        ),
    )
    p_boot.add_argument("gff", type=Path, help="GFF to analyse (typically GPLDATA.GFF)")
    p_boot.set_defaults(handler=cmd_boot_chunks)

    args = ap.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
