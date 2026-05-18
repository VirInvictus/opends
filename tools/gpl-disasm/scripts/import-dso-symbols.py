#!/usr/bin/env python3
"""Import DSO Crimson Sands debug symbols into gpl-disasm catalogues.

Parses `.dso-online/tools/symbols.txt` (3,530 functions + 2,247
globals from the DSO v1.0 client; see `docs/dso-symbols.md`) and
emits review-ready proposals for the curated symbol catalogues
under `tools/gpl-disasm/syms/`.

The script never writes to the curated TOML files in `syms/`
directly. Per the curation rule in `syms/opcodes.toml`, every
proposed override must be hand-reviewed. The script's job is to
generate the proposal cheaply enough that review is a five-minute
task instead of a half-hour one.

Outputs (default: stdout):

  --opcodes-proposed    TOML block of opcode-byte renames where
                        libgff's mnemonic and DSO's Decode* handler
                        name agree by case-insensitive PascalCase
                        equivalence. Suitable for cherry-picking
                        into syms/opcodes.toml.

  --functions-summary   Markdown table of DSO functions categorised
                        by GPL/GFF-related prefix. Suitable for
                        pasting into docs/dso-symbols.md as the
                        "Highest-value GPL-related symbols" tier.

  --globals-summary     Markdown table of gGpl* / bGpl* engine
                        globals. Same docs target.

  --unmatched-decoders  DSO Decode* names with no obvious libgff
                        slot. Candidates for filling in libgff's
                        `gpl default` / `gpl unknown` entries once
                        the dispatch table is RE'd.

Default with no flag: emits a human-readable summary covering all
four categories.

Stdlib-only; no third-party deps.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# libgff's opcode table, byte-indexed. Source of truth is OPCODES
# in tools/gpl-disasm/src/lib.rs. Keep in sync; this is the only
# Python consumer.
LIBGFF_OPCODES: list[str] = [
    "gpl zero",              # 0x00
    "gpl long divide equal", # 0x01
    "gpl byte dec",          # 0x02
    "gpl word dec",          # 0x03
    "gpl long dec",          # 0x04
    "gpl byte inc",          # 0x05
    "gpl word inc",          # 0x06
    "gpl long inc",          # 0x07
    "gpl hunt",              # 0x08
    "gpl getxy",             # 0x09
    "gpl string copy",       # 0x0A
    "gpl p damage",          # 0x0B
    "gpl changemoney",       # 0x0C
    "gpl setvar",            # 0x0D
    "gpl toggle accum",      # 0x0E
    "gpl getstatus",         # 0x0F
    "gpl getlos",            # 0x10
    "gpl long times equal",  # 0x11
    "gpl jump",              # 0x12
    "gpl local sub",         # 0x13
    "gpl global sub",        # 0x14
    "gpl local ret",         # 0x15
    "gpl load variable",     # 0x16
    "gpl compare",           # 0x17
    "gpl load accum",        # 0x18
    "gpl global ret",        # 0x19
    "gpl nextto",            # 0x1A
    "gpl inlostrigger",      # 0x1B
    "gpl notinlostrigger",   # 0x1C
    "gpl clear los",         # 0x1D
    "gpl nametonum",         # 0x1E
    "gpl numtoname",         # 0x1F
    "gpl bitsnoop",          # 0x20
    "gpl award",             # 0x21
    "gpl request",           # 0x22
    "gpl source trace",      # 0x23
    "gpl shop",              # 0x24
    "gpl clone",             # 0x25
    "gpl default",           # 0x26
    "gpl ifcompare",         # 0x27
    "gpl trace var",         # 0x28
    "gpl orelse",            # 0x29
    "gpl clearpic",          # 0x2A
    "gpl continue",          # 0x2B
    "gpl log",               # 0x2C
    "gpl damage",            # 0x2D
    "gpl source line num",   # 0x2E
    "gpl drop",              # 0x2F
    "gpl passtime",          # 0x30
    "gpl exit gpl",          # 0x31
    "gpl fetch",             # 0x32
    "gpl search",            # 0x33
    "gpl getparty",          # 0x34
    "gpl fight",             # 0x35
    "gpl flee",              # 0x36
    "gpl follow",            # 0x37
    "gpl getyn",             # 0x38
    "gpl give",              # 0x39
    "gpl go",                # 0x3A
    "gpl input bignum",      # 0x3B
    "gpl goxy",              # 0x3C
    "gpl readorders",        # 0x3D
    "gpl if",                # 0x3E
    "gpl else",              # 0x3F
    "gpl setrecord",         # 0x40
    "gpl setother",          # 0x41
    "gpl input string",      # 0x42
    "gpl input number",      # 0x43
    "gpl input money",       # 0x44
    "gpl joinparty",         # 0x45
    "gpl leaveparty",        # 0x46
    "gpl lockdoor",          # 0x47
    "gpl menu",              # 0x48
    "gpl setthing",          # 0x49
    "gpl default",           # 0x4A
    "gpl local sub trace",   # 0x4B
    "gpl default",           # 0x4C
    "gpl default",           # 0x4D
    "gpl default",           # 0x4E
    "gpl print string",      # 0x4F
    "gpl print number",      # 0x50
    "gpl printnl",           # 0x51
    "gpl rand",              # 0x52
    "gpl default",           # 0x53
    "gpl showpic",           # 0x54
    "gpl default",           # 0x55
    "gpl default",           # 0x56
    "gpl default",           # 0x57
    "gpl skillroll",         # 0x58
    "gpl statroll",          # 0x59
    "gpl string compare",    # 0x5A
    "gpl match string",      # 0x5B
    "gpl take",              # 0x5C
    "gpl sound",             # 0x5D
    "gpl tport",             # 0x5E
    "gpl music",             # 0x5F
    "gpl default",           # 0x60
    "gpl cmpend",            # 0x61
    "gpl wait",              # 0x62
    "gpl while",             # 0x63
    "gpl wend",              # 0x64
    "gpl attacktrigger",     # 0x65
    "gpl looktrigger",       # 0x66
    "gpl endif",             # 0x67
    "gpl move tiletrigger",  # 0x68
    "gpl door tiletrigger",  # 0x69
    "gpl move boxtrigger",   # 0x6A
    "gpl door boxtrigger",   # 0x6B
    "gpl pickup itemtrigger",# 0x6C
    "gpl usetrigger",        # 0x6D
    "gpl talktotrigger",     # 0x6E
    "gpl noorderstrigger",   # 0x6F
    "gpl usewithtrigger",    # 0x70
    "gpl default",           # 0x71
    "gpl default",           # 0x72
    "gpl default",           # 0x73
    "gpl default",           # 0x74
    "gpl default",           # 0x75
    "gpl byte plus equal",   # 0x76
    "gpl byte minus equal",  # 0x77
    "gpl byte times equal",  # 0x78
    "gpl byte divide equal", # 0x79
    "gpl word plus equal",   # 0x7A
    "gpl word minus equal",  # 0x7B
    "gpl word times equal",  # 0x7C
    "gpl word divide equal", # 0x7D
    "gpl long plus equal",   # 0x7E
    "gpl long minus equal",  # 0x7F
    "gpl get range",         # 0x80
]

# libgff handler names that mean "we don't know what this opcode
# does." Treated as no-information slots in the proposal output:
# the DSO Decode* family might tell us, but name-equivalence can't
# resolve which Decode* maps to which slot without a dispatch-table
# RE pass against DSUN.EXE.
LIBGFF_PLACEHOLDER_NAMES = {"gpl default", "gpl unknown"}


def to_pascal(libgff_name: str) -> str:
    """Convert 'gpl long divide equal' to 'LongDivideEqual'.

    Drops the 'gpl ' prefix, splits on whitespace, capitalises each
    token. Matches the naming pattern DSO appears to follow for
    its Decode* family.
    """
    stripped = re.sub(r"^gpl ", "", libgff_name)
    return "".join(part.capitalize() for part in stripped.split())


def parse_symbols(path: Path) -> tuple[dict[str, int], dict[str, int]]:
    """Parse the DSO symbols file.

    Returns (functions, globals) where each maps name -> v1.0 client
    image offset. Lines are 'NAME HEX KIND' with KIND in {f, l}.
    """
    funcs: dict[str, int] = {}
    globs: dict[str, int] = {}
    with path.open() as fh:
        for line in fh:
            parts = line.split()
            if len(parts) != 3:
                continue
            name, addr_hex, kind = parts
            try:
                addr = int(addr_hex, 16)
            except ValueError:
                continue
            if kind == "f":
                funcs[name] = addr
            elif kind == "l":
                globs[name] = addr
    return funcs, globs


def propose_opcode_renames(
    funcs: dict[str, int],
) -> tuple[list[tuple[int, str, str]], list[int]]:
    """Match libgff opcodes to DSO Decode* handlers by name.

    Returns (matches, unmatched_libgff_bytes):
      matches: list of (byte, libgff_name, dso_name) where
        Decode<PascalCase(libgff_name)> is present in DSO.
      unmatched_libgff_bytes: libgff bytes with a real handler name
        that DSO doesn't appear to have under the conventional
        prefix.
    """
    matches: list[tuple[int, str, str]] = []
    unmatched: list[int] = []
    for byte, libgff in enumerate(LIBGFF_OPCODES):
        if libgff in LIBGFF_PLACEHOLDER_NAMES:
            continue
        candidate = "Decode" + to_pascal(libgff)
        if candidate in funcs:
            matches.append((byte, libgff, candidate))
        else:
            unmatched.append(byte)
    return matches, unmatched


def find_unmatched_decoders(
    funcs: dict[str, int],
    matches: list[tuple[int, str, str]],
) -> list[str]:
    """Return DSO Decode* names that didn't pair with a libgff opcode.

    These are candidates for slots libgff marks `gpl default`: the
    handler exists in the engine but libgff doesn't name it. Without
    the dispatch table we can't say which opcode byte each maps to,
    but the list tells us how many real handlers libgff is missing.
    """
    matched_names = {dso for _, _, dso in matches}
    return sorted(
        name for name in funcs
        if name.startswith("Decode") and name not in matched_names
    )


def render_opcode_proposals(matches: list[tuple[int, str, str]]) -> str:
    """Emit TOML rows for the matched proposals, comment-rich for review."""
    lines = [
        "# DSO opcode-rename proposals.",
        "# Generated by tools/gpl-disasm/scripts/import-dso-symbols.py",
        "# from .dso-online/tools/symbols.txt. Each row pairs",
        "# libgff's mnemonic with the DSO debug-symbol handler",
        "# name. Review per the curation rule at the top of",
        "# syms/opcodes.toml; do NOT cherry-pick blindly.",
        "#",
        f"# {len(matches)} matched proposals.",
        "",
    ]
    for byte, libgff, dso in matches:
        display = dso.removeprefix("Decode")
        lines.append(f'# 0x{byte:02x}  libgff: "{libgff}"  ->  DSO: {dso}')
        lines.append(f'[opcodes."0x{byte:02x}"]')
        lines.append(f'name = "{display}"')
        lines.append(f'dso_source = "DSO::{dso}"')
        lines.append('verified_by = "name-equivalence-with-libgff"')
        lines.append("")
    return "\n".join(lines)


GPL_GLOBAL_PREFIXES = ("gGpl", "bGpl", "gGame", "gParty", "gCurrent")


def render_globals_summary(globs: dict[str, int]) -> str:
    """Markdown table of GPL-related engine globals."""
    rows = sorted(
        (name, addr) for name, addr in globs.items()
        if any(name.startswith(p) for p in GPL_GLOBAL_PREFIXES)
    )
    lines = [
        f"## DSO engine globals (prefix-filtered, {len(rows)} entries)",
        "",
        "Auto-extracted from `.dso-online/tools/symbols.txt`. These are",
        "candidates: the v1.0 client image offsets do not map directly",
        "to DS2's `DSUN.EXE`; the names are the cross-reference.",
        "",
        "| Symbol | v1.0 client offset | Likely role |",
        "|--------|-------------------|-------------|",
    ]
    for name, addr in rows:
        lines.append(f"| `{name}` | `0x{addr:08x}` | _(TBD; cross-reference and verify)_ |")
    return "\n".join(lines)


GPL_FUNCTION_PATTERNS = (
    re.compile(r"^Gpl"),
    re.compile(r"^Decode"),
    re.compile(r"^.*Gpl.*$"),
    re.compile(r"^Gff"),
    re.compile(r"^.*Gff.*$"),
)


def render_functions_summary(funcs: dict[str, int]) -> str:
    """Markdown table of GPL/GFF-related engine functions."""
    rows = sorted(
        (name, addr) for name, addr in funcs.items()
        if any(p.search(name) for p in GPL_FUNCTION_PATTERNS)
    )
    lines = [
        f"## DSO engine functions related to GPL/GFF ({len(rows)} entries)",
        "",
        "Auto-extracted by name pattern. These are the high-value",
        "cross-reference targets for `gpl-disasm` and `gff-edit`:",
        "engine intrinsics that GPL chunks invoke, GFF I/O routines,",
        "and the Decode* opcode-handler family.",
        "",
        "| Symbol | v1.0 client offset |",
        "|--------|-------------------|",
    ]
    for name, addr in rows:
        lines.append(f"| `{name}` | `0x{addr:08x}` |")
    return "\n".join(lines)


def render_unmatched_decoders_summary(unmatched: list[str]) -> str:
    """Markdown / text summary of unmatched DSO Decode* functions."""
    lines = [
        f"## DSO Decode* handlers with no libgff slot ({len(unmatched)} entries)",
        "",
        "These are candidates for the `gpl default` / `gpl unknown`",
        "rows in libgff's table. Without a DSUN.EXE dispatch-table RE",
        "pass we can't say which opcode byte each maps to. Listed",
        "for awareness; map them as the RE catches up.",
        "",
    ]
    for name in unmatched:
        lines.append(f"- `{name}`")
    return "\n".join(lines)


def default_symbols_path() -> Path:
    """Find .dso-online/tools/symbols.txt by walking up from this script."""
    here = Path(__file__).resolve().parent
    for ancestor in [here, *here.parents]:
        candidate = ancestor / ".dso-online" / "tools" / "symbols.txt"
        if candidate.is_file():
            return candidate
    return Path(".dso-online/tools/symbols.txt")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--source",
        type=Path,
        default=default_symbols_path(),
        help="path to DSO symbols.txt (default: walk up to .dso-online/tools/symbols.txt)",
    )
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument(
        "--opcodes-proposed", action="store_true",
        help="emit TOML opcode-rename proposals only",
    )
    mode.add_argument(
        "--functions-summary", action="store_true",
        help="emit markdown engine-functions summary only",
    )
    mode.add_argument(
        "--globals-summary", action="store_true",
        help="emit markdown engine-globals summary only",
    )
    mode.add_argument(
        "--unmatched-decoders", action="store_true",
        help="emit list of DSO Decode* handlers with no libgff slot",
    )
    args = ap.parse_args()

    if not args.source.is_file():
        sys.stderr.write(
            f"error: DSO symbols not found at {args.source}\n"
            f"hint: clone greg-kennedy/DarkSunOnline to .dso-online/\n"
            f"      (see docs/dso-symbols.md for licence and scope)\n"
        )
        return 2

    funcs, globs = parse_symbols(args.source)
    matches, _unmatched_libgff = propose_opcode_renames(funcs)
    unmatched_decoders = find_unmatched_decoders(funcs, matches)

    if args.opcodes_proposed:
        print(render_opcode_proposals(matches))
    elif args.functions_summary:
        print(render_functions_summary(funcs))
    elif args.globals_summary:
        print(render_globals_summary(globs))
    elif args.unmatched_decoders:
        print(render_unmatched_decoders_summary(unmatched_decoders))
    else:
        # Default: combined summary, all four sections.
        print(f"DSO symbol import summary (source: {args.source})")
        print(f"  functions: {len(funcs)}")
        print(f"  globals:   {len(globs)}")
        print(f"  opcode-rename proposals: {len(matches)}")
        print(f"  unmatched DSO Decode* handlers: {len(unmatched_decoders)}")
        print()
        print("Use --opcodes-proposed / --functions-summary /")
        print("--globals-summary / --unmatched-decoders to emit each section.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
