# Binary Patching

Some bugs do not live in GPL bytecode: they live in `DSUN.EXE`.
Combat AI loops, sprite culling, save/exit, sound-related bugs,
inventory removal of charged weapons. For those, we patch the
executable directly.

This is well-trodden territory (the entire ROM-hacking and
DOS-game patching community has been doing this for thirty
years). The risk is bounded; the practice is mature.

## 1. The binaries

The binary layout, format disproof (no DOS/4GW; Borland/TLINK
VROOM overlaid 16-bit real mode), and hash-verification details
are the canonical domain of [`dsun-exe-re.md`](dsun-exe-re.md) §1.
Both games' `DSUN.EXE` hashes are pinned in
[`source-hashes/`](source-hashes/) and enforced by the patch
manifest.

## 2. Tooling

| Tool                      | Role                                        |
|---------------------------|---------------------------------------------|
| `radare2` (`r2`) / `r2pm` | Primary disassembler, scriptable           |
| `ghidra`                  | Heavier static analysis when r2 stalls     |
| `dosbox-staging --debug`  | Live debugging in the original engine      |
| `python3 + bsdiff4`       | Generate / apply binary diffs              |
| `keystone` (Python)       | Assemble x86 instructions into bytes       |
| `xxd`, `bvi`, `hexedit`   | Manual hex inspection                      |

Most on Fedora via `sudo dnf install radare2 hexedit` (or pip /
`uv tool` for the Python ones). DOSBox-Staging via Flatpak:
`flatpak install flathub io.github.dosbox-staging`.

⚠ **`ghidra` is NOT in the Fedora repos** (verified against F44:
`dnf list --available ghidra` finds nothing). This line used to
say `dnf install radare2 hexedit ghidra`, which silently fails the
whole transaction. Ghidra is a manual install, and it needs
**JDK 21** while Fedora 44 ships only 25 and 26. The working setup
on this machine, plus the three import traps specific to a
Borland-overlaid real-mode target, is documented in
[`dsun-exe-re.md`](dsun-exe-re.md) §7 and summarised in the repo
`CLAUDE.md` under "Host RE tooling".

## 3. Process for one binary fix

### 3.1. Identify the bug surface

GPL fixes are tried first. If the bug behaves the same regardless
of which GPL script is at the wheel: for example, a graphics
glitch, an inventory state corruption, a crash without a
discernible quest trigger: it's likely engine-side.

### 3.2. Find the function

In `r2`:

```
r2 -A .games/ds2/DSUN.EXE
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
requires a code cave: find an unused area in the binary, write
the new logic there, redirect a JMP. Standard fare for ROM
hackers.

### 3.4. Author the patch

The patch artifact format is specified once, in
[`fix-format.md`](fix-format.md): a darkfix fix script
(`fixes/NNN-<short-id>.py`) whose `EDITS` carry
`{"offset", "expect", "replace"}`: the fingerprint-gated,
in-place-only byte edit this section used to sketch as a TOML
applier that was never built. Author EXE edits against
`ndisasm -b 16` output and `ovr-map`'s addressing; author GPL
edits with `gpl-asm --patch` and paste the resolved offsets into
the fix script.

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

The format disproof (no DOS/4GW; Borland/TLINK VROOM overlaid
16-bit real mode) and the full evidence chain are in
[`dsun-exe-re.md`](dsun-exe-re.md) §1. Practical consequence for
patching: all code is 16-bit; `ndisasm -b 16` or `pwn disasm
arch='i386', bits=16` is mandatory: a 32-bit decode produces
convincing garbage without erroring.

## 5. Risks

- **Wrong-version binary**. A patch built against DS2 1.10 will
  not apply cleanly to DS2 1.0 or 1.02. The manifest's source
  hash check is the line of defense.
- **Compounding patches**. Two fixes that touch nearby bytes can
  conflict. The applier checks each `expect` independently: if
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
