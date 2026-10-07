# opcode-fuzz recipes

Templated `.asm` chunks that drive the engine through a single
opcode in isolation.

**v0.3.1 status: the loop runs; recipes still wait on one
gpl-asm extension.** The 2026-10-07 first drive of the full loop
(extract -> author chunk.json -> pack -> run -> DARKRUN diff)
works end to end: `run` synthesises its repro fixture, boots the
game through the harness, and computes the diff (that first drive
also fixed two latent tool bugs: the fixture TOML refused the
DOS redirect path's backslash, and the factory DARKRUN path
predated the current install layout). Two findings now shape the
recipe format:

1. **The observation channel must be world-state, not VM state.**
   The sentinel probe (two `gpl byte inc GBYTE[100]` around a
   `gpl global ret`, swapped into boot candidate GPL-9) ran clean
   and changed nothing in DARKRUN.GFF: VM globals do not surface
   in the world-state file, so a sentinel diff shows nothing
   until a save is taken. The recipe epilogue should instead
   perform a world-visible act attributable to the probe (e.g.
   `gpl request 5` to toggle a world object's state bit, whose
   visible-object record the world file carries), or the diff
   must read a post-probe in-game save.
2. **Gap-opcode probes need raw-byte emission.** The 15 unnamed
   opcodes (0x26, 0x4a, 0x4c-0x4e, 0x53, 0x55-0x57, 0x60,
   0x71-0x75) are all `ParamSpec::Custom` in the catalogue:
   gpl-disasm decodes them best-effort (opcode byte only) and
   gpl-asm refuses best-effort instructions, so no JSON or text
   program can place a bare target byte at an instruction
   boundary today. The format decision below therefore lands on
   option 3, narrowed: a `db <hex>` line form in gpl-asm's
   encoder (the one feature the modder surface needs), after
   which recipes are plain `.asm` files and `fuzz <opcode>`
   becomes a thin driver.


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
