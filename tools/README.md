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
| [`gpl-disasm`](gpl-disasm/)              | Rust   | 0.2.0   | GPL bytecode disassembler. v0.2 ports libgff's `gpl_read_number` + the 7-bit packed-string decoder, so output is one row per instruction with decoded parameters. `--json` mode for downstream tools.|
| [`save-inspect`](save-inspect/)          | Python | 0.1.0   | Dump a CHARSAVE.GFF as JSON. Decodes PSIN/PSST/TEXT and the CHAR RDFF header; opaque hex preview for CHAR body, SPST, CACT, PREF, GREQ.|
| [`dialog-extract`](dialog-extract/)      | Python | 0.1.0   | Pull GPL inline strings (NPC dialog, prompts) from GPL/MAS chunks via heuristic IMMED_STRING scan + 7-bit decoder.|

## Planned

In roadmap order. See [`../roadmap.md`](../roadmap.md).

| Tool             | Lang             | Phase | Purpose                                              |
|------------------|------------------|-------|------------------------------------------------------|
| `repro`          | Shell + Python   | 2     | DOSBox repro harness with per-bug save library.      |
| `region-view`    | Rust + SDL2      | 4     | Render a region GFF (tilemap + sprites + entities).  |
| `gpl-asm`        | Rust             | 5     | GPL bytecode reassembler.                            |
| `opcode-fuzz`    | Python           | 5     | DOSBox-driven opcode discovery harness.              |
| `extract.sh`     | Shell            | (deferred) | GOG installer → flat extracted file tree.       |
