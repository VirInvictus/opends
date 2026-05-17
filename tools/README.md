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
| [`gpl-asm`](gpl-asm/)                    | Rust   | 0.5.0   | GPL bytecode reassembler. Consumes `gpl-disasm --json` (600/600 byte-identical) or the text listing in either form. v0.3.0 added the `Editor` API for structural edits; v0.4.0 adds label-relative APIs (`insert_before_label`) and parser support for user-chosen label names. **v0.5.0 ships the author safety net**: rustc-style caret parse errors (`format_with_caret`), and a `validate()` pass (branch-target bounds, Immediate14 overflow, RetVal depth) wired into the binary as the default pre-encode check (`--validate-only`, `--no-validate`). Corpus validates 600 / 600 clean; zero false positives.|
| [`save-inspect`](save-inspect/)          | Python | 0.6.0   | Dump a CHARSAVE.GFF / DARKRUN.GFF / SAVE0N.SAV as JSON, or diff two of them. v0.2 walked CHAR sub-blocks for DS1; v0.4 locked DS2 combat (49 bytes); v0.5 locked DS2 character (66 bytes). **v0.6.0** validates DS2 items (23 bytes) against 151 items across played + factory CHARSAVEs, zero truncations, adds `_format: ds1_item` / `ds2_item` tags. Bonus discovery: `SAVE0N.SAV` is byte-identical to `DARKRUN.GFF` at save time (engine just snapshots one to the other); save-inspect reads both natively as GFFs. The `SAVE` chunk inside `DARKRUN.GFF` (per-region world state) is still un-decoded.|
| [`dialog-extract`](dialog-extract/)      | Python | 0.4.0   | Pull GPL strings (NPC dialog, prompts, NPC names) from GPL/MAS chunks. Consumes `gpl-disasm --json` instruction-aware. `--text-source RESOURCE.GFF` resolves GSTRING refs (v0.2); CFG-aware `dialog_tree` per chunk (v0.3); path-aware LSTR-slot tracking + inter-chunk `gpl global sub` expansion (v0.4). 96.4% of corpus LSTRING refs resolve.|
| [`image-extract`](image-extract/)        | Rust   | 0.2.1   | Extract Dark Sun bitmap chunks (`BMP `, `PORT`, `ICON`, `BMAP`, `OMAP`, `TILE`) as palette-indexed PNG. Decodes DS1 RLE, PLNR, and PLAN frame formats; pulls palettes from `PAL ` / `CPAL` chunks in the same GFF. 99.95% of corpus frames decode (v0.2.0 added PLAN + fixed PLNR's cross-byte chomp). **v0.2.1** root-causes the one remaining failure (DS1 `RESOURCE.GFF:ICON/0x7f9` frame 2 is malformed in the GOG ship) and strengthens the corpus test to pin it as the only expected failure; any new decoder regression now breaks the test.|
| [`region-render`](region-render/)        | Rust   | 0.5.0   | Render a region GFF's full visual stack: background tiles, walls, and entity sprites into a 2048x1568 palette-indexed PNG. v0.4.0 adds `--palette-preset {ds1-pink, ds1-rust, ds1-deep-red}` for one-knob DS1 palette switching. v0.5.0 lands a DSUN.EXE RE pass (`docs/dsun-exe-re.md`) that located the engine's `CMAT[id] -> CPAL[id]` per-region palette routine; default DS1 fallback now uses `CPAL:200` (engine-default) instead of `PAL :1000` (menu palette). Per-region family-id mapping and animated colours still queued.|
| [`repro`](repro/)                        | Shell + Python | 0.2.1 | DOSBox-Staging repro harness. Boots a per-bug fixture under `bugs/<id>/` with overlay-mounted writes (the install stays byte-identical), evaluates pass/fail by elapsed time + scratch-dir artifacts. v0.1.0 shipped the harness pattern + `ds1-smoke`. v0.2.0 added `ds2-smoke` (DS2 boots through `imgmount` of `game.ins` CD audio), DOSBox stderr capture to `<scratch>/dosbox.log`, `--list`, DSUN.LOG preview on early-exit FAIL, and a `bugs/README.md` catalogue. **v0.2.1** adds `--play`: the same setup recipe as the harness (overlay-mount, factory-save staging, sound_ds-generated SOUND.CFG) but with no wall-clock budget, so the recipe that sidesteps the DARKSAVE / MEL gotchas lets you actually play the game instead of just running the regression test. Input automation and video capture roll into v0.3.0.|

## Planned

In roadmap order. See [`../roadmap.md`](../roadmap.md).

| Tool             | Lang             | Phase | Purpose                                              |
|------------------|------------------|-------|------------------------------------------------------|
| `opcode-fuzz`    | Python           | 5     | DOSBox-driven opcode discovery harness.              |
| `extract.sh`     | Shell            | (deferred) | GOG installer → flat extracted file tree.       |
