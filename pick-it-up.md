# Pick It Up — gpl-disasm v0.2.0

A handoff primer for a fresh session to resume work where the
previous session left off. **Read this first**, then run the
pre-flight, then implement. Scope is *locked* — don't
re-litigate; the decisions in this file were made deliberately
with research backing.

This file is transient. Delete or rewrite it once v0.2.0 ships.

---

## TL;DR

- **Next deliverable**: `tools/gpl-disasm/` v0.2.0 — port libgff's
  `gpl_read_number` expression decoder so each GPL/MAS
  instruction's parameter bytes are consumed correctly and the
  disassembler emits one row per *instruction* rather than one
  per byte.
- **Scope is Partial v0.2.0** (locked): 14-bit immediates,
  GPL_IMMED_* literals (including IMMED_STRING via the 7-bit
  decoder already in `dialog-extract`), simple variable refs,
  operator chains, parens. **Defer GPL_RETVAL and
  GPL_COMPLEX_VAL to v0.2.1.**
- **Honest estimate**: ~5–7 focused hours, ~700 LOC of Rust + tests.
  Multi-commit ok per the per-feature commit pattern already
  established in this repo.
- **Working tree should be clean** when you start. `git log
  --oneline -5` should show `ca95200 CREDITS.md` at top. Push
  before you start so origin is in sync.

---

## Current state (as of last commit `ca95200`)

| Tool | Version | Language | Status |
|------|---------|----------|--------|
| `tools/verify-install/` | 0.1.0 | Python (stdlib) | Shipped |
| `tools/gff-edit/` | 0.4.0 | Rust | Shipped — read/write, bulk extract, text codec, JSON, FOURCC catalogue |
| `tools/gpl-disasm/` | 0.1.0 | Rust | Shipped — byte-annotation pass (every byte → one row tagged with libgff opcode name) |
| `tools/save-inspect/` | 0.1.0 | Python (stdlib) | Shipped — CHARSAVE.GFF → JSON |
| `tools/dialog-extract/` | 0.1.0 | Python (stdlib) | Shipped — 36,369 NPC dialog strings extracted from DS1+DS2 GPLDATA |

Reference checkouts (gitignored):

- `.dsun_music/` — `JohnGlassmyer/dsun_music` (MIT, JVM/Maven)
- `.dsoageofheroes/` — all 7 repos from `github.com/dsoageofheroes`
  (libgff, libsoloscuro, soloscuro, soloscuro-archive,
  soloscuro-oldgo, soloscuro-orx, the-dark-lens). All MIT or
  presumed MIT.

Memory notes ([`~/.claude/projects/-home-bdkl--gitrepos-opends/memory/`](file:///home/bdkl/.claude/projects/-home-bdkl--gitrepos-opends/memory/)):

- `opends_project.md` — project framing, **Goal 1 (modding
  toolkit) > Goal 2 (darkfix patches)**
- `dsun_music_reference.md` — JVM checkout map
- `dsoageofheroes_reference.md` — dsoageofheroes checkouts map +
  critical findings
- `feedback_honest_scope.md` — surface realistic scope before
  diving in

---

## What v0.1.0 currently does (and its limitation)

`tools/gpl-disasm/src/lib.rs` `disassemble(bytes)` returns
`Vec<Annotation>` where `Annotation { offset, byte, mnemonic,
string_run }` is **one row per input byte**. We look up each
byte in `OPCODES` (the 129-entry table sourced from libgff's
`gpl_commands` at `parse.c` lines 1554–1684) and emit the
mnemonic name where known. Inline ASCII runs ≥4 bytes get an
inline string-run annotation.

**The limitation**: opcodes have variable-length *parameters*
(read via `gpl_get_parameters(gpl, N)` which calls
`gpl_read_number` N times, where each `gpl_read_number` is a
recursive expression decoder). v0.1.0 ignores parameter bytes;
every byte is treated as a potential opcode. So a parameter
byte that happens to equal `0x4F` is labelled `gpl print
string` by mistake; instruction boundaries are not aligned with
the real program flow.

v0.2.0 fixes this.

---

## Locked scope for v0.2.0

### What ships

1. **`gpl_read_number` ported faithfully** for the common cases
   (see Decode cases below). Returns `(Expression,
   bytes_consumed)`. Stops at non-operator next-byte (per the
   `do_next` loop in libgff `parse.c` lines 626–630).
2. **Helpers ported**: `gpl_read_simple_num_var` (variable
   reference, 1 or 2 bytes depending on `EXTENDED_VAR` flag from
   the caller; libgff `parse.c` 134–233), `gff_gpl_read_text`
   (inline string reader; reuse the 7-bit decoder from
   `tools/dialog-extract/dialog-extract.py` —
   `decode_compressed_string`).
3. **Per-opcode parameter count table**. The earlier session
   extracted this via awk over libgff `parse.c` handler
   bodies; see the "Reproduce the param-count extraction"
   section below. Bake into a `PARAM_COUNTS: [u8; 0x81]` const.
4. **New `Instruction` and `Expression` types** replacing
   `Annotation`. One `Instruction` spans `length_bytes` bytes
   in the input and carries `params: Vec<Expression>`.
5. **`disassemble()` refactored** to return `Vec<Instruction>`.
   Each instruction reads opcode → look up param count → read
   that many expressions via `gpl_read_number`.
6. **CLI updates**: one row per instruction (not per byte).
   Add `--json` flag for structured output (uses
   `serde::Serialize` on `Instruction` and `Expression`).
7. **Tests**: unit tests for each Expression case + corpus
   integration test (`tests/corpus_smoke.rs`) updated to
   verify all 600 GPL/MAS chunks across DS1+DS2 GPLDATA
   disassemble without panic and consume their full byte
   length.
8. **Docs**: `tools/gpl-disasm/README.md` roadmap ticks v0.2.0;
   `docs/gpl-opcodes.md` adds a param-count column;
   `docs/gpl-bytecode.md` v0.2 description marked shipped;
   `tools/README.md` version bump; `roadmap.md` Phase 3 boxes;
   `patchnotes.md` unreleased entry; VERSION → 0.2.0;
   `Cargo.toml` version → 0.2.0.

### What's deferred to v0.2.1

- **GPL_RETVAL** (`0x8C` = `GPL_RETVAL | 0x80`). Nested
  function call: reads one byte for the opcode and recursively
  dispatches it via `gpl_commands[cmd].func`. libgff scopes
  this to a "safe" subset of commands in `gpl_retval`
  (`parse.c` lines 1791–1826): 0x0f, 0x10, 0x1a, 0x1e, 0x1f,
  0x20, 0x22, 0x25, 0x2f, 0x33, 0x34, 0x38, 0x39, 0x3d, 0x41,
  0x49, 0x52, 0x59, 0x5a, 0x5c, 0x80. v0.2.0 emits
  `Expression::RetVal { opcode: byte, body: Box<Expression>}`
  with `body = Unknown(raw_bytes_up_to_next_op)` and resyncs
  on next operator byte. Best-effort.
- **GPL_COMPLEX_VAL** (`0x31` per `libgff/include/gpl/var.h`,
  `GPL_COMPLEX_LOW..HIGH = 0x30..0x3F`). Record-field access via
  `gpl_access_complex` + `gpl_read_complex` (`parse.c` 235–368).
  v0.2.0 emits `Expression::Complex { raw_bytes: Vec<u8> }` and
  bails on byte counting (consumer must know it's opaque).
- **0xb3 special case** (`parse.c` line 609 — "THIS OP APPEARS
  TO BE SETTING A PASSIVE'S flag value to something"). Treat
  as Complex.

If a chunk uses any of these, the rest of that chunk after the
deferred case may misalign. The disassembler keeps going (best
effort) but the row count for that chunk drops below the byte
count. Track this in the corpus smoke test as a percentage
("aligned" vs "best-effort") rather than a binary pass/fail.

---

## Decode cases for `gpl_read_number`

Read libgff `parse.c` lines 369–635 alongside this list. Each
case is keyed by the value of `cop` (the first byte). When
`cop < 0x80`, it's the 14-bit immediate path; when `cop >=
0x80`, it's the high-bit dispatch.

### 14-bit immediate (`cop < 0x80`)

```
cop = byte0
b   = byte1
cval = cop * 256 + b
bytes_consumed = 2
```

Emit `Expression::Immediate14(cval)`. Always followed by the
operator-loop check.

### High-bit dispatch (`cop >= 0x80`)

Strip the high bit: `tag = cop & 0x7F`. Match `tag` against
GPL_* constants from `libgff/include/gpl/var.h`:

| `tag` value | GPL_* constant | Action | Bytes |
|-------------|----------------|--------|-------|
| 0x00 | GPL_ACCM | error (accum here is a bug — match libgff and emit an `Expression::Error`) | 1 |
| 0x01..0x0E (variable types) | GPL_LSTRING / LNUM / LBYTE / LNAME / LBIGNUM / GSTRING / GNUM / GBYTE / GNAME / GBIGNUM / GFLAG / LFLAG | check `cop & EXTENDED_VAR` (where `EXTENDED_VAR = 0x40`); call `gpl_read_simple_num_var` (1 byte without EXTENDED_VAR, 2 bytes with) | 2–3 |
| 0x0B | GPL_IMMED_BIGNUM | read two words via `gpl_get_word`; assemble as `int32_t` (low word in low half). Emit `Expression::ImmediateBigNum(i32)` | 5 |
| 0x0C | GPL_RETVAL | **deferred** — emit `Expression::RetVal { opcode, ... }` and try to resync. v0.2.1. | 2+ |
| 0x0F | GPL_IMMED_BYTE | read one signed byte | 2 |
| 0x10 | GPL_IMMED_WORD | libgff errors "not implemented"; treat the same | n/a |
| 0x11 | GPL_IMMED_NAME | read half-word; cval = h * -1 | 3 |
| 0x12 | GPL_IMMED_STRING | call `read_text` (port the 7-bit decoder from `tools/dialog-extract/dialog-extract.py` `decode_compressed_string`). Emit `Expression::ImmediateString(String)` | variable |
| 0x30..0x3F | GPL_COMPLEX_* | **deferred** — emit `Expression::Complex { raw_bytes }`. v0.2.1. | opaque |
| 0x50..0x5F (operators, on the low-bit side, after `OPERATOR_OFFSET - 0x80`) | GPL_OP_* | DO NOT consume here; this is the operator-loop check. Set `do_next = true`. | 1 |
| 0x61 | GPL_HI_CLOSE_PAREN | decrement paren depth | 1 |
| 0x62 | GPL_HI_OPEN_PAREN | increment paren depth; set `do_next = true`; reset `cval = 0` | 1 |
| 0x33 | special "0xb3" case | **deferred** | opaque |
| anything else | unknown | log + bail | n/a |

### Operator loop

After each value, peek the next byte (do not consume). If the
next byte is in `OPERATOR_OFFSET..=OPERATOR_LAST` (`0xD0..=0xDF`
from `var.h`), consume it (emit
`Expression::BinaryOp(Op::Add/Minus/...)`) and continue the
outer loop reading the next value. Also continue while paren
depth > 0. Stop otherwise.

The operator-loop logic is at `parse.c` lines 626–630:
```c
if (!do_next) {
    do_next = (gpl_preview_byte16(gpl, &next_op) == EXIT_SUCCESS
               && next_op > OPERATOR_OFFSET
               && next_op <= OPERATOR_LAST);
}
```

---

## `gpl_read_simple_num_var` (variable references)

libgff `parse.c` lines 134–233. Each variable-typed expression
calls this after stripping the EXTENDED_VAR bit from the dispatch
byte. The function:

1. Reads one byte → `temps16 = b`.
2. If `EXTENDED_VAR` was set on the original `cop`, multiply
   `temps16 *= 0x100` and read another byte → `temps16 += b`.
   (So 1 byte for vid ≤ 255, 2 bytes for vid > 255.)
3. The variable type (`gpl_global_big_num`, set by the caller)
   dispatches: GFLAG / LFLAG / GNUM / LNUM / GBIGNUM / LBIGNUM
   / GNAME / GSTRING / LSTRING — each emits a different
   readable form. Port faithfully; emit
   `Expression::Variable { kind: VarKind, id: i16 }`.

The libgff source also has GNAME / GSTRING / LSTRING branches
that look special-cased (the GNAME branch checks
`temps16 >= 0x20 && temps16 < 0x2F` and rewrites the id by
subtracting 0x20). Match the libgff logic verbatim.

---

## Per-opcode parameter count (`PARAM_COUNTS`)

To populate the const table, run this against the local libgff
checkout:

```sh
awk '
/^static int gpl_[a-zA-Z_]+\(gpl_data_t/ {
    name = $0
    sub(/^static int /, "", name)
    sub(/\(.*$/, "", name)
    funcs[name] = 0
    current = name
}
/^int gpl_[a-zA-Z_]+\(gpl_data_t/ {
    name = $0
    sub(/^int /, "", name)
    sub(/\(.*$/, "", name)
    funcs[name] = 0
    current = name
}
/gpl_get_parameters\(gpl, [0-9]+\)/ && current != "" {
    n = $0
    sub(/.*gpl_get_parameters\(gpl, /, "", n)
    sub(/\).*/, "", n)
    funcs[current] = n
}
END { for (f in funcs) print funcs[f] "\t" f }
' .dsoageofheroes/libgff/src/gpl/parse.c | sort -k2
```

Hand-curate the result. Caveats:

- Some handlers (`gpl_load_accum`, `gpl_setrecord`, etc.) read
  parameters via `load_accum(gpl)` or direct `gpl_read_number`
  calls rather than `gpl_get_parameters`. Grep for those too.
- Handlers using `gpl_unknown` as their stub function have a
  param count of 0 from the grep, but the actual byte
  consumption is also 0 (since we don't decode), so 0 is
  correct.
- `gpl_get_parameters(gpl, amt)` where `amt` is a variable
  (e.g. `gpl_request`) — these read a count first then that
  many params. Handle as a special case in the dispatch table:
  `ParamSpec::CountThenParams` or similar.

Map opcode byte → param count via the `gpl_commands` table
(already in `OPCODES` as `&[&str]`).

---

## Recommended task order

Existing tasks #39–45 cover this:

1. **#39** Design `Instruction` and `Expression` types.
   Document with `#[serde(...)]` for `--json` from the start.
2. **#40** Port `gpl_read_number` (common cases; defer RETVAL
   and COMPLEX with placeholder variants).
3. **#41** Port helpers — `gpl_read_simple_num_var`,
   `gff_gpl_read_text` (reuse the Python implementation as a
   reference; same algorithm). `gpl_access_complex` and
   `gpl_read_complex` get stubs that consume opaque bytes (v0.2.1).
4. **#42** Refactor `disassemble()` to return
   `Vec<Instruction>`. Build the per-opcode param-count table
   and use it to drive parameter reads.
5. **#43** Add `--json` to the CLI.
6. **#44** Update unit tests; corpus smoke: track aligned vs
   best-effort percentage.
7. **#45** Docs + commit.

Commit between #42 and #44 if a working checkpoint is reached
(e.g., `disassemble()` works for chunks with no deferred cases,
tests pass on small fixtures). Brandon prefers per-feature
commits over giant ones.

---

## Constraints and preferences (from Brandon's CLAUDE.md and memory)

- **No em-dashes** in prose you write for him (READMEs, specs,
  commit messages, PR descriptions). Hyphens in compound
  modifiers (`single-writer`, `read-only`) are fine; en-dashes
  in ranges are fine. Recast sentences if you find yourself
  reaching for an em-dash.
- **Heavy planning**: for non-trivial work, write a plan and
  get sign-off before coding. This file IS the plan for v0.2.0;
  no further sign-off needed unless scope shifts.
- **Always show commit messages before committing** (not "just
  commit" unless he says so). He'll say "go" or sign off.
- **Don't push without explicit approval**. He says when.
- **Tests are not optional**. Match the project's test style;
  Rust integration tests live in `tools/<tool>/tests/`.
- **No third-party deps without asking**. v0.2.0 doesn't need
  any new deps; serde + serde_json are already in
  `workspace.dependencies`.
- **Attribution rule**: cite each ported piece of logic in the
  source file's comments (`// Ported from
  dsoageofheroes/libgff src/gpl/parse.c <function> (MIT)`)
  AND update `CREDITS.md` with the per-feature entry.
- **Honest scope**: if the implementation goes significantly
  over the ~700 LOC estimate or new unknowns emerge, surface
  it before committing more time.

---

## Pre-flight checklist

Before writing any v0.2.0 code:

1. `cd /home/bdkl/.gitrepos/opends` — make sure cwd is the repo
   root (the previous session had a cwd drift issue from a `cd`
   into `.dsoageofheroes`).
2. `git status` should show a clean working tree at commit
   `ca95200` (or its descendant if Brandon pushed something
   between sessions).
3. `git pull --ff-only` to make sure local is current.
4. `cargo test -p gpl-disasm --release` — confirms the v0.1.0
   baseline passes (6 unit + 1 corpus integration).
5. Re-read [`docs/gpl-bytecode.md`](docs/gpl-bytecode.md) §5
   for the per-version scope (v0.2 is parameter decoding).
6. Skim [`tools/gpl-disasm/src/lib.rs`](tools/gpl-disasm/src/lib.rs)
   to refresh the v0.1.0 API surface before refactoring.
7. Skim [`tools/dialog-extract/dialog-extract.py`](tools/dialog-extract/dialog-extract.py)
   `decode_compressed_string` — port this directly to Rust
   for the IMMED_STRING case.
8. Have `.dsoageofheroes/libgff/src/gpl/parse.c` open in another
   pane. Lines 369–635 (`gpl_read_number`), 134–233
   (`gpl_read_simple_num_var`), 1554–1684 (`gpl_commands`),
   1791–1826 (`gpl_retval`).
9. Have `.dsoageofheroes/libgff/include/gpl/var.h` open for
   the GPL_* constant values.

---

## Risks and known unknowns

- **`gpl_read_complex` is non-trivial** (`parse.c` 329–368).
  We stub it for v0.2.0 (`Expression::Complex { raw_bytes }`)
  but the stub still needs to know how many bytes to consume.
  Probable approach: emit the stub at the first byte (`0xB1`,
  i.e. `0x31 | 0x80`) and treat the remainder of the parameter
  as opaque until the next operator byte. This may misalign
  for chunks that have non-trivial complex access; track in
  corpus smoke.
- **The "0xb3 special case"** at `parse.c` line 609 has no
  GPL_* constant name and is described in a comment as
  "setting a passive's flag value to something". v0.2.0 treats
  it as Complex.
- **GPL_IMMED_WORD** is libgff-unimplemented. Either we never
  see it in the wild (likely), or we hit it and need to
  research. Track if encountered.
- **`gpl_get_parameters(gpl, amt)` with variable `amt`** (some
  handlers compute `amt` from a preceding parameter, e.g.
  `gpl_request` reads a count then that many params). Build a
  `ParamSpec` enum: `Fixed(u8)`, `CountThenParams`,
  `Custom(handler-specific)`. Match libgff's per-handler
  behavior.
- **Recursive depth** for GPL_RETVAL nested calls — defer to
  v0.2.1 entirely.

---

## What dialog-extract gains from v0.2.0

When v0.2.0 ships, `tools/dialog-extract/` upgrades from its
heuristic byte-scan to a true instruction-aware extractor:

- Replace `find_strings_in_chunk` with a `gpl-disasm --json`
  consumer.
- For each `gpl print string` instruction (opcode `0x4F`),
  inspect its parameters. The 2 params are typically
  `(string_source, formatting)`. String source can be
  `Expression::ImmediateString` (already decoded) or
  `Expression::Variable { kind: GSTRING/LSTRING, id }` (text-id
  reference to a TEXT chunk in a sibling GFF).
- Add a `--text-source <RESOURCE.GFF>` flag so dialog-extract
  can resolve text-id references against the game's TEXT
  chunks. This finally surfaces strings like "Garn" from
  RESOURCE.GFF that the v0.1 heuristic missed.

That upgrade is its own commit, after v0.2.0 ships. Not part
of v0.2.0's scope.

---

## Done-when

- `cargo test -p gpl-disasm --release` passes (unit + corpus).
- Corpus integration test reports >= 95% of chunks "aligned"
  (no deferred cases hit) and <= 5% "best-effort" (RETVAL or
  COMPLEX encountered).
- `gpl-disasm <file> --kind 'GPL ' --id 1` on DS1 GPLDATA shows
  proper instructions with parameters (e.g. `gpl print string
  IMMED_STRING("Free! Finally free!..."), <expr>` instead of
  a byte-per-row dump).
- All docs updated (README, opcodes.md, bytecode.md, roadmap,
  patchnotes).
- VERSION + Cargo.toml bumped to 0.2.0 in sync.
- CREDITS.md updated for any newly-ported logic (the expression
  decoder, the helpers).
- Commit message lays out the scope + corpus stats.
- Pushed (with Brandon's approval).

---

## When in doubt

- Run the v0.1.0 disassembler on a small chunk first; compare
  byte stream to libgff's `gpl_read_number` traces. Print
  statements in libgff source show what each case emits — use
  those to validate your Rust port.
- Talk through architecture decisions with Brandon (use
  `AskUserQuestion`) before refactoring shared types.
- If a fresh issue emerges (a case in `gpl_read_number` that
  isn't in this file), update this file with the new finding
  and the decision, then continue.
