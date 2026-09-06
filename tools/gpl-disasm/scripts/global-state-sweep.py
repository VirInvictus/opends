#!/usr/bin/env python3
"""global-state-sweep: find written-but-never-read GPL global state.

Consumes a directory of `gpl-disasm --all --json` dumps and classifies
every global-variable reference (gflag / gnum / gbignum / gstring) as
a READ or a WRITE:

- `gpl load variable <src>, <dst>`: the destination (last parameter)
  is a WRITE; variable uses inside the source expression are READs.
- compound-assign mnemonics (`* inc`, `* dec`, `*times equal`,
  `*plus equal`, ...) read their target to compute and write it back:
  counted as both.
- every other occurrence (expressions, conditions, ret_val contexts)
  is a READ.

Output bands:

- DANGLING: written somewhere, never read anywhere.
- SELF-CONTAINED: read somewhere, but every reading chunk also
  writes the variable, so the state never escapes the script that
  owns it and cannot influence any other script. This is the
  measured form of the "dangling switch" class: DS2's elevator
  railhead flags are written by GPL-287 and read only by GPL-287's
  own status print, which is why the switch state never causes a
  ride.
- READ-NEVER-WRITTEN: consulted but never assigned in the shipped
  corpus, so the script logic is dead or the write is engine-side.

Local variables (lnum / lflag / lstring) are per-script stack state,
not save state, and gname registers are runtime object handles; all
three are excluded.

Proposals are review input: this tool never edits catalogues.
Stdlib-only. Python 3.11+.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
VERSION = (HERE.parent / "VERSION").read_text().strip()

SWEEP_KINDS = {"gflag", "gnum", "gbignum", "gstring"}
COMPOUND_TOKENS = ("inc", "dec", "equal")


class SweepError(Exception):
    pass


def collect_vars(node: Any, out: list[dict[str, Any]]) -> None:
    """Depth-first collection of variable operands in a param tree."""
    if isinstance(node, dict):
        if node.get("kind") == "variable":
            out.append(node)
        for value in node.values():
            collect_vars(value, out)
    elif isinstance(node, list):
        for value in node:
            collect_vars(value, out)


def classify_instruction(instruction: dict[str, Any]) -> tuple[list, list]:
    """Return (reads, writes) variable dicts for one instruction."""
    mnemonic = instruction.get("mnemonic", "")
    params = instruction.get("params", [])
    reads: list[dict[str, Any]] = []
    writes: list[dict[str, Any]] = []

    first: list = []
    for group in params:
        collect_vars(group, first)

    if mnemonic == "gpl load variable":
        # params[-1] is the destination: WRITE. Every other use is a READ.
        dest: list = []
        for group in params[-1:]:
            collect_vars(group, dest)
        writes.extend(dest)
        dest_ids = {id(v) for v in dest}
        reads.extend(v for v in first if id(v) not in dest_ids)
        return reads, writes

    if any(token in mnemonic for token in COMPOUND_TOKENS) and first:
        # compound-assign: every referenced variable is read and written
        return list(first), list(first)

    return first, []


def sweep_dump_dir(dump_dir: Path) -> dict[str, Any]:
    files = sorted(dump_dir.glob("*.json"))
    if not files:
        raise SweepError(
            f"no .json dumps under {dump_dir} "
            f"(run: gpl-disasm GPLDATA.GFF --all --json -o {dump_dir})"
        )
    state: dict[tuple[str, int], dict[str, Any]] = {}

    def entry(kind: str, ident: int) -> dict[str, Any]:
        return state.setdefault(
            kind + f"[{ident}]",
            {
                "kind": kind,
                "id": ident,
                "reads": 0,
                "writes": 0,
                "written_by": [],
                "read_by": [],
                "extended_writes": 0,
            },
        )

    for path in files:
        chunk = path.stem
        data = json.loads(path.read_text())
        for instruction in data.get("instructions", []):
            reads, writes = classify_instruction(instruction)
            for var in reads:
                kind, ident = var.get("var_kind"), var.get("id")
                if kind in SWEEP_KINDS:
                    e = entry(kind, ident)
                    e["reads"] += 1
                    e["read_by"].append(chunk)
            for var in writes:
                kind, ident = var.get("var_kind"), var.get("id")
                if kind in SWEEP_KINDS:
                    e = entry(kind, ident)
                    e["writes"] += 1
                    if chunk not in e["written_by"]:
                        e["written_by"].append(chunk)
                    if var.get("extended"):
                        e["extended_writes"] += 1

    dangling = sorted(
        (e for e in state.values() if e["writes"] and not e["reads"]),
        key=lambda e: (e["kind"], e["id"]),
    )
    self_contained = sorted(
        (
            e
            for e in state.values()
            if e["reads"] and e["writes"] and set(e["read_by"]) <= set(e["written_by"])
        ),
        key=lambda e: (e["kind"], e["id"]),
    )
    dead = sorted(
        (e for e in state.values() if e["reads"] and not e["writes"]),
        key=lambda e: (e["kind"], e["id"]),
    )
    live = sum(
        1
        for e in state.values()
        if e["reads"] and e["writes"] and not set(e["read_by"]) <= set(e["written_by"])
    )
    return {
        "dangling": dangling,
        "self_contained": self_contained,
        "dead": dead,
        "totals": {
            "globals_seen": len(state),
            "live": live,
            "dangling": len(dangling),
            "self_contained": len(self_contained),
            "read_never_written": len(dead),
        },
    }


def selftest() -> int:
    """Classifier checks on synthetic instructions (no corpus needed)."""
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    def var(kind: str, ident: int, ext: bool = False) -> dict[str, Any]:
        return {"kind": "variable", "var_kind": kind, "id": ident, "extended": ext}

    def imm(value: int) -> dict[str, Any]:
        return {"kind": "immediate_byte", "value": value}

    # load variable: dest write, source read
    reads, writes = classify_instruction(
        {
            "mnemonic": "gpl load variable",
            "params": [[imm(0)], [var("gflag", 647, ext=True)]],
        }
    )
    check(len(writes) == 1 and writes[0]["id"] == 647, "loadvar dest is the write")
    check(not reads, "loadvar plain immediate source adds no read")

    # load variable with an expression source: the source var is a read
    reads, writes = classify_instruction(
        {
            "mnemonic": "gpl load variable",
            "params": [[var("gnum", 5)], [var("gnum", 6)]],
        }
    )
    check(writes and writes[0]["id"] == 6, "loadvar var-to-var writes the dest")
    check(reads and reads[0]["id"] == 5, "loadvar var-to-var reads the source")

    # compound assign: both read and write
    reads, writes = classify_instruction(
        {
            "mnemonic": "gpl byte plus equal",
            "params": [[var("gnum", 9)], [imm(1)]],
        }
    )
    check(
        reads and writes and reads[0]["id"] == 9 and writes[0]["id"] == 9,
        "compound assign counts as read+write",
    )

    # plain expression: read only
    reads, writes = classify_instruction(
        {
            "mnemonic": "gpl load accum",
            "params": [
                [
                    {"kind": "open_paren"},
                    var("gflag", 12),
                    {"kind": "binary_op", "op": "equal"},
                    imm(0),
                    {"kind": "close_paren"},
                ]
            ],
        }
    )
    check(
        len(reads) == 1 and reads[0]["id"] == 12 and not writes,
        "expression use is a read",
    )

    # end-to-end over a synthetic dump dir
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        dump = Path(td) / "GPL-1.json"
        dump.write_text(
            json.dumps(
                {
                    "instructions": [
                        {
                            "mnemonic": "gpl load variable",
                            "params": [[imm(1)], [var("gflag", 700, ext=True)]],
                        },
                        {"mnemonic": "gpl load accum", "params": [[var("gflag", 701)]]},
                        {
                            "mnemonic": "gpl load variable",
                            "params": [[imm(2)], [var("gnum", 8)]],
                        },
                        {"mnemonic": "gpl load accum", "params": [[var("gnum", 8)]]},
                    ]
                }
            )
        )
        report = sweep_dump_dir(Path(td))
        dangles = {(e["kind"], e["id"]) for e in report["dangling"]}
        deads = {(e["kind"], e["id"]) for e in report["dead"]}
        check(("gflag", 700) in dangles, "written-never-read lands in dangling")
        check(("gflag", 701) in deads, "read-never-written lands in dead")
        check(
            ("gnum", 8) not in dangles and ("gnum", 8) not in deads,
            "read+written is live",
        )
        check(report["totals"]["globals_seen"] == 3, "totals count")

    if failures:
        for f in failures:
            print(f"FAIL {f}", file=sys.stderr)
        return 1
    print("global-state-sweep selftest: classifier holds")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="global-state-sweep",
        description="Find written-but-never-read GPL global state "
        "(the dangling-switch class) from gpl-disasm --all --json dumps.",
    )
    ap.add_argument(
        "dump_dir",
        type=Path,
        nargs="?",
        help="directory of per-chunk .json dumps from "
        "`gpl-disasm <gff> --all --json -o <dir>`",
    )
    ap.add_argument(
        "--selftest", action="store_true", help="run the classifier checks and exit"
    )
    ap.add_argument("--json", action="store_true", help="emit the full report as JSON")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.dump_dir is None:
        ap.error("dump_dir is required (or pass --selftest)")
    try:
        report = sweep_dump_dir(args.dump_dir)
    except (SweepError, json.JSONDecodeError) as e:
        print(f"global-state-sweep: {e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    t = report["totals"]
    print(
        f"globals seen: {t['globals_seen']}  "
        f"live: {t['live']}  dangling: {t['dangling']}  "
        f"self-contained: {t['self_contained']}  "
        f"read-never-written: {t['read_never_written']}"
    )
    if report["dangling"]:
        print("\nDANGLING (written, never read):")
        for e in report["dangling"]:
            print(
                f"  {e['kind']}[{e['id']}]  writes={e['writes']}"
                f"{' (GF+[..] form)' if e['extended_writes'] else ''}"
                f"  in {', '.join(e['written_by'])}"
            )
    if report["self_contained"]:
        print(
            "\nSELF-CONTAINED (read only by chunks that also write it; "
            "state never escapes its owner):"
        )
        for e in report["self_contained"]:
            print(
                f"  {e['kind']}[{e['id']}]  writes={e['writes']} reads={e['reads']}"
                f"  in {', '.join(sorted(set(e['written_by'])))}"
            )
    if report["dead"]:
        print("\nREAD-NEVER-WRITTEN (consulted, never assigned):")
        for e in report["dead"]:
            readers = ", ".join(sorted(set(e["read_by"]))[:4])
            more = "" if len(set(e["read_by"])) <= 4 else ", ..."
            print(f"  {e['kind']}[{e['id']}]  reads={e['reads']}  in {readers}{more}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
