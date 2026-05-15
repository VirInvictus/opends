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
| [`gpl-disasm`](gpl-disasm/)              | Rust   | 0.2.1   | GPL bytecode disassembler. v0.2 ports libgff's `gpl_read_number` + 7-bit packed-string decoder; v0.2.1 closes the deferred cases (RETVAL, COMPLEX_*, setrecord). 100% corpus alignment on DS1+DS2 GPL/MAS. `--json` mode for downstream tools.|
| [`save-inspect`](save-inspect/)          | Python | 0.2.0   | Dump a CHARSAVE.GFF as JSON. v0.2 walks the CHAR record body into combat / character / item sub-blocks (DS1 full schema; DS2 surfaces names + raw hex). PSIN/PSST/TEXT decoded too.|
| [`dialog-extract`](dialog-extract/)      | Python | 0.2.0   | Pull GPL strings (NPC dialog, prompts, NPC names) from GPL/MAS chunks. v0.2 consumes `gpl-disasm --json` instruction-aware; `--text-source RESOURCE.GFF` resolves GSTRING text-id references.|

## Planned

In roadmap order. See [`../roadmap.md`](../roadmap.md).

| Tool             | Lang             | Phase | Purpose                                              |
|------------------|------------------|-------|------------------------------------------------------|
| `repro`          | Shell + Python   | 2     | DOSBox repro harness with per-bug save library.      |
| `region-view`    | Rust + SDL2      | 4     | Render a region GFF (tilemap + sprites + entities).  |
| `gpl-asm`        | Rust             | 5     | GPL bytecode reassembler.                            |
| `opcode-fuzz`    | Python           | 5     | DOSBox-driven opcode discovery harness.              |
| `extract.sh`     | Shell            | (deferred) | GOG installer → flat extracted file tree.       |
