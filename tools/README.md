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
| [`gpl-asm`](gpl-asm/)                    | Rust   | 0.6.0   | GPL bytecode reassembler. Consumes `gpl-disasm --json` (600/600 byte-identical) or the text listing in either form. v0.3.0 added the `Editor` API for structural edits; v0.4.0 adds label-relative APIs and user-chosen label names. v0.5.0 shipped the author safety net (caret-style parse errors + a `validate()` pass wired as the default pre-encode check). **v0.6.0** adds the preprocessor: `%define <name> <replacement>` for token substitution (with reject lists for operator words / variable shorts / keyword tokens / mnemonic words) and `%search-tail <hex-bytes>` for ergonomic raw-tail composition on `gpl_search`. Directive lines blank-replace so caret error line numbers still match the user's source. Corpus stays at 600 / 600.|
| [`save-inspect`](save-inspect/)          | Python | 0.6.0   | Dump a CHARSAVE.GFF / DARKRUN.GFF / SAVE0N.SAV as JSON, or diff two of them. v0.2 walked CHAR sub-blocks for DS1; v0.4 locked DS2 combat (49 bytes); v0.5 locked DS2 character (66 bytes). **v0.6.0** validates DS2 items (23 bytes) against 151 items across played + factory CHARSAVEs, zero truncations, adds `_format: ds1_item` / `ds2_item` tags. Bonus discovery: `SAVE0N.SAV` is byte-identical to `DARKRUN.GFF` at save time (engine just snapshots one to the other); save-inspect reads both natively as GFFs. The `SAVE` chunk inside `DARKRUN.GFF` (per-region world state) is still un-decoded.|
| [`dialog-extract`](dialog-extract/)      | Python | 0.5.0   | Pull GPL strings (NPC dialog, prompts, NPC names) from GPL/MAS chunks. Consumes `gpl-disasm --json` instruction-aware. v0.2 resolves GSTRING refs via `--text-source`; v0.3 builds a CFG-aware `dialog_tree`; v0.4 path-aware LSTR-slot tracking + cross-chunk expansion. **v0.5.0** closes the LSTR tail: the 32 previously-unresolved reads now each carry a callgraph-narrowed `possible_writers` array (avg ~4-7 candidates per read; zero reads have no writers anywhere in the corpus). New `lstr_stats` top-level field; stderr summary at end of run.|
| [`image-extract`](image-extract/)        | Rust   | 0.2.1   | Extract Dark Sun bitmap chunks (`BMP `, `PORT`, `ICON`, `BMAP`, `OMAP`, `TILE`) as palette-indexed PNG. Decodes DS1 RLE, PLNR, and PLAN frame formats; pulls palettes from `PAL ` / `CPAL` chunks in the same GFF. 99.95% of corpus frames decode (v0.2.0 added PLAN + fixed PLNR's cross-byte chomp). **v0.2.1** root-causes the one remaining failure (DS1 `RESOURCE.GFF:ICON/0x7f9` frame 2 is malformed in the GOG ship) and strengthens the corpus test to pin it as the only expected failure; any new decoder regression now breaks the test.|
| [`region-render`](region-render/)        | Rust   | 0.5.0   | Render a region GFF's full visual stack: background tiles, walls, and entity sprites into a 2048x1568 palette-indexed PNG. v0.4.0 adds `--palette-preset {ds1-pink, ds1-rust, ds1-deep-red}` for one-knob DS1 palette switching. v0.5.0 lands a DSUN.EXE RE pass (`docs/dsun-exe-re.md`) that located the engine's `CMAT[id] -> CPAL[id]` per-region palette routine; default DS1 fallback now uses `CPAL:200` (engine-default) instead of `PAL :1000` (menu palette). Per-region family-id mapping and animated colours still queued.|
| [`repro`](repro/)                        | Shell + Python | 0.3.0 | DOSBox-Staging repro harness. Boots a per-bug fixture under `bugs/<id>/` with overlay-mounted writes (the install stays byte-identical), evaluates pass/fail by elapsed time + scratch-dir artifacts. v0.1.0 shipped the harness pattern + `ds1-smoke`. v0.2.0 added `ds2-smoke`, DOSBox stderr capture, `--list`, DSUN.LOG preview. v0.2.1 added `--play` (no time budget; play through the harness's setup). **v0.3.0** makes `--play` resumable via `--session <name>` (stable scratch path at `$XDG_STATE_HOME/opends-repro/play-<game>-<session>/`; in-game saves persist across runs), plus `--list-sessions` and `--reset-session`. Input automation + video capture queued for v0.3.x / v0.4.0+ (need dep approvals).|

| [`opcode-fuzz`](opcode-fuzz/)            | Python | 0.1.0   | Phase 5's second tool: the eventual GPL opcode-discovery harness. **v0.1.0** ships the chunk-patchwork pipeline (`extract` / `pack` / `roundtrip`): pull a GPL chunk into a work-dir, edit its disassembly, repack it back into the GFF. The corpus roundtrip self-test verifies every GPL/MAS chunk in DS1 (250/250) and DS2 (350/350) survives extract→disasm→reasm→replace byte-identical. The DOSBox-side observation loop (swap a chunk, run the engine, diff DARKRUN.GFF) is v0.2.0+.|

## Planned

In roadmap order. See [`../roadmap.md`](../roadmap.md).

| Tool             | Lang             | Phase | Purpose                                              |
|------------------|------------------|-------|------------------------------------------------------|
| `extract.sh`     | Shell            | (deferred) | GOG installer → flat extracted file tree.       |
