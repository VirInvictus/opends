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
| [`gff-edit`](gff-edit/)                  | Rust   | 0.3.0   | Pure-Rust GFF read/write (library `gff_edit` + CLI `gff-cat`). Indexed + segmented; extract + replace.|

## Planned

In roadmap order. See [`../roadmap.md`](../roadmap.md).

| Tool             | Lang             | Phase | Purpose                                              |
|------------------|------------------|-------|------------------------------------------------------|
| `repro`          | Shell + Python   | 2     | DOSBox repro harness with per-bug save library.      |
| `gpl-disasm`     | Rust             | 3     | GPL bytecode disassembler.                           |
| `dialog-extract` | Python           | 4     | Pull NPC dialog trees out as structured JSON.        |
| `save-inspect`   | Python           | 4     | Read and diff `CHARSAVE.GFF` as JSON.                |
| `region-view`    | Rust + SDL2      | 4     | Render a region GFF (tilemap + sprites + entities).  |
| `gpl-asm`        | Rust             | 5     | GPL bytecode reassembler.                            |
| `opcode-fuzz`    | Python           | 5     | DOSBox-driven opcode discovery harness.              |
| `extract.sh`     | Shell            | (deferred) | GOG installer → flat extracted file tree.       |
