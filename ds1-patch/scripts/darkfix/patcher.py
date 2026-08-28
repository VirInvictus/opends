"""darkfix.patcher: the fix-application engine for darkfix patches.

Stdlib-only. Python 3.11+ (tomllib). This is the library half of
the applier; apply.py is the CLI half. Per-fix scripts import
``apply_bytes`` / ``apply_gff_chunk`` from here, matching the
contract in docs/patch-workflow.md §4.2.

Refusals are exceptions; the CLI turns them into exit code 1.
Everything is all-or-nothing per fix: fingerprints are checked on
the pristine bytes before anything is written, and every patched
file is backed up first so --unapply can always restore.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import tomllib

# Written inside the game install, next to the patched files.
BACKUP_DIR = "darkfix-backup"
JOURNAL_NAME = "darkfix-applied.json"


class PatchError(Exception):
    """Base class: every refusal the engine makes."""


class ManifestError(PatchError):
    """The patch manifest or a fix script is malformed/inconsistent."""


class HashMismatch(PatchError):
    """A file's hash does not match its required value."""


class FingerprintMismatch(PatchError):
    """Original bytes at a patch site differ from the fingerprint."""


class AlreadyApplied(PatchError):
    """A darkfix journal is present; applying again would double-apply."""


class NotApplied(PatchError):
    """No darkfix journal is present, so there is nothing to revert."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------- manifest


def load_manifest(path: Path) -> dict:
    """Load and structurally validate a patch manifest (schema v1)."""
    path = Path(path)
    with path.open("rb") as f:
        manifest = tomllib.load(f)
    meta = manifest.get("meta", {})
    if meta.get("schema_version") != 1:
        raise ManifestError(
            f"{path}: [meta] schema_version must be 1,"
            f" got {meta.get('schema_version')!r}"
        )
    if not meta.get("game") or not meta.get("name"):
        raise ManifestError(f"{path}: [meta] needs game and name")
    if not manifest.get("target", {}).get("files"):
        raise ManifestError(f"{path}: [target.files] is empty")
    fixes = manifest.get("fixes", [])
    if not fixes:
        raise ManifestError(f"{path}: [[fixes]] list is empty")
    seen: set[str] = set()
    for entry in fixes:
        fid = entry.get("id")
        fpath = entry.get("path")
        if not fid or not fpath:
            raise ManifestError(f"{path}: every [[fixes]] entry needs id and path")
        if fid in seen:
            raise ManifestError(f"{path}: duplicate fix id {fid!r}")
        seen.add(fid)
    return manifest


# ---------------------------------------------------------------- edits


def _coerce_bytes(value: object, what: str) -> bytes:
    """Accept bytes literals or hex strings in fix-script EDITS."""
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, str):
        try:
            return bytes.fromhex(value)
        except ValueError:
            raise PatchError(f"{what}: not valid hex: {value!r}") from None
    raise PatchError(
        f"{what}: expected bytes or hex string, got {type(value).__name__}"
    )


@dataclass(frozen=True)
class Edit:
    """One in-place byte edit: offset, original bytes, replacement.

    Byte patches are strictly in-place (same length). An edit that
    changes file length is refused; see spec.md §4 and the overlay
    payload-offset rule (one inserted byte shifts every following
    overlay payload).
    """

    offset: int
    expect: bytes
    replace: bytes

    @classmethod
    def from_dict(cls, d: dict, *, what: str = "edit") -> Edit:
        missing = [k for k in ("offset", "expect", "replace") if k not in d]
        if missing:
            raise PatchError(f"{what}: missing keys {missing}")
        return cls(
            offset=int(d["offset"]),
            expect=_coerce_bytes(d["expect"], f"{what}.expect"),
            replace=_coerce_bytes(d["replace"], f"{what}.replace"),
        )


def apply_edits(data: bytes, edits: list[Edit], *, what: str = "fix") -> bytes:
    """Apply same-length byte edits to `data`, all-or-nothing.

    Every site is fingerprint-checked before anything is written,
    and overlapping sites are refused.
    """
    checked: list[tuple[int, int]] = []
    for i, edit in enumerate(edits):
        end = edit.offset + len(edit.expect)
        if end > len(data):
            raise FingerprintMismatch(
                f"{what}: edit {i} at offset {edit.offset:#x} runs past end of file"
            )
        if len(edit.replace) != len(edit.expect):
            raise PatchError(
                f"{what}: edit {i} changes length"
                f" ({len(edit.expect)} -> {len(edit.replace)} bytes);"
                " byte patches must be in-place (spec.md §4)"
            )
        actual = data[edit.offset : end]
        if actual != edit.expect:
            raise FingerprintMismatch(
                f"{what}: edit {i} at offset {edit.offset:#x}:"
                f" expected {edit.expect.hex()}, found {actual.hex()}"
            )
        for start0, end0 in checked:
            if edit.offset < end0 and start0 < end:
                raise PatchError(f"{what}: edit {i} overlaps an earlier edit")
        checked.append((edit.offset, end))
    out = bytearray(data)
    for edit in edits:
        out[edit.offset : edit.offset + len(edit.replace)] = edit.replace
    return bytes(out)


def apply_bytes(source_path: Path, dest_path: Path, edits) -> Path:
    """Read source_path, apply byte edits, write dest_path.

    Per-fix authoring helper (docs/patch-workflow.md §4.2). Accepts
    Edit objects or the raw dicts fix scripts declare.
    """
    edits = [
        e if isinstance(e, Edit) else Edit.from_dict(e, what=f"edit {i}")
        for i, e in enumerate(edits)
    ]
    data = apply_edits(Path(source_path).read_bytes(), edits)
    dest = Path(dest_path)
    if not dest.parent.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return dest


# ------------------------------------------------------------- gff chunks


def apply_gff_chunk(
    source_path: Path,
    dest_path: Path,
    kind: str,
    chunk_id: int,
    bytes_path: Path,
    *,
    gff_cat: str | None = None,
) -> Path:
    """Replace one GFF chunk via `gff-cat replace` (tools/gff-edit).

    Data-surface fixes swap a GPL/RESOURCE/OBJEX chunk through the
    gff-edit writer: in-place when the replacement fits, appended
    otherwise. Shells out; gff-cat must be on PATH, or name the
    binary via gff_cat= or $DARKFIX_GFF_CAT.
    """
    binary = gff_cat or os.environ.get("DARKFIX_GFF_CAT") or "gff-cat"
    if os.sep not in binary and shutil.which(binary) is None:
        raise PatchError(
            "gff-cat not found on PATH; build it with"
            " `cargo build -p gff-edit` or set DARKFIX_GFF_CAT"
        )
    dest = Path(dest_path)
    proc = subprocess.run(
        [
            binary,
            "replace",
            str(source_path),
            kind,
            str(chunk_id),
            str(bytes_path),
            "-o",
            str(dest),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0 or not dest.is_file():
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
        raise PatchError(
            f"gff-cat replace failed for {kind} chunk {chunk_id} in"
            f" {source_path}: {'; '.join(tail)}"
        )
    return dest


# ------------------------------------------------------- backup + journal


def backup_root(install: Path) -> Path:
    return install / BACKUP_DIR


def backup_file(install: Path, rel: str) -> Path:
    """Copy the pristine file into darkfix-backup/ before first write.

    Never overwrites an existing backup: the only pristine copy
    must not be clobberable by a re-apply.
    """
    src = install / rel
    dst = backup_root(install) / rel
    if dst.exists():
        raise PatchError(f"refusing to overwrite existing backup: {dst}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def journal_path(install: Path) -> Path:
    return install / JOURNAL_NAME


def write_journal(install: Path, journal: dict) -> Path:
    path = journal_path(install)
    path.write_text(json.dumps(journal, indent=2) + "\n")
    return path


def read_journal(install: Path) -> dict | None:
    path = journal_path(install)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise PatchError(
            f"{path} is not valid JSON ({e}); restore manually from {BACKUP_DIR}/"
        ) from None


def restore_from_backup(install: Path, journal: dict) -> list[str]:
    """Restore every journaled file from darkfix-backup/.

    All backups are hash-verified against the journal before any
    restore begins; consumed backups are deleted and empty
    directories pruned. Returns the restored relative paths.
    """
    wanted: list[tuple[str, str]] = []
    for fix in journal.get("fixes", []):
        for f in fix.get("files", []):
            wanted.append((f["path"], f["original_sha256"]))
    if not wanted:
        raise PatchError("journal records no files; nothing to restore")
    for rel, want in wanted:
        src = backup_root(install) / rel
        if not src.is_file():
            raise PatchError(
                f"backup missing: {src}; the install cannot be reverted automatically"
            )
        got = sha256_file(src)
        if got != want:
            raise HashMismatch(
                f"backup {src} does not match the journaled original hash"
            )
    restored: list[str] = []
    for rel, _ in wanted:
        src = backup_root(install) / rel
        shutil.copy2(src, install / rel)
        src.unlink()
        restored.append(rel)
    root = backup_root(install)
    for dirpath, _dirnames, _filenames in sorted(os.walk(root, topdown=False)):
        try:
            os.rmdir(dirpath)
        except OSError:
            pass  # not empty; leave it
    return restored
