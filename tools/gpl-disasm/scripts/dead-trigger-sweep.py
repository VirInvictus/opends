#!/usr/bin/env python3
"""dead-trigger-sweep: find entity triggers whose handlers are missing
or trivial.

Consumes a directory of `gpl-disasm --all --json` dumps. Entity
trigger registrations have the shape (entry_offset, handler_chunk_id,
NAME(-object)):

- attacktrigger / looktrigger / pickupitemtrigger / usetrigger /
  talktotrigger / noorderstrigger (3 params; chunk id at position 1)
- usewithtrigger (4 params; chunk id at position 3)

For every registration the sweep checks the handler chunk:

- MISSING: no such GPL chunk in the corpus (dangling registration).
- TRIVIAL: the entry offset holds only an exit/ret instruction (the
  handler was stubbed out; the trigger fires into nothing).
- OFFSET-PAST-END: the entry offset is beyond the chunk's bytes.
- otherwise ALIVE.

Coordinate triggers (tile/boxtrigger) have no handler chunk and are
out of scope. The "enemies refuse to engage" DS1 community reports
are the motivating class: an attacktrigger whose handler is trivial
or missing is exactly a monster that will not fight.

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

# mnemonic -> index of the handler-chunk-id parameter
TRIGGER_OPS = {
    "gpl attacktrigger": 1,
    "gpl looktrigger": 1,
    "gpl pickupitemtrigger": 1,
    "gpl usetrigger": 1,
    "gpl talktotrigger": 1,
    "gpl noorderstrigger": 1,
    "gpl usewithtrigger": 3,
}
# instructions that mean "there is no handler here"
TRIVIAL_MNEMONICS = {"gpl exit gpl", "gpl global ret", "gpl local ret"}


class SweepError(Exception):
    pass


def _immediate(param: list[dict[str, Any]]) -> int | None:
    """The plain immediate value of a parameter group, if it is one."""
    if len(param) == 1 and param[0].get("kind") in ("immediate14", "immediate_byte"):
        return int(param[0]["value"])
    return None


def sweep_dump_dir(dump_dir: Path) -> dict[str, Any]:
    files = sorted(dump_dir.glob("*.json"))
    if not files:
        raise SweepError(
            f"no .json dumps under {dump_dir} "
            f"(run: gpl-disasm GPLDATA.GFF --all --json -o {dump_dir})"
        )

    chunks: dict[str, dict[str, Any]] = {}
    for path in files:
        data = json.loads(path.read_text())
        insts = data.get("instructions", [])
        end = max((i["offset"] + i["length"] for i in insts), default=0)
        by_offset = {i["offset"]: i for i in insts}
        chunks[path.stem] = {"instructions": insts, "end": end, "by_offset": by_offset}

    registrations: list[dict[str, Any]] = []
    for path in files:
        registrar = path.stem
        data = json.loads(path.read_text())
        for instruction in data.get("instructions", []):
            position = TRIGGER_OPS.get(instruction.get("mnemonic", ""))
            if position is None:
                continue
            params = instruction.get("params", [])
            if len(params) <= position:
                continue
            handler_id = _immediate(params[1] if position == 1 else params[3])
            entry_offset = _immediate(params[0])
            if handler_id is None or entry_offset is None:
                continue  # computed handler: flag as unresolvable below
            registrations.append(
                {
                    "registrar": registrar,
                    "offset": instruction["offset"],
                    "mnemonic": instruction["mnemonic"],
                    "handler": f"GPL-{handler_id}",
                    "entry_offset": entry_offset,
                }
            )

    dead: list[dict[str, Any]] = []
    null_handler = 0
    alive = 0
    for reg in registrations:
        if reg["handler"] == "GPL-0":
            # handler id 0 with entry 0 is the 'no orders / do nothing'
            # sentinel (chunk 0 does not exist in either corpus);
            # intentional, counted separately, not a dead trigger.
            reg["verdict"] = "NULL-HANDLER"
            null_handler += 1
            continue
        chunk = chunks.get(reg["handler"])
        if chunk is None:
            reg["verdict"] = "MISSING"
            dead.append(reg)
            continue
        inst = chunk["by_offset"].get(reg["entry_offset"])
        if inst is None:
            if reg["entry_offset"] >= chunk["end"]:
                reg["verdict"] = "OFFSET-PAST-END"
                dead.append(reg)
            else:
                reg["verdict"] = "MID-SEQUENCE"
                alive += 1  # offset inside the chunk but not an entry point
            continue
        if inst["mnemonic"] in TRIVIAL_MNEMONICS:
            reg["verdict"] = "TRIVIAL"
            dead.append(reg)
        else:
            reg["verdict"] = "ALIVE"
            alive += 1

    return {
        "registrations": len(registrations),
        "alive": alive,
        "null_handler": null_handler,
        "dead": dead,
    }


def selftest() -> int:
    """Synthetic dump: one alive handler, one trivial, one missing."""
    import tempfile

    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    def inst(mnemonic: str, offset: int, length: int, params: list) -> dict:
        return {
            "mnemonic": mnemonic,
            "offset": offset,
            "length": length,
            "params": params,
        }

    def imm(value: int) -> list:
        return [{"kind": "immediate14", "value": value}]

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "MAS-1.json").write_text(
            json.dumps(
                {
                    "instructions": [
                        inst(
                            "gpl usetrigger",
                            0,
                            8,
                            [
                                imm(0x10),
                                imm(2),
                                [{"kind": "immediate_name", "value": -74}],
                            ],
                        ),
                        inst(
                            "gpl looktrigger",
                            20,
                            8,
                            [
                                imm(0x20),
                                imm(3),
                                [{"kind": "immediate_name", "value": -75}],
                            ],
                        ),
                        inst(
                            "gpl attacktrigger",
                            40,
                            8,
                            [
                                imm(0x30),
                                imm(9),
                                [{"kind": "immediate_name", "value": -76}],
                            ],
                        ),
                        inst(
                            "gpl attacktrigger",
                            60,
                            8,
                            [
                                imm(0x40),
                                imm(2),
                                [{"kind": "immediate_name", "value": -77}],
                            ],
                        ),
                    ]
                }
            )
        )
        (root / "GPL-2.json").write_text(
            json.dumps(
                {
                    "instructions": [
                        inst("gpl print string", 0x10, 4, [imm(1)]),
                        inst("gpl exit gpl", 0x40, 1, []),
                    ]
                }
            )
        )
        (root / "GPL-3.json").write_text(
            json.dumps(
                {
                    "instructions": [
                        inst("gpl exit gpl", 0x20, 1, []),
                    ]
                }
            )
        )
        report = sweep_dump_dir(root)
        verdicts = {(d["handler"], d["verdict"]) for d in report["dead"]}
        check(report["registrations"] == 4, "four registrations parsed")
        check(report["alive"] == 1, "one alive")
        check(("GPL-9", "MISSING") in verdicts, "missing chunk detected")
        check(("GPL-3", "TRIVIAL") in verdicts, "trivial handler detected")
        check(("GPL-2", "MID-SEQUENCE") not in verdicts, "mid-sequence not dead")

    if failures:
        for f in failures:
            print(f"FAIL {f}", file=sys.stderr)
        return 1
    print("dead-trigger-sweep selftest: verdicts hold")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="dead-trigger-sweep",
        description="Find entity triggers whose handler chunk is missing "
        "or trivial, from gpl-disasm --all --json dumps.",
    )
    ap.add_argument(
        "dump_dir",
        type=Path,
        nargs="?",
        help="directory of per-chunk .json dumps from "
        "`gpl-disasm <gff> --all --json -o <dir>`",
    )
    ap.add_argument(
        "--selftest", action="store_true", help="run the synthetic checks and exit"
    )
    ap.add_argument("--json", action="store_true", help="emit the report as JSON")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.dump_dir is None:
        ap.error("dump_dir is required (or pass --selftest)")
    try:
        report = sweep_dump_dir(args.dump_dir)
    except (SweepError, json.JSONDecodeError) as e:
        print(f"dead-trigger-sweep: {e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    print(
        f"registrations: {report['registrations']}  alive: {report['alive']}  "
        f"null-handler: {report['null_handler']}  dead: {len(report['dead'])}"
    )
    if report["dead"]:
        print("\nDEAD TRIGGERS:")
        for d in report["dead"]:
            print(
                f"  {d['verdict']:15s} {d['mnemonic']}  handler {d['handler']}"
                f" entry 0x{d['entry_offset']:x}  registered in {d['registrar']}"
                f"@0x{d['offset']:x}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
