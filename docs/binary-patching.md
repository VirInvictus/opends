# Binary Patching

Some bugs do not live in GPL bytecode — they live in `DSUN.EXE`.
Combat AI loops, sprite culling, save/exit, sound-related bugs,
inventory removal of charged weapons. For those, we patch the
executable directly.

This is well-trodden territory (the entire ROM-hacking and
DOS-game patching community has been doing this for thirty
years). The risk is bounded; the practice is mature.

## 1. The binaries

### DS1 `DSUN.EXE`

- 611 KB
- DOS executable (likely DOS/4GW or similar; needs confirmation
  via `r2 -A`)
- `extracted/ds1/DSUN.EXE`

### DS2 `DSUN.EXE`

- 634 KB
- Same engine generation, larger codebase
- `extracted/ds2/DSUN.EXE`

Hashes (to be added once `tools/verify-install.py` lands):

- DS1 GOG 1.10 `DSUN.EXE` SHA256: `<TBD>`
- DS2 GOG 1.10 `DSUN.EXE` SHA256: `<TBD>`

The patch manifest will refuse to apply if the source hash
doesn't match the canonical 1.10 GOG build.

## 2. Tooling

| Tool                      | Role                                        |
|---------------------------|---------------------------------------------|
| `radare2` (`r2`) / `r2pm` | Primary disassembler, scriptable           |
| `ghidra`                  | Heavier static analysis when r2 stalls     |
| `dosbox-staging --debug`  | Live debugging in the original engine      |
| `python3 + bsdiff4`       | Generate / apply binary diffs              |
| `keystone` (Python)       | Assemble x86 instructions into bytes       |
| `xxd`, `bvi`, `hexedit`   | Manual hex inspection                      |

All on Fedora via `sudo dnf install radare2 hexedit ghidra`
(or pip for the Python ones). DOSBox-Staging via Flatpak:
`flatpak install flathub io.github.dosbox-staging`.

## 3. Process for one binary fix

### 3.1. Identify the bug surface

GPL fixes are tried first. If the bug behaves the same regardless
of which GPL script is at the wheel — for example, a graphics
glitch, an inventory state corruption, a crash without a
discernible quest trigger — it's likely engine-side.

### 3.2. Find the function

In `r2`:

```
r2 -A extracted/ds2/DSUN.EXE
afll               # list functions
fs strings; fs *   # list strings
/r <symptom-string>
```

Symptom strings ("Saving...", "Combat", error messages, names of
items involved in the bug) are the fastest entry points. The
inventory-removal bug, for instance, is likely near a string
like "depleted" or near the inventory-render path.

The DSO v1.0 client's debug symbols (per
[`upstream-projects.md`](upstream-projects.md)) list function
names from the WotR codebase. Cross-reference DSO
`function_<x>_<y>` symbols against r2-discovered functions in
WotR's `DSUN.EXE`.

### 3.3. Diagnose

Use r2's visual mode (`V`) and graph view (`VV`) to read the
function. Set a breakpoint in dosbox-staging's debugger
(`dosbox-staging -debug`), trigger the bug, watch state.

Two patterns are common:

- **One-byte fix**: a JE → JNE (74→75) or vice versa. A wrong
  branch, easy to flip.
- **NOP-out fix**: a faulty call gets replaced with `90 90 90...`,
  removing it.

Anything more complex (insert new code, call a new function)
requires a code cave — find an unused area in the binary, write
the new logic there, redirect a JMP. Standard fare for ROM
hackers.

### 3.4. Author the patch

Smallest possible byte change. Format:

```toml
# fixes/binary/042-combat-ai-loop.toml
id = "fix.ds2.combat-ai-loop"
target_file = "DSUN.EXE"
target_sha256 = "<canonical>"
description = "Combat AI no longer infinite-loops on Umber Hulk turn"

[[patch]]
offset = 0x0001abcd
expect = "74 0a"        # JE +0x0a
replace = "75 0a"       # JNE +0x0a
```

The applier:

1. Opens the file.
2. Seeks to `offset`.
3. Reads len(`expect`) bytes; if they don't match, refuses.
4. Writes `replace` bytes.

`expect` is a fingerprint, not just a comment. It guarantees we
don't apply a fix to a binary we don't recognize.

### 3.5. Distribute

Two options:

- **Hex-pair format** (recommended for v1): the TOML format above.
  Human-readable, easy to review in a PR, easy to apply.
- **`bsdiff`** for larger fixes (anything over a few hundred
  bytes). Smaller distribution; less reviewable.

We default to the hex-pair format; bsdiff only for code-cave
fixes.

### 3.6. Verify

Three checks:

1. **Hash of the patched binary** matches the post-patch hash
   recorded in the manifest.
2. **Disassembly** of the patched binary in r2 reads sensibly
   (no garbled instructions).
3. **In-game**: the bug repro fires the bug on unpatched, does
   not fire on patched.

## 4. DOS executable specifics

DOS-era executables have a few wrinkles modern tools handle but
worth being aware of:

- **MZ header**: standard DOS PE-style preamble. r2 handles it.
- **Protected-mode extender stub**: DOS/4GW or PMODE/W or HMI
  prepends a 32-bit DOS-extender stub. The actual code lives
  past it. r2's auto-analysis usually finds the entry point.
- **Segmented memory model**: 16-bit code segments may have
  far calls (`9A`-prefixed). Modern tools handle this; just be
  aware when reading addresses.
- **Self-modifying code**: rare in this era for SSI titles, but
  possible. If r2's analysis looks wrong, check if a `MOV [seg:off], imm`
  is rewriting the code we're reading.

## 5. Risks

- **Wrong-version binary**. A patch built against DS2 1.10 will
  not apply cleanly to DS2 1.0 or 1.02. The manifest's source
  hash check is the line of defense.
- **Compounding patches**. Two fixes that touch nearby bytes can
  conflict. The applier checks each `expect` independently — if
  patch A modified bytes patch B expected, patch B refuses.
- **Anti-debug**. None known in DSUN.EXE; if any surfaces, we
  document and route around it.
- **WotC IP**. Binary patches are derivative works. Each ships
  only the *byte deltas*, never the full executable. The
  player provides their own legitimate copy.

## 6. Worked example (placeholder)

A worked example will go here once the first DS2 binary fix
ships. Until then, see
[`patch-workflow.md`](patch-workflow.md) for the end-to-end
authoring process.
