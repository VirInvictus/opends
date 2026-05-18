# opcode-fuzz recipes

Forward-looking placeholder for templated `.asm` chunks that
will drive the engine through a single opcode in isolation.

**v0.3.0 status: scaffold only.** This directory exists so the
`opcode-fuzz fuzz <opcode>` subcommand (planned v0.3.1+) has a
home for recipe templates. v0.3.0 itself ships only the
`boot-chunks` subcommand (the discovery half: which chunks are
safe to swap because the engine guarantees it'll invoke them);
the recipe-driven `fuzz` half waits until the recipe format
settles.

## Why the wait

`gpl-asm` v0.7.0 parses `gpl-disasm`'s full text listing
(per-line `<offset>  <byte>  <mnemonic>  <params>`). A
modder-authored recipe written in short-form (`gpl byte inc
GBYTE[100]` with no offset / byte prefixes) doesn't round-trip
through the encoder yet. The format options under consideration:

1. **Short-form preprocessor** in `opcode-fuzz fuzz` that
   resolves offsets + bytes from the mnemonic table before
   handing to `gpl-asm`. Authoring stays minimal; opcode-fuzz
   carries the smarts.
2. **JSON recipes**: each recipe is a small chunk-JSON dict
   that the fuzz command serialises and passes to `gpl-asm
   --json`. Machine-friendly; not human-friendly.
3. **gpl-asm extension** that accepts short-form text directly
   (a `gpl-asm v0.8.0` candidate); recipes are plain `.asm`
   files at that point.

The plan favours (3) once `gpl-asm v0.8.0`'s patch-script mode
lands and we know what the modder's "small edit" surface
should look like. Recipes here will be plain `.asm` files at
that point.

## In the meantime

Use `opcode-fuzz boot-chunks <gff>` to identify safe-to-swap
chunks; use `opcode-fuzz extract` + your editor + `opcode-fuzz
pack` to author a one-off test chunk by hand. The full
discovery loop (recipes + boot-chunks + run + structured diff)
ships in v0.3.1+.
