# ovr-map

Map the Borland overlay structure of a Dark Sun `DSUN.EXE`. Turns the
engine binary from a 600 KB blob you hex-search into a segmented,
addressable artifact: which overlay segment covers a file offset, where
each segment really starts, and which addresses are confirmed function
entries.

Everything else in the toolkit stops at the GFF containers. This reads
the engine binary itself.

- **Language**: Python (stdlib only).
- **Requires**: Python 3.11+.
- **Version**: see [`VERSION`](VERSION).
- **License**: MIT.

## Usage

### Summary (default mode)

```sh
python3 ovr-map.py .games/ds1/DSUN.EXE
```

```
.games/ds1/DSUN.EXE  (611408 bytes)
  MZ image ends   0x52ea0   header 0x5400   relocations 4853
  overlay base    0x52eb0   ovrsize 271776
  descriptor tbl  0x46e60

  segments        52  (6 empty records skipped)
  entry points    935
  overlaid        253109 bytes (247 KB)
  area covered    93.13%
```

### Full map as JSON

```sh
python3 ovr-map.py .games/ds1/DSUN.EXE --json
```

Per segment: descriptor offset, payload offset, size, relocation count,
file range, and the entry-stub list (stub offset, `cs:` entry offset,
resolved file offset).

### What is at this address

```sh
python3 ovr-map.py .games/ds1/DSUN.EXE --verify 0x568be
```

Names the segment, the offset within it, and the nearest preceding entry
point. This is the query the patch workflow needs: it catches a site that
has drifted, straddles a segment boundary, or lands in the inter-segment
padding rather than in code.

### Disassemble a segment at its correct base

```sh
python3 ovr-map.py .games/ds1/DSUN.EXE --disasm 4 --limit 40
```

Shells out to `ndisasm -b 16` (install `nasm`) with the segment's real
base, and inserts a labelled banner at every entry stub. Offsets in the
output are segment-local, so they line up with the `cs:` values in the
stubs and in `docs/dsun-exe-re.md`.

⚠ The 16-bit width is not optional. Decoding this binary as 32-bit does
not error, it produces convincing garbage.

### Call graph

```sh
python3 ovr-map.py .games/ds1/DSUN.EXE --callgraph
```

Far-call edges whose target is an entry stub. An overlaid routine is
never called at its own address, so the edge points at the stub in the
resident image, not at the function.

Candidates are filtered against the MZ relocation table: a real
`9A off:2 seg:2` has its segment word fixed up at load time, so that
word's location appears there. Without that filter a raw `0x9A` scan is
mostly false positives.

⚠ **This graph is deliberately incomplete and says so.** Only ~12-14% of
stubs have a direct caller; the rest are reached indirectly or by table
dispatch. A stub absent from the edge list is **not** evidence that it is
unreachable. The tool reports coverage rather than implying completeness.

### Named symbols (`--syms`)

```sh
python3 ovr-map.py .games/ds1/DSUN.EXE --syms syms/ds1.toml --verify 0x58b4
python3 ovr-map.py .games/ds2/DSUN.EXE --syms syms/ds2.toml --disasm 5
```

Loads a curated symbol catalogue and renders names in three places:
`--verify` gains `name` / `confidence` / `evidence` fields when the
offset is a catalogued function, `--disasm` entry separators carry
`<name>`, and `--callgraph` edges gain a `callee_name` field (plus a
`named callees hit` line).

The catalogues live in `syms/<game>.toml`; their header comment is the
schema and the curation rule (rows carry an evidence chain, a
confidence level, and are hand-accepted; machine proposals from
`scripts/propose-exe-symbols.py` are review input, never commits).
`--selftest` validates the shipped catalogues against the parsed maps,
so a typo'd segment index or a row past a segment's end fails loudly
instead of silently never matching. Names are facts we can cite; the
DSO offsets they came from are not (docs/dso-symbols.md).

### Ghidra bridge

```sh
python3 ovr-map.py .games/ds1/DSUN.EXE --ghidra -o OvrMap.java
```

Emits a self-contained Ghidra script. Drop it in your Ghidra scripts
directory, import `DSUN.EXE`, and run it from the Script Manager.

Ghidra's MZ loader maps only the resident image (as `CODE_n` blocks).
Everything past the `FBOV` header, which is where the overlaid code
lives, is **not mapped at all**. The script creates one overlay memory
block per segment at its correct base, fills it from the file, labels
every entry stub as `ovrNN_XXXX`, and labels the matching stub in the
resident image as `stub_ovrNN_XXXX` so a caller's far call reads as a
name.

Verified headless against Ghidra 12.1.2: 52 blocks, 935 labels, and
`ovr04_042e` lands on `55 8b ec 83 ec 0e`, the dispatcher prologue in
`docs/dsun-exe-re.md` §3.1.

Notes, each of which cost a debugging round:

- **Java, not Python.** Ghidra 12 dropped Jython; Python scripts now
  need a PyGhidra (jpype) install. Java scripts run on a stock Ghidra,
  which matters for a public toolkit.
- **Ghidra's MZ loader already selects `x86:LE:16:Real Mode`.** No
  manual language choice is needed for an MZ import (it is only needed
  if you import as raw binary).
- ⚠ **An overlay block lives in its own address space.** Addresses
  inside it must come from `block.getStart()`, not from the default
  space. Labelling through the default space silently lands in `ram:`
  and points at unrelated bytes rather than erroring.
- ⚠ **Segment bases are allocated consecutively, not on a fixed
  stride.** A `0x1000`-paragraph stride overflows the 16-bit segment
  range at segment 57. `ovr-map` assigns bases from the segments' real
  sizes and errors if the layout will not fit.

### Ghidra rename bridge (`--ghidra-rename`)

```sh
python3 ovr-map.py .games/ds1/DSUN.EXE --ghidra-rename syms/ds1.toml -o OvrRename.java
```

Generates the catalogue-driven companion to the `--ghidra` script: it
applies a `syms/<game>.toml` catalogue to the imported program,
creating a named function and label at every catalogue row with the
row's confidence and evidence as a comment. Run it after `OvrMap.java`
in the same headless session, so the overlay blocks exist for overlay
rows. Pair both with `ghidra/OvrExport.java` (checked in, static) to
write the final function list as TSV.

The full headless recipe, including the dot-free path rules that make
it runnable from this checkout, is in `docs/re-tooling.md`.

### Helper scripts (`scripts/`)

- `propose-exe-symbols.py` — the naming-campaign worklist
  generator (see the roadmap's 5.6.1): `--census` resolves every
  overlay far-call to exact `seg:off` resident targets with
  `55 8B EC` evidence marks, `--strings` finds source-file string
  anchors beside the DSO prefix census, and `--anchors` renders
  curated rows into `syms/` catalogue format. Proposals are review
  input; the script never writes `syms/`.
- `xref-string.py` — string cross-references: given a resident
  string, finds the `push`/`mov` immediates that reference it
  (DS-relative against DGROUP, auto-discovered from the entry
  point). The tool behind the catalogue's verified anchors.
- `gpl-xref.py` — the GPL↔EXE index: joins `66 68 <FOURCC>` push
  sites (with immediate ids) and their loader calls against a
  `gpl-disasm --global-cfg --json` chunk inventory, answering
  "which EXE code loads which chunk kind".
- `diff-official.py` — the cluster-annotated official-patch
  differ: signature-checked segment pairing, per-cluster offsets in
  both binaries, nearest-entry ndisasm excerpts (CD 1.0 vs GOG
  1.10 by default).

### Self-test

```sh
python3 ovr-map.py --selftest
```

Asserts the structural invariants against `.games/ds1` and `.games/ds2`
and skips cleanly when they are absent, matching the corpus-test pattern
of the Rust tools. It lives in the tool rather than a separate suite
because the Python tools here are single-file and the repo has no Python
test harness (CI gates them with ruff plus `compileall`).

Checked: FBOV present at the image end, at least one non-empty segment,
no descriptor range past EOF, no segment starting before the overlay
area or overlapping the resident image, no two segments overlapping, no
entry stub pointing outside its own segment, and coverage above 92%.

## Format notes

Both games are **Borland/TLINK (VROOM) overlaid 16-bit real-mode** MZ
programs, not DOS/4GW. See [`docs/dsun-exe-re.md`](../../docs/dsun-exe-re.md)
§1 and §3.5 for the evidence and the calling mechanism.

Layout, as parsed here:

| Where | What |
|---|---|
| MZ image | the program itself, not a stub (~4,850 relocations) |
| image end | `FBOV` header: `ovrsize`, `exeinfo`, `segnum` |
| `+16` | the overlay area begins |
| descriptor table | 32-byte records, each followed by its entry stubs |

Each 32-byte descriptor:

```
+0x00  CD 3F 00 00   INT 3Fh signature
+0x04  dword         payload offset, relative to the overlay area
+0x08  word          segment size
+0x0a  word          relocation count
+0x0c  dword         entry-stub count
```

then exactly that many 5-byte stubs (`CD 3F <entry_offset:2> <ovr:1>`),
then padding to a 16-byte boundary.

⚠ **Two things make a naive parse wrong**, both of which cost a pass
during development:

1. `exeinfo` does **not** point at the descriptor table. It points at a
   block of 8-byte records followed by the overlay's own filename
   (`darkcd.exe` in DS1); the table starts after that. `ovr-map` anchors
   on `exeinfo` and validates the whole chain, so a wrong start derails
   immediately rather than silently.
2. A stub whose `entry_offset` is `0` is byte-identical to a descriptor
   prefix (DS1 has one at `0x46fd5`, in the palette dispatcher's own
   segment). Any heuristic that sniffs for the next descriptor
   miscounts. The explicit stub count at `+0x0c` is what makes the walk
   deterministic, so use it.

Zero-size descriptors are legitimate empty overlay slots (DS1 has 6).
They are parsed and reported, but excluded from the segment count.

## Verified against

`--verify 0x568be` reproduces the §3.5 worked example independently:
segment file range `0x56490..0x56be0`, stub at `0x46fd0`, `cs:0x042e`,
flagged as a confirmed entry point. The descriptor table terminates
exactly where the `Borland C++` copyright string begins, which is the
end-of-table check.
