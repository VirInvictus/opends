# OpenDS Tools

The toolkit. Each tool is independent and shippable on its own.
Each has its own `README.md` and `VERSION`. Releases are tagged
`<tool>-vX.Y.Z` (forward-only from 2026-09-04; earlier tools are
untagged).

Version history lives in [`../patchnotes.md`](../patchnotes.md)
(newest first); this table describes each tool as it is now.
See [`../docs/versioning.md`](../docs/versioning.md) for the
versioning policy and [`../spec.md`](../spec.md) §7a for the
implementation-language split.

## Shipped

| Tool | Lang | Version | Purpose |
|---|---|---|---|
| [`atlas`](atlas/) | Python | 0.1.1 | **Static-HTML site generator.** Drives image-extract / region-render / dialog-extract against every detected game install and produces a browsable offline `file://` directory: sprite gallery, inline region maps, dialog browser. |
| [`opends`](opends/) | Rust | 0.1.0 | **Umbrella CLI.** "I have this file, what is it?" Auto-dispatches by file magic to the right tool; `opends tools` prints the version table; thin shells over extract / render / find. |
| [`verify-install`](verify-install/) | Python | 0.3.0 | Checks an install against the canonical pristine-hash manifest. Repairs from the GOG installer (`--repair`, `--dry-run`), rolls repairs back (`--rollback`), and answers in one line with `--summary`. |
| [`gff-edit`](gff-edit/) | Rust | 0.6.0 | Pure-Rust GFF read/write (library `gff_edit` + CLI `gff-cat`): dump, extract, replace, text codec, JSON, catalogue, and the `gff-cat what` per-chunk describer. The foundation everything else builds on. |
| [`gpl-disasm`](gpl-disasm/) | Rust | 0.6.0 | GPL bytecode disassembler: text or JSON, CFG labels, curated symbol catalogues (functions, variables, per-chunk locals), inter-chunk callgraph (`--global-cfg`), lossless packed-string decode. |
| [`gpl-asm`](gpl-asm/) | Rust | 0.9.0 | GPL reassembler and patch author: consumes `gpl-disasm` text/JSON (600/600 corpus chunks round-trip byte-identical) and applies fingerprint-checked, label-relative `--patch` byte edits. |
| [`save-inspect`](save-inspect/) | Python | 0.9.5 | Save-file inspector and editor: dump, diff, edit PCs and items, write back with round-trip verification; `save-semantic-diff` annotates save diffs with field meaning. |
| [`dialog-extract`](dialog-extract/) | Python | 0.7.1 | Pulls NPC dialog out of GPL chunks as JSON, a plain-text transcript, or a single-file browsable HTML page. |
| [`image-extract`](image-extract/) | Rust | 0.4.0 | Decodes Dark Sun bitmap chunks to palette-indexed PNG (multi-frame, spritesheets) and packs edited PNGs back as DS1 RLE chunks: the sprite-modding loop. |
| [`region-render`](region-render/) | Rust | 0.7.1 | Composites a region's tiles, walls and entities into a map PNG; animates entities and exports GIF (`--gif`, `--gif-fps`). |
| [`repro`](repro/) | Shell + Python | 0.4.0 | DOSBox-Staging repro harness: per-bug fixtures under overlay mounts (the install is never written), session continuity, scheduled keystrokes, video capture. |
| [`opcode-fuzz`](opcode-fuzz/) | Python | 0.3.0 | GPL opcode-discovery harness: chunk pack/extract/roundtrip, swap-and-run against DOSBox with world-state diffing, and `boot-chunks` to surface directly-dispatched chunks. |
| [`ovr-map`](ovr-map/) | Python | 0.3.0 | Maps `DSUN.EXE`'s Borland overlay structure: segments, entry stubs, 16-bit disassembly, curated symbol catalogue (`syms/<game>.toml`), Ghidra bridges, and the string-xref tooling under `scripts/`. |


## Planned

In roadmap order. See [`../roadmap.md`](../roadmap.md).

| Tool             | Lang             | Phase | Purpose                                              |
|------------------|------------------|-------|------------------------------------------------------|
| `extract.sh`     | Shell            | (deferred) | GOG installer → flat extracted file tree.       |
