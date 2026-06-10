# OpenDS — Design Spec

This document captures the design invariants and architectural
decisions for OpenDS. It is the source of truth for "what we are
building"; [`roadmap.md`](roadmap.md) tracks "in what order."

## 1. Scope

OpenDS is a **community toolkit** for SSI's Dark Sun CRPGs:

- *Dark Sun: Shattered Lands* (1993, GOG-shipped 1.10)
- *Dark Sun: Wake of the Ravager* (1994, GOG-shipped 1.10)

Three product surfaces, each shippable on its own and ordered
by priority:

1. **Modding toolkit (Goal 1)** — public, MIT-licensed tools
   under [`tools/`](tools/) that let anyone read, inspect,
   edit, and repack the game's files: GFF reader/writer
   (`gff-edit`), GPL disassembler/assembler, region viewer,
   dialog extractor, save inspector, install verifier. The
   toolkit is the primary deliverable. It serves any mod
   author, not just our own patch work.
2. **darkfix patches (Goal 2)** — unofficial bugfix patches
   per game, under [`ds1-patch/`](ds1-patch/) and
   [`ds2-patch/`](ds2-patch/). Applied to the player's GOG
   install; the game still runs in DOSBox under the original
   engine. These are our application of the toolkit, not the
   reason for it. A community mod author with different goals
   uses the same tools.
3. **Documentation** — every reverse-engineering finding is
   written into [`docs/`](docs/) so the next person doesn't
   have to redo the work. Cross-cutting; supports both Goal 1
   and Goal 2.

What OpenDS is **not** (now):

- Not a from-scratch engine reimplementation. That is the
  long-term aspiration the name encodes; it is not the v1
  deliverable. See §12.
- Not a content mod (no new quests, no new items, no new
  regions).
- Not a re-balance.
- Not a port (still DOSBox; still DOS).

## 1a. Why a toolkit, not an engine

Multiple public engine reimplementation attempts going back to
2004 have stalled before producing a playable game (Dark Sun
World, the 2010s DSO emulator, soloscuro-archive at ~567 commits,
several other dsoageofheroes prototypes, the Beamdog Infinity
Engine port). The blocker each time is the GPL bytecode VM:
no public spec, lots of game logic, hard to verify against the
original.

OpenDS reframes the problem. Instead of "build the whole engine
in one push," we ship the artifacts you accumulate *on the way*
to an engine — disassemblers, chunk editors, format
documentation, bug patches — as standalone, useful tools. Each
one is valuable on its own. Each one chips at the GPL VM
problem. Each one is something a future engine project can pick
up and use rather than reinvent.

## 1b. Tools-first ordering

A consequence of §1a, reinforced by the Goal 1 / Goal 2 split
in §1: **anything that makes the digging easier is priority
over any specific patch.** Tools that help anyone read, locate,
edit, and verify the game's internals ship before the patches
that consume them. The patch phases of the
[roadmap](roadmap.md) (Phase 6 onward) start when the toolkit
is sharp enough that authoring fixes is plumbing rather than
archaeology.

This ordering also reflects who the toolkit serves: mod
authors first, our own patch authoring second. We are one
consumer of the toolkit among many. Tools first means each
new tool benefits every later one, and the eventual darkfix
patches inherit the leverage of the whole toolkit instead of
being authored against ad-hoc one-off code.

## 2. Target platform

- **Player platform**: anywhere the GOG release runs — primarily
  Windows, Linux, macOS. The patch is applied to the installed game
  files, then the user launches via the GOG/DOSBox launcher as usual.
- **Authoring platform**: Linux x86_64, Fedora 43+. All tooling
  (DOSBox-Staging, `gff-tool`, radare2/Ghidra, hash utilities) is
  available natively.

The patch artifact is platform-agnostic: it's a zip of edited GFF
chunks plus a binary diff for `DSUN.EXE`, plus a small applier
script in Python or shell.

## 3. Two patch surfaces

Every fix lives on one of two surfaces:

### 3.1. Data surface (GFF edits)

Most quest bugs are GPL bytecode bugs (wrong flag set on the wrong
event, missing branch, off-by-one) and some are item/region/
dialogue data bugs. These live in `GPLDATA.GFF`, `RESOURCE.GFF`,
`SEGOBJEX.GFF`/`OBJEX.GFF`, and the various `RGN*.GFF` files.

Authoring tool: **`gff-tool`** from
[`JohnGlassmyer/dsun_music`](https://github.com/JohnGlassmyer/dsun_music)
— the only public GFF *writer*. We extract a chunk, edit, replace.

Each fix produces:

- A short markdown writeup in `dsN-patch/fixes/<id>.md`.
- A per-fix script (Python; see §7a) that takes the original GFF
  and emits the patched GFF.
- A test record: hash of the original chunk, hash of the patched
  chunk.

### 3.2. Binary surface (DSUN.EXE patches)

Bugs that the GPL scripts cannot reach (combat AI loops, sprite
culling, save/exit bugs) live in `DSUN.EXE`. We patch the executable
directly.

Authoring tools: **radare2** (preferred — scriptable, on Fedora as
`r2`) or **Ghidra** for analysis; Python `pwntools`/`keystone-engine`
or hand-assembled hex for emitting patches.

Each binary fix:

- Identified by exact byte offsets and original-byte fingerprints in
  the canonical 1.10 GOG `DSUN.EXE`.
- Refuses to apply if the fingerprint doesn't match (we will not
  overwrite an already-patched binary or a non-1.10 build).
- Distributed as a `.bsdiff` or hand-rolled `(offset, original, replacement)`
  triples.

## 4. Patch artifact format

A darkfix patch is a directory tree:

```
darkfix-ds2-v0.1.0/
├── manifest.toml         # version, target hashes, fix list
├── fixes/
│   ├── data/
│   │   ├── 001-mines-elevator.bin    # patched GFF chunk
│   │   └── ...
│   └── binary/
│       ├── 042-combat-ai.bsdiff
│       └── ...
└── apply.py              # the applier
```

`manifest.toml` declares:

- Target game (`ds1` or `ds2`)
- Required source hashes (rejects mismatched installs)
- Ordered list of fixes with on/off state
- Version, license, contact info

`apply.py`:

- Verifies source-file hashes match the manifest.
- Backs up touched files to `darkfix-backup/` next to them.
- Applies each enabled fix.
- Writes a `darkfix-applied.json` next to the game files for
  later un-applying or upgrading.

Reverse step (`apply.py --unapply`) restores from `darkfix-backup/`.

## 5. Fix policy

Each fix:

1. Targets a documented bug (preserved in
   [`docs/known-bugs.md`](docs/known-bugs.md) or a new entry).
2. Ships with a writeup explaining the symptom, the root cause,
   and the patch.
3. Has a stable identifier (`fix.ds2.mines-elevator`) that
   survives renumbering.
4. Is **on by default** if it is a clear bug.
5. Is **off by default** if it is balance-affecting (XP exploits,
   item duplication, etc.). User can enable in the manifest.
6. Has a regression test: the bug is reproducible on a clean install,
   and the bug is gone on a patched install.

Fixes are not bundled into one giant patch. Each fix is independent
and can be enabled or disabled.

## 6. GPL bytecode

Quest fixes require disassembling, editing, and reassembling GPL
("Game Programming Language") bytecode chunks. The authoring stack:

1. **`gpl-disasm`** — our own disassembler. Reads `GPL ` chunks,
   emits annotated mnemonic source. Built incrementally; opcodes
   that aren't decoded yet are emitted as `db` byte literals.
2. **Manual editing** — we hand-edit the disassembly in the patch
   we author. No reassembler in v1; we patch bytes directly using
   the disassembler's offset annotations.
3. **`gpl-asm`** — eventual reassembler that takes our disassembly
   format back to bytecode. Not blocking for v1 patches.

`soloscuro-archive`'s partial GPL parser is the closest public
prior art and the starting point. The DSO v1.0 client (per
greg-kennedy's wiki) shipped with debug symbols including GPL
function names — the highest-value cross-reference we have.

See [`docs/gpl-bytecode.md`](docs/gpl-bytecode.md).

## 7. Tooling stack

| Tool                  | Purpose                                  |
|-----------------------|------------------------------------------|
| `innoextract`         | Unpack GOG installer EXE                 |
| `dsun_music gff-tool` | Read/write GFF chunks                    |
| `libgff gfftool`      | Reference reader, extraction sanity      |
| `dosbox-staging`      | Run the original game for repro/testing  |
| `radare2` / `r2`      | Disassemble & patch DSUN.EXE             |
| `ghidra`              | Heavier static analysis on DSUN.EXE      |
| `bsdiff` / `bspatch`  | Distribute binary patches                |
| `python3` (+ `bsdiff4`)| Applier script and authoring helpers    |
| `flac`/`vorbis-tools` | Inspect DS2 redbook OGG tracks (rarely)  |

All available on Fedora via `dnf` (or pip/cargo for niche tools).
See [`docs/build-environment.md`](docs/build-environment.md).

## 7a. Implementation languages

OpenDS tools we author are written in **Rust or Python**, split
by role:

| Role                                                          | Language | Why                                                                              |
|---------------------------------------------------------------|----------|----------------------------------------------------------------------------------|
| Foundation libraries (other tools depend on them)             | Rust     | Correctness and perf matter; engine-inheritable.                                 |
| Heavy-lifting tools (disassembler, assembler, region renderer)| Rust     | Throughput-bound; benefit from strict types; single-binary distribution.         |
| CLI utilities (verify, inspect, extract-as-JSON)              | Python   | Iteration-bound; stdlib-preferred; no build step for contributors.               |
| Patch authoring scripts and applier                           | Python   | User-runnable; readable by anyone reviewing a fix.                               |

Tool-by-tool assignment:

| Tool                                  | Language                                          |
|---------------------------------------|---------------------------------------------------|
| `verify-install`                      | Python                                            |
| `gff-edit` (library) + `gff-cat` (CLI)| Rust                                              |
| `repro/` (DOSBox harness)             | Shell + Python glue                               |
| `gpl-disasm`                          | Rust                                              |
| `dialog-extract`                      | Python                                            |
| `save-inspect`                        | Python                                            |
| `region-view`                         | Rust                                              |
| `gpl-asm`                             | Rust                                              |
| `opcode-fuzz`                         | Python (drives DOSBox debugger over IPC)          |
| Per-fix patch scripts                 | Python                                            |
| `apply.py` (applier)                  | Python                                            |

**Language defaults**

- Python target: **3.11 or newer** (we rely on `tomllib` in
  stdlib).
- Python tools are **stdlib-only** by default. Adding a
  third-party dependency requires per-tool justification. The
  single pre-approved exception is `bsdiff4` for the applier
  (binary patches need bsdiff; we are not writing one from
  scratch).
- Rust target: **stable channel, edition 2024**. A minimal
  dependency tree is acceptable from the start: `clap` for CLI
  parsing, `anyhow` / `thiserror` for errors, `serde` plus
  `toml` / `serde_json` where format I/O is needed. Anything
  beyond requires per-tool justification.

**Why both languages, not one**

A single-language toolkit was considered. Python-only loses the
engine-inheritable foundation Rust gives (`gff-edit`,
`gpl-disasm`, `gpl-asm`, `region-view`): those crates are
exactly the artifacts a future engine project would want to
absorb without rewriting. Rust-only adds build complexity to
tools that don't need it (verify-install, per-fix scripts, the
applier) and slows reverse-engineering iteration on small
exploratory tools. The split-by-role tax is one extra toolchain
on the contributor's machine; the gain is each tool fits its
workload, and the artifacts that matter long-term are written
in the language that benefits.

## 8. Repository layout

```
opends/
├── README.md
├── spec.md                 # this file
├── roadmap.md
├── patchnotes.md
├── logo.svg
├── .gitignore              # .games/, scratch/
├── docs/
│   ├── research.md         # engine research
│   ├── file-formats.md     # GFF and chunks
│   ├── known-bugs.md       # the target bug list
│   ├── upstream-projects.md
│   ├── build-environment.md
│   ├── gpl-bytecode.md
│   ├── binary-patching.md
│   └── patch-workflow.md
├── ds1-patch/              # darkfix patch for Shattered Lands
│   ├── README.md
│   ├── manifest.toml
│   ├── fixes/              # one .md + script per fix
│   └── scripts/            # apply.py and helpers
├── ds2-patch/              # darkfix patch for Wake of the Ravager
│   ├── README.md
│   ├── manifest.toml
│   ├── fixes/
│   └── scripts/
├── tools/                  # the public toolkit
│   ├── verify-install/     # hash a player's install
│   ├── gpl-disasm/         # GPL bytecode disassembler
│   ├── gff-edit/           # GFF chunk editor (Rust)
│   └── ...                 # one folder per tool
└── .games/     (gitignored) # GOG installers + unpacked
                             # game files (.games/ds1, ds2)
```

The repo name `opends` is the umbrella project. The patches
shipped from inside it are referred to as **darkfix patches**
(`darkfix-ds1`, `darkfix-ds2`) — that's the name players and
release artifacts see. Tools are referred to by their own names
(`gpl-disasm`, etc.). When the engine eventually exists, it
inherits the umbrella name: OpenDS.

## 9. Versioning

- Each game's patch versions independently:
  `darkfix-ds1-vMAJOR.MINOR.PATCH`, `darkfix-ds2-vMAJOR.MINOR.PATCH`.
- MAJOR for breaking format / target changes.
- MINOR for new fixes.
- PATCH for fixes-to-fixes.
- Repository tag is `vYYYY.MM.X` for the umbrella; per-game
  releases are GitHub releases with their own tags.

## 10. Distribution

Per-game GitHub releases under `github.com/virinvictus/darkfix`.
Each release is a single zip:

- `darkfix-ds1-v0.1.0.zip` for DS1
- `darkfix-ds2-v0.1.0.zip` for DS2

User downloads, unzips, runs `python3 apply.py /path/to/game`.

A future Flatpak helper can wrap this for Linux desktop users; not
in v1 scope.

## 11. Testing

Three levels:

1. **Unit** — patch script applies cleanly to a known-hash source
   and produces a known-hash output.
2. **In-game** — DOSBox-Staging runs the patched game; a recorded
   playthrough trace reproduces the bug-trigger and the bug doesn't
   fire.
3. **Manual** — Brandon plays the game.

CI runs unit tests only. In-game and manual run locally.

## 12. Engine (deferred — the aspiration in the name)

A from-scratch engine remains the long-term goal the name
*OpenDS* encodes. The project does not promise it. The toolkit
and patches are the v1 deliverables; the engine is what becomes
*possible* if the toolkit gets good enough.

Concretely: when we have a working GPL disassembler, a
GPL reassembler, a GFF reader/writer in our preferred language,
a region renderer prototype, and enough documented opcodes to
read the bulk of `GPLDATA.GFF` — *then* an engine project is no
longer an act of single-handed reverse-engineering. It's
plumbing. At that point, spinning it up makes sense.

Not before. Not as a roadmap commitment. We get there if we get
there. Every shipped tool and patch is independently valuable.

## 13. Tool publication policy

Every utility built in service of a fix is a candidate for
public release as a standalone tool, even tools we initially
build "just for our own use." If a tool would help anyone else
working on Dark Sun (or any other GFF-based SSI title), it
ships:

- Its own README, with examples and known limitations.
- MIT license unless there's a specific reason otherwise.
- An entry in `tools/README.md` (an index of the toolkit).
- Versioned releases when meaningful (a parser that gets
  better over time deserves tags).

If a tool turns out to have wider applicability than Dark Sun
specifically (e.g., a generic GFF inspector), we factor it into
its own repo and link from the toolkit index — but we don't do
this prematurely. One repo until friction proves we need two.

## 14. Open questions

- Do we want one umbrella repo (current plan) or two repos
  (`darkfix-ds1`, `darkfix-ds2`)? Current: umbrella with subfolders.
- License — MIT for tooling, what for the patches themselves?
  (Patches don't include game data, but they are derived works of
  reverse-engineering. MIT or Public Domain likely.)
- How to handle the GOG-Linux-DOSBox `cloud_saves/` directory in
  the applier — back it up too, or leave it alone?
- Should we publish the GPL disassembly itself, or treat it as
  internal-only (for risk-reducing the project's relationship with
  WotC's IP)?
