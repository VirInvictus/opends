# OpenDS Tools

The toolkit. Each tool is independent and shippable on its own.
Each has its own `README.md`, `VERSION`, and tagged GitHub
releases.

See [`../docs/versioning.md`](../docs/versioning.md) for the
versioning policy and [`../spec.md`](../spec.md) §7a for the
implementation-language split.

## Shipped

| Tool                                     | Lang   | Version | Purpose                                                                              |
|------------------------------------------|--------|---------|--------------------------------------------------------------------------------------|
| [`verify-install`](verify-install/)      | Python | 0.1.0   | Check a Dark Sun install against the canonical pristine-hash manifest.               |
| [`gff-edit`](gff-edit/)                  | Rust   | 0.4.0   | Pure-Rust GFF read/write (library `gff_edit` + CLI `gff-cat`). Read/write + bulk extract + text codec + JSON + catalogue.|
| [`gpl-disasm`](gpl-disasm/)              | Rust   | 0.4.6   | GPL bytecode disassembler. 100% corpus alignment on DS1+DS2 GPL/MAS. Recursive-descent CFG with labeled branches (v0.3.x), hand-curated symbol catalogue (v0.4.0 / v0.4.2), inter-chunk callgraph (v0.4.1), lossless 7-bit packed-string decoder (v0.4.3), Deserialize impls (v0.4.4), `raw_tail` side-byte preservation (v0.4.5), and a public `render_text` API with round-trippable label / raw_tail rendering (v0.4.6). `--json` mode for downstream tools.|
| [`gpl-asm`](gpl-asm/)                    | Rust   | 0.4.0   | GPL bytecode reassembler. Consumes `gpl-disasm --json` (600/600 byte-identical) or the text listing in either form. v0.3.0 added the `Editor` API for structural edits; v0.4.0 adds label-relative APIs (`insert_before_label`) and parser support for user-chosen label names. The author-friendly half of the GPL loop.|
| [`save-inspect`](save-inspect/)          | Python | 0.2.0   | Dump a CHARSAVE.GFF as JSON. v0.2 walks the CHAR record body into combat / character / item sub-blocks (DS1 full schema; DS2 surfaces names + raw hex). PSIN/PSST/TEXT decoded too.|
| [`dialog-extract`](dialog-extract/)      | Python | 0.4.0   | Pull GPL strings (NPC dialog, prompts, NPC names) from GPL/MAS chunks. Consumes `gpl-disasm --json` instruction-aware. `--text-source RESOURCE.GFF` resolves GSTRING refs (v0.2); CFG-aware `dialog_tree` per chunk (v0.3); path-aware LSTR-slot tracking + inter-chunk `gpl global sub` expansion (v0.4). 96.4% of corpus LSTRING refs resolve.|
| [`image-extract`](image-extract/)        | Rust   | 0.2.0   | Extract Dark Sun bitmap chunks (`BMP `, `PORT`, `ICON`, `BMAP`, `OMAP`, `TILE`) as palette-indexed PNG. Decodes DS1 RLE, PLNR, and PLAN frame formats; pulls palettes from `PAL ` / `CPAL` chunks in the same GFF. 99.95% of corpus frames decode (v0.2.0 adds PLAN + fixes PLNR's cross-byte chomp).|
| [`region-render`](region-render/)        | Rust   | 0.1.0   | Render a region GFF's background-tile layer (`RMAP` DS1 / `MAP ` DS2 + `TILE`) to a 2048x1568 palette-indexed PNG. Static; walls and entities are v0.2+. Closes Phase 4.|

## Planned

In roadmap order. See [`../roadmap.md`](../roadmap.md).

| Tool             | Lang             | Phase | Purpose                                              |
|------------------|------------------|-------|------------------------------------------------------|
| `repro`          | Shell + Python   | 2     | DOSBox repro harness with per-bug save library.      |
| `opcode-fuzz`    | Python           | 5     | DOSBox-driven opcode discovery harness.              |
| `extract.sh`     | Shell            | (deferred) | GOG installer → flat extracted file tree.       |
