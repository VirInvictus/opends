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
| [`gpl-disasm`](gpl-disasm/)              | Rust   | 0.1.0   | GPL bytecode disassembler. v0.1 = byte-annotation pass with libgff's 129-entry opcode catalogue. Parameter decoding lands in v0.2.|
| [`save-inspect`](save-inspect/)          | Python | 0.1.0   | Dump a CHARSAVE.GFF as JSON. Decodes PSIN/PSST/TEXT and the CHAR RDFF header; opaque hex preview for CHAR body, SPST, CACT, PREF, GREQ.|

## Planned

In roadmap order. See [`../roadmap.md`](../roadmap.md).

| Tool             | Lang             | Phase | Purpose                                              |
|------------------|------------------|-------|------------------------------------------------------|
| `repro`          | Shell + Python   | 2     | DOSBox repro harness with per-bug save library.      |
| `dialog-extract` | Python           | 4     | Pull NPC dialog trees out as structured JSON.        |
| `region-view`    | Rust + SDL2      | 4     | Render a region GFF (tilemap + sprites + entities).  |
| `gpl-asm`        | Rust             | 5     | GPL bytecode reassembler.                            |
| `opcode-fuzz`    | Python           | 5     | DOSBox-driven opcode discovery harness.              |
| `extract.sh`     | Shell            | (deferred) | GOG installer → flat extracted file tree.       |
