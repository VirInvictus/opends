# Next-versions planning

Sprint plan for the five "next mature version" ships across
the toolkit. The bar is per-Brandon: every tool fully shelled
out before any darkfix patch work. See [memory
`feedback-tools-before-patches`](../.. ) for the durable rule.

The five plans below are sequenced in roughly increasing
risk / cost order:

1. `gpl-asm v0.6.0` (authoring conveniences; self-contained)
2. `dialog-extract v0.5.0` (LSTR tail; inter-chunk flow)
3. `repro v0.3.0` (`--play` session continuity + input + video)
4. `opcode-fuzz v0.2.0` (run-and-observe; depends on repro
   v0.3.0)
5. `region-render v0.6.0` (`--animate`; third try, time-boxed)

Each plan section includes scope, the implementation steps,
the test plan, and the open risks. Background research from
the public Dark Sun reverse-engineering corpus (libgff,
soloscuro-archive, dsun_music, dso-online) anchors the
findings.

## Background research

### `.dsoageofheroes/` subrepos

Seven checkouts, ordered roughly by impl maturity:

- `libgff`: the public reference for the GFF container, the
  RDFF sub-block schemas, and the GPL bytecode interpreter
  surface. `include/gff/var.h` declares the GPL VM's data
  vocabulary (operator opcodes `0xD0..0xDF`, type tags
  `0x00..0x12`, complex-access dispatch bytes); `include/gff/gfftypes.h`
  catalogues every FOURCC; `src/gpl/state.c` declares the
  static VM-state arrays we'll need to observe in
  `opcode-fuzz v0.2.0`. The implementation is **partial**;
  many opcode handlers in `src/gpl/parse.c` are
  `printf`-only stubs (see `GPL_LSTRING` at parse.c:217-226).
- `libsoloscuro`: newer C library factored out of
  soloscuro-archive. Reorganised; smaller. Same
  vocabulary but most of the engine-side logic is still in
  soloscuro-archive.
- `soloscuro-archive`: the ~567-commit engine reimpl attempt
  that stalled in 2023. Custom Lua-based save format
  (`src/save-load.c`); not GFF, so not directly applicable
  to `save-inspect` / `opcode-fuzz`. The GPL VM impl lives
  here but borrows libgff's parser. Region rendering exists
  but has **no palette-cycle handling** (verified by grep
  on `cycle`, `animat`, `palette`).
- `soloscuro`: Zig rewrite skeleton; minimal code.
- `soloscuro-oldgo` / `soloscuro-orx`: older Go / Orx
  experiments; not load-bearing.
- `the-dark-lens`: DSO protocol notes only; one Markdown file
  + an `xmi-tracks.txt`. Useful as background for DSO
  symbols but no code.

**Headline findings**:

1. **GPL VM variable layout** (libgff `include/gff/var.h` +
   `src/gpl/state.c`):
   - `gpl_global_flags[MAXGFLAGS = 800]` (1 bit each, packed
     to 101 bytes).
   - `gpl_global_nums[MAXGNUMS = 400]` (`int16_t`, 800 bytes).
   - `gpl_global_bnums[MAXGBIGNUMS = 40]` (`int32_t`, 160
     bytes).
   - `gpl_global_strs[MAXGSTRS = 32][1024]` (32 × 1024 = 32 KB).
   - `gpl_gnames[MAXGNAMES = 13]` (`int16_t`, 26 bytes).
   - Locals: `MAXLFLAGS = 64`, `MAXLNUMS = 32`,
     `MAXLBIGNUMS = 40`. Locals are per-chunk and don't
     persist.
   - Search stack: `MAX_SEARCH_STACK = 32`.

   These are the arrays a single-opcode test must read from /
   write to for `opcode-fuzz` to observe behaviour.

2. **SAVE-chunk family in GFFs** (libgff `include/gff/gfftypes.h`
   lines 93-106):
   - `CHAR` (`'CHAR'`) = saved character slot.
   - `SAVE` (`'SAVE'`) = save entries (the per-region world-
     state chunks save-inspect saw in DARKRUN.GFF).
   - `STXT` (`'STXT'`) = save-file display name.
   - libgff also defines `POS `, `ROBJ`, `TRIG`, `GDAT`,
     `PLAY`, `RENT` but flags them "(not part of original
     engine.)"; those are soloscuro-archive's additions.
     The original engine ships `SAVE` / `STXT` / `ETME` /
     `ETAB` / `CHAR` only, matching what `save-inspect` reads.

3. **LSTRING (local string slot) semantics** are documented
   but **not implemented** in libgff (parse.c:217-226 is a
   `printf` stub with commented-out array access). That
   makes libgff a non-source for the LSTR caller-population
   problem; our own `dialog-extract` already exceeds the
   public state of the art.

4. **Palette cycling is publicly un-RE'd**. Both libgff and
   soloscuro-archive have zero code for cycle / animated
   palettes. `dsun_music`'s region-tool carries the canonical
   `TODO: properly render animated colors` at line 180 of
   `RegionTool.java`. Our DSUN.EXE work in
   `docs/dsun-exe-re.md` §4 is the public state.

### `.dsun_music/` subrepo (JohnGlassmyer)

Four tools: `gff-tool`, `image-tool`, `region-tool`,
`xmi-tool`, plus a `common` library. The `common/GffFile.java`
is the canonical public GFF writer (the policy `gff-edit` and
the OpenDS toolkit follow: in-place if it fits, append
otherwise; segmented-chunk secondary-table format).
`region-tool` is the public closest-prior-art region renderer
that we informed `region-render` from; the only cycle-related
content is the line-180 TODO.

### `.dso-online/` subrepo (greg-kennedy)

Symbol catalogue (`tools/symbols.txt`) is the highest-value
reference: 3,530 names from the DSO v1.0 client, sharing the
WotR codebase. Headline cohorts for the upcoming versions:

**GPL VM state pointers** (likely `int32_t*` each, allocated
elsewhere):

| DSO offset | Symbol           | Role                                 |
|------------|------------------|--------------------------------------|
| `0x00108210` | `gplData`        | bytecode pointer for current chunk |
| `0x00108218` | `gGnumvar`       | pointer to GNUMs array             |
| `0x00108220` | `gGbignumvar`    | pointer to GBIGNUMs array          |
| `0x00108224` | `gLbignumvar`    | pointer to LBIGNUMs array          |
| `0x00108228` | `gGflagvar`      | pointer to GFLAGs array            |
| `0x00108234` | `gBignumptr`     | scratch big-num pointer            |
| `0x0010823C` | `gGstringvar`    | pointer to GSTRINGs array          |
| `0x001BFD94` | `gNameBuffer`    | GNAMEs buffer                      |
| `0x001D0648` | `gplIp`          | GPL instruction pointer            |

DSO offsets are not DSUN.EXE offsets; the call-graph-shape
matching pattern from `dsun-exe-re.md` §3 / §4 is the way to
find DS2 counterparts. The 8-byte stride between successive
pointer symbols (`gGnumvar` at `+0x00`, `gGbignumvar` at
`+0x08`, `gLbignumvar` at `+0x0c`) is the distinguishing
shape: a contiguous run of `int32_t*` slots in the data
segment.

**Save / load**:

- `OpenCharsave 0x0002E791 f`, `CloseCharsave 0x0002E7CF f`.
- `SaveCharRec 0x0002C45F f` (the per-character writer; the
  function whose disassembly would pin down DS2 character
  schema's byte semantics).
- `GameModeSave 0x0001E640 f`, `SaveGameToDisk 0x0002F1C5 f`.
- `GameLoadRegion 0x00024131 f` (region loader; touches the
  SAVE-chunk read path).
- `dosave 0x0011075A l`, `dothesave 0x000C0A64 f`,
  `usuallysave 0x000C0A7E f` (state guards around save).

**Input / timer** (relevant for `repro v0.3.0` + `opcode-fuzz`):

- `messageTimer 0x001BBA1C`, `gTheDJTimer 0x001BE450`,
  `hFrameTimer 0x0010B3E4`: timer handles; the engine's tick
  cadence.
- `keytranslate 0x00041061 f`: keyboard input translator.
  Hooked into the BIOS keyboard interrupt; if we can find its
  input buffer, that's where ydotool-driven keystrokes land
  in DOSBox.
- `Inputi16 0x000336BC f`, `InputBignum`, `InputString`: GPL-
  side input request functions.

**MEL audio** (already known; included for completeness):

- `melReset`, `_melDisplayFliFrames` etc. confirm the engine
  binds against Miles Audio Library; the v0.1.0 `repro` work
  that captured the `sound_ds`-generated `SOUND.CFG` is the
  workaround.

---

## `gpl-asm` v0.6.0: authoring conveniences

The remaining out-of-scope items from v0.5.0:

1. **Macros** for parameterised expressions / blocks.
2. **Forward references** beyond `label:` (named symbolic
   constants for the `name_idx` / item id / flag id token
   slots the parser currently demands as numeric literals).
3. **`gpl_search` raw_tail composition**: today the modder
   has to compose the hex by hand or paraphrase via JSON.

### Scope (in)

- **`%define <name> <expression>`** preprocessor directive.
  Single-line, no parameters; substitutes the named token
  with the expression body in subsequent lines. Lives in the
  parser's first pass alongside label collection.
- **Constant `.const <name> = <value>` declarations** that
  bind to integer literals; usable wherever the existing
  parser accepts an integer (param slots, immediate values,
  label-relative offsets). Goes in the same pass.
- **`gpl_search` raw_tail helper macro**: `%search-tail
  <byte> ...` directive emits `; raw_tail=HEX` trailer for
  the following `gpl_search` instruction. So:

  ```
  %search-tail 01 00 02 ff
  0040  33  gpl_search       NAME, ACTIVE
  ```

  becomes the same chunk the JSON path produces, no manual
  hex composition.

### Scope (out)

- **Parameterised macros** (`%define name(arg1, arg2) ...`).
  Adds tokenisation complexity for marginal v0.6.0 value;
  queued for v0.7.0+ if anyone actually wants it.
- **Macro precedence over labels**. Definitions live in their
  own namespace; if a `%define foo 42` collides with a
  `foo:` label, the parser errors at definition time. No
  shadowing.
- **`@include` directives** (multi-file authoring). Single-
  file source files only.

### Implementation steps

1. Extend `tools/gpl-asm/src/parse.rs` with a pre-scan pass
   that consumes `%define` / `.const` / `%search-tail` lines.
   These look unlike instruction lines (no leading 4-hex
   offset), so they're already in the "skip" branch of the
   main loop; just need to recognise them.
2. Build a `HashMap<String, String>` of name -> replacement
   text. The replacement is integer-typed at use time.
3. Add a token-substitution pass before `parse_param_tokens`:
   any identifier whose first character is alphanumeric and
   whose name matches a defined constant gets replaced by
   the literal text. Operator words (`and`, `or`) and
   variable shorts (`GNUM`, `LSTR`, ...) keep their existing
   precedence.
4. The `%search-tail` directive sets a one-shot trailer state
   that the next instruction-line parser consumes as if it
   came in via the `; raw_tail=HEX` trailer path. Implemented
   in the same pass that handles the trailer reading today.
5. Add `gpl_asm::parse::PreprocessedSource` (or similar) that
   captures the post-preprocessor text with line-number
   mappings so caret error messages still point at the
   original line.
6. Tests:
   - `parser_handles_define`: a chunk that uses a `%define`
     expands to the same bytes as the literal version.
   - `parser_rejects_duplicate_define`: shadowing is an
     error.
   - `parser_rejects_define_colliding_with_label`: both
     define-first-then-label and label-first-then-define
     emit `ParseError::DuplicateName`.
   - `search_tail_directive_round_trips`: a chunk with the
     directive round-trips byte-identical against a chunk
     authored via the JSON path.

### Test plan

- Unit tests in `tools/gpl-asm/src/parse.rs`'s existing
  `#[cfg(test)] mod tests` block.
- Corpus round-trip stays at 600/600 (the preprocessor is
  no-op on `gpl-disasm`-produced output).
- Add at least one *new* fixture under
  `tools/gpl-asm/tests/` that exercises macros + search-tail
  directives end-to-end (parse text -> encode -> assert
  byte-equal against the JSON-encoded version of the same
  semantic chunk).

### Risks

- Caret-style error messages need source-line awareness post-
  preprocessing. Solution: keep an explicit
  `OriginalLineNum -> ProcessedLineNum` map; route errors
  back through it. Existing `format_with_caret` infrastructure
  needs minor extension.
- `%search-tail` and the existing trailer-comment path must
  not double-fire on the same instruction. Document the
  precedence (directive wins; trailer-comment is the JSON
  fallback) and add a test.

### Effort estimate

One focused session. ~200 lines of parser changes + 50 lines
of tests. No game files needed.

---

## `dialog-extract` v0.5.0: LSTR tail

v0.4.0 resolves 96.4% of LSTR refs. The 3.6% tail (DS1 + DS2
combined ~32 unresolved reads) is **caller-populated slots**:
LSTR slot N is read in some chunk X, but X was reached via a
caller path where X's direct caller didn't set N; N was set
further up the call chain.

### Scope (in)

- **Multi-hop caller-LSTR propagation**. Today
  `_expand_cross_chunk_call` walks one level: caller's
  current LSTR state is passed to callee. v0.5.0 walks the
  full caller chain (depth-limited; same `MAX_DEPTH` as the
  existing CFG walker) and propagates the LSTR state along
  every prefix of the entry path.
- **`possible_writers` set** as a fallback resolution. When
  exact path-aware propagation doesn't pin a single value,
  emit the set of all chunks + offsets that could
  legitimately write to that slot, ordered by static-CFG
  proximity. The reader sees "LSTR[3] = one of A:0x42,
  B:0x88" instead of "LSTR[3] = ???".
- **Stats line in stderr**: print "v0.4 baseline: X
  unresolved / v0.5: Y unresolved (Z resolved exactly, W
  resolved via possible_writers)" so improvement is visible
  from corpus runs.

### Scope (out)

- **Dynamic LSTR resolution** (LSTR slot written from another
  LSTR slot whose value isn't statically determinable).
  These should be the residual cases after the multi-hop +
  possible_writers improvements. Queued for v0.6.0+ with no
  obvious path.
- **Inter-chunk slot expansion through `gpl_search`** (the
  search opcode can write to LSTR slots indirectly).
  Marginal; queued.

### Implementation steps

1. Build a global **LSTR-writer index** at startup:
   `Dict[LSTRSlot, List[(chunk_kind, chunk_id, offset)]]`.
   Scan every chunk's instructions for opcode `0x0A`
   (`gpl_string_copy`) with `param[0]` = LSTR variable.
2. Build a global **LSTR-reader index**: for every unresolved
   LSTR read currently surfaced by v0.4, record the chunk +
   the slot.
3. For each unresolved read in a chunk X:
   - Find all chunks that call X (via the global CFG).
   - For each caller, walk back from the call site looking
     for LSTR writes to the target slot.
   - If found: emit as `possible_writer` reference; mark
     resolution path as "via caller chain".
   - If multiple chunks could feed the slot: emit the set,
     ordered by caller-graph distance.
4. Update the `dialog_tree` JSON schema: unresolved LSTR
   refs gain a `possible_writers` array (empty when truly
   unresolvable).
5. Update README + version bump.

### Test plan

- Corpus delta: re-run the v0.4 unresolved-count check;
  assert the count drops. Target: <1% unresolved after
  exact resolution (i.e. >99% of reads pin to a single
  writer); residual <1% surfaces as `possible_writers`.
- Add an integration test that constructs a known
  caller -> callee -> reader chain with a unique LSTR
  writer in the caller; v0.5 should resolve exactly.
- Add a test that constructs an ambiguous resolution (two
  callers, different writers); v0.5 should emit both via
  `possible_writers`.

### Risks

- **CFG depth blow-up**. Walking back through every caller
  for every unresolved read is potentially `O(callers ^
  depth)`. The existing `cross_chunk_visited` cycle-guard
  applies; same `MAX_DEPTH` cap. Measure on the corpus
  before shipping.
- **False positives in possible_writers**. The static CFG
  doesn't know which callers *actually* run in any given
  game state. We may emit writer candidates that never
  fire. Document as expected; the set is "all
  statically-reachable writers", not "the writer that fires
  at runtime."

### Effort estimate

One to two sessions. The CFG already exists (gpl-disasm
v0.4.1 `--global-cfg`), so the work is mostly Python over
existing data structures. ~150-200 lines.

---

## `repro` v0.3.0: `--play` session continuity + input + video

Brandon's explicit `--play` requirement: **the game should
actually play across sessions**, with save files findable
between invocations. v0.2.1's `--play` creates a fresh
tempfile dir each invocation; in-game saves don't carry over.

Plus the v0.2.0 deferred items: input automation, video
capture.

### Scope (in)

#### 1. `--play` session continuity (priority 1)

- **`--session <name>` flag** on `--play`. Replaces the
  default `tempfile.mkdtemp(dir="/tmp")` with a stable path
  at `${XDG_STATE_HOME:-~/.local/state}/opends-repro/play-<game>-<session>/`.
  Persistent across invocations.
- **Default session naming**: if `--session` is omitted on
  `--play`, default to `<bug_id>` (so
  `repro.py ds1-smoke --play` always uses
  `play-ds1-ds1-smoke/`).
- **Save resumption flow**: each `--play --session foo` run
  starts by inheriting the previous session's overlay (the
  `c-overlay/` from the same path is reused, not recreated).
  In-game saves automatically persist for the next
  invocation.
- **`--list-sessions`** to enumerate active sessions per
  game and show last-modified time + scratch path.
- **`--reset-session <name>`** to nuke a session's scratch
  before next launch.

#### 2. Input automation (priority 2)

- **`ydotool` integration**. Requires `dnf install ydotool`
  (Brandon to approve; ydotool is in Fedora's repos). The
  daemon (`ydotoold`) needs uinput access; one-time setup
  documented in repro README.
- **Per-fixture `[trigger].keystrokes`**: a list of
  timed keystroke records the harness feeds ydotool after
  the game has booted.

  ```toml
  [trigger]
  commands = ["DSUN.EXE > d:\\dsun.log"]

  [[trigger.keystrokes]]
  at_seconds = 8
  send = "Return"

  [[trigger.keystrokes]]
  at_seconds = 12
  send = "ctrl+s"
  ```

- **Graceful degradation**: when ydotool isn't installed,
  the harness emits a warning and skips keystrokes (rather
  than failing). Fixtures that *require* keystrokes are
  marked `[trigger].requires_input = true`; running them
  without ydotool aborts with a clear error.

#### 3. Video capture (priority 3)

- **GNOME Wayland-compatible recorder selection**. Three
  candidates; pick the one Brandon already has or is willing
  to install:
  - `gnome-screen-recorder` (D-Bus interface to gnome-shell):
    no extra dep, GNOME-only.
  - `ffmpeg -f pipewire` via xdg-desktop-portal: cross-DE.
  - `obs-cli` via OBS Studio's WebSocket interface: heavier.
- **`[expected].record_video = true|false`** in bug.toml.
  When true: the harness spawns the selected recorder
  against the DOSBox window region for the budget duration;
  output lands at `<session>/repro.webm`.
- **Auto-window detection** via Wayland's `wmctrl` analogue
  or DOSBox's WM_CLASS.

### Scope (out)

- **Differential capture** (run-with-patch vs without). Still
  v0.4.0+.
- **Per-fixture `[trigger].mouse_actions`**. Just keystrokes
  for v0.3.0; mouse input automation is fiddlier on
  Wayland and we'll get further by sticking to keyboard.

### Implementation steps (priority 1: session continuity)

1. Add `--session <name>` argparse to repro.py; default to
   `bug_id` when `--play` is set.
2. Compute `session_root = Path(os.environ.get("XDG_STATE_HOME",
   Path.home() / ".local/state")) / "opends-repro" / f"play-{game}-{session}"`.
3. When `--play`:
   - If `session_root` exists, reuse it as the scratch dir.
   - If not, create it (`mkdir -p`).
   - Stage factory saves *only if* `session_root / c-overlay`
     is empty (first run); otherwise honour the persisted
     state.
4. Print session path at start of run AND at end ("session
   retained at ...").
5. `--list-sessions`: walk the per-game session dirs, show
   last-modified time of `c-overlay/DARKRUN.GFF`.
6. `--reset-session <name>`: `shutil.rmtree(session_root)`
   after a y/n prompt.

### Implementation steps (priority 2: input)

1. Add ydotool detection at startup (`shutil.which("ydotool")`).
2. Add `[trigger.keystrokes]` parsing to `BugFixture.load`.
3. After spawning DOSBox, spawn a Python thread that sleeps
   to each `at_seconds` and calls `ydotool key <send>`.
4. The DOSBox window needs focus for keystrokes to land;
   document this constraint in README.
5. `--no-input` flag to disable keystroke automation for one
   run.

### Implementation steps (priority 3: video)

1. Detect available recorder via `shutil.which` calls.
2. Add `[expected].record_video` to schema.
3. On record_video=true: spawn recorder process before
   DOSBox launch; signal it to start after a short delay
   (so DOSBox window exists); kill on DOSBox exit.
4. Output path is `<session>/repro.webm`. Emitted in run
   header.

### Test plan

- `--play` smoke: run `ds1-smoke --play`, save in-game, exit;
  re-run `ds1-smoke --play`, confirm last save is loadable.
- `--list-sessions` after two sessions: lists both,
  correct mtimes.
- `--reset-session` deletes the named session, doesn't
  touch others.
- Input automation: a smoke fixture that types "ESC" 5 s
  after boot to exit the SSI intro screen; the harness
  exits with the expected behaviour.
- Video: same smoke fixture, assert `repro.webm` exists and
  is non-empty after the run.

### Risks

- **Wayland window focus** for ydotool. The DOSBox window
  must be focused when keystrokes are sent. If the user
  alt-tabs away mid-run, input lands on the wrong window.
  Document; consider a future "lock-focus" mode.
- **ydotool daemon setup**. Requires uinput access (root or
  group `input`). One-time setup. README covers it.
- **Video file size**. A 30-second `webm` is small (~5 MB);
  a 5-minute play session is larger. Document; don't
  default-enable.

### Effort estimate

Priority 1 (session continuity): one session. Priority 2
(input): one to two sessions, contingent on ydotool approval.
Priority 3 (video): one session, contingent on recorder dep
approval. Ship priority 1 alone if (2) and (3) get gated;
that's still meaningful improvement.

---

## `opcode-fuzz` v0.2.0: the run-and-observe loop

v0.1.0 shipped the chunk-patchwork pipeline; v0.2.0 adds the
"run a patched chunk under DOSBox and observe the effect" half.
The Phase 5 "done when": discover at least one previously-
unknown opcode and add it to `docs/gpl-opcodes.md`.

### Dependencies

- `repro v0.3.0` (input automation; the test chunk needs to
  *run* to completion before we observe state, which means
  triggering whatever the chunk's caller expects).
- **GPL VM global-array addresses in DSUN.EXE**. The DSO
  symbols (`gGflagvar 0x00108228` etc.) give us the shape;
  the DS2 counterparts need pattern-search work.

### Scope (in)

- **`opcode-fuzz run <work-dir>` subcommand**. Takes a
  staged work-dir (from `extract`), packs the modified
  chunk into a patched GFF, stages it via a synthetic
  `repro` fixture, launches DOSBox via `repro.py` (with
  scripted keystrokes to navigate past the boot screen if
  needed), and captures the post-run `DARKRUN.GFF` /
  `c-overlay`.
- **Pre/post state diff**. Use `save-inspect` to dump
  CHARSAVE.GFF + DARKRUN.GFF before and after the run; emit
  a structured diff of every changed field. SAVE chunks in
  DARKRUN are the primary observable surface (per the v0.6
  save-inspect discovery that `DARKRUN.GFF = SAVE0N.SAV`).
- **Test-chunk recipe library** at `tools/opcode-fuzz/recipes/`.
  Each recipe is a GPL listing template:
  - **Prologue**: load known sentinel values into a known
    set of GFLAGs / GNUMs / GBIGNUMs. (`gpl_set_var` etc.)
  - **Test opcode**: the opcode under investigation, with
    parameters drawn from the recipe.
  - **Epilogue**: write the resulting accumulator / VM
    state to a sentinel GFLAG, GNUM, or GSTRING. The
    sentinel write opcode is known-good (e.g. `gpl_set_var`).
  - **Optional**: `gpl_save_game` to force a save if the
    auto-flush to DARKRUN.GFF doesn't happen within the
    test budget.
- **Boot-chunk identification**. Use `gpl-disasm
  --global-cfg` to identify chunks that are referenced by
  the engine's main-loop scripts (the "always runs on
  start" chunks). Empirically: scan known-runs-on-boot
  chunks like `GPL /1` (the global-functions chunk) for
  hookable extension points where a test chunk can be
  spliced.

### Scope (out)

- **DOSBox debugger IPC**. Out for v0.2.0; the cheap path
  (observe via save-state diff) gets us most of the value.
- **Automated bisection** of opcode parameters (binary
  search to determine which byte controls which behaviour).
  Queued for v0.3.0+; v0.2.0 ships the single-shot observe.

### Implementation steps

1. **Identify a boot-time chunk** that runs early. Candidates:
   - `MAS /0` is often the master script entry point.
   - `GPL /1..N` global functions chunks; trace
     `gpl-disasm`'s global CFG for chunks with no incoming
     callers (engine-invoked).
   - The simplest: replace the entire `GPL /1` body with a
     test recipe; if the engine boots far enough to run it,
     we'll see the effect.
2. **Add `gpl-asm` recipe templating helper** (depends on
   v0.6.0's macros). A recipe is a `.asm` file with `%define`
   placeholders the harness substitutes.
3. **Pattern-search for the GPL global arrays in DS2
   DSUN.EXE**:
   - The arrays are referenced by every `gpl_set_var` /
     `gpl_get_var` opcode handler in the VM.
   - The pattern: 32-bit (or 16-bit, in real-mode segments)
     base address loads followed by `var_id`-indexed array
     access. Look for `ba <addr_lo> <addr_hi>` or
     `bf <addr> <addr>` instructions paired with array-
     access patterns.
   - Cross-reference against the DSO `gGflagvar`,
     `gGnumvar`, `gGbignumvar` symbols (the 8-byte stride
     between adjacent pointer slots is distinctive).
4. **Add `run` subcommand**:
   - Argparse for `--keep-session`, `--repro-bug-id`
     (default: `ds1-fuzz-tmp`), `--budget-seconds`
     (default 60).
   - Synthesise a `repro` fixture: a temporary
     `bugs/opcode-fuzz-tmp/` with the patched GPLDATA.GFF
     in `[setup].copy_files`.
   - Capture pre-state: read source `.games/ds1/__support/save/CHARSAVE.GFF`
     + `DARKRUN.GFF` (or the session's persisted state).
   - Spawn `repro.py opcode-fuzz-tmp --play --session
     opcode-fuzz-tmp` (with scripted keystrokes to navigate
     past the boot screen).
   - Capture post-state: same paths after the run.
   - Diff via save-inspect, emit JSON.
5. **First test**: a "null recipe" that writes sentinel to a
   known GFLAG. If post-state shows the GFLAG set, the
   pipeline works.
6. **Second test**: pick a known opcode (e.g.
   `gpl_immed 0x42`) and confirm the accumulator value
   ends up where the epilogue writes it.

### Test plan

- Pipeline smoke: null recipe writes sentinel; observe.
- Known-opcode confirmation: `gpl_immed` + sentinel-write
  pattern produces the expected value in the post-state
  diff.
- (Stretch) Unknown-opcode discovery: pick one of the
  high-number opcodes we have weakest semantics for, run
  the recipe, document the observed effect in
  `docs/gpl-opcodes.md`.

### Risks

- **Boot-chunk identification might fail**. The engine
  might not actually execute any GPL chunk before the user
  interacts with the main menu, in which case input
  automation is required to step past the menu before any
  fuzz observation happens. This is why `repro v0.3.0` is
  a prerequisite.
- **DARKRUN.GFF flush timing**. Globals might not persist
  to DARKRUN.GFF until the engine explicitly saves. If so,
  the test chunk needs an in-script `gpl_save_game` (or
  the harness needs to trigger an in-game save via input
  automation).
- **DOSBox crashes on the synthesised chunk**. The
  validator pass in `gpl-asm` v0.5.0 catches structural
  issues; harder failures (the engine state machine
  doesn't expect the chunk to fire from this caller, etc.)
  can crash mid-run. Treat as a "PASS-ish" signal: at
  least the engine *got to* the chunk before crashing.

### Effort estimate

Multi-session. v0.2.0 is "pipeline works + null recipe
proves observability"; full opcode-discovery loop is v0.3.0+.

---

## `region-render` v0.6.0: third try at `--animate`

Two prior attempts produced documentation but no feature.
The current state: `docs/dsun-exe-re.md` §4.5 lists three
attack surfaces. v0.6.0 is one more time-boxed pass; pre-
committed fallback is docs-only.

### Findings from this research pass

- **Public state of the art**: no public Dark Sun engine
  has decoded the cycle table. libgff doesn't have it;
  soloscuro-archive doesn't have it; `dsun_music`'s
  region-tool has the TODO. The DSUN.EXE work in
  `docs/dsun-exe-re.md` §4 is where the public record
  ends.
- **Our prior findings** (which §4 covers): the four
  palette-write primitives at DS1 `0x1168c..0x288c4` are
  catalogued. The DS2 mirrors are at `0x13bc3..0x...`.
  Neither the cycle table nor the routine that walks it
  has been located.

### Three attack surfaces (carried over from §4.5)

1. **Caller-search against `write_palette_range`
   (`0x288a4`)**. The cycle update almost certainly
   delegates to this helper; find the callers.
   - Blocker: we don't know the segment selector for
     `0x288a4`'s segment. Same problem as §3.3 (the
     dispatcher caller hunt). The technique that found
     `0x3a98` for the dispatcher segment can be applied
     here.
2. **Tick-handler / timer-ISR trace**. The cycle runs
   every N ticks. DSO has `gTheDJTimer 0x001BE450` +
   `hFrameTimer 0x0010B3E4` (DSO offsets). Find the DS2
   counterparts; the cycle handler will be near them in the
   main loop's tick dispatch.
3. **DS2 shape-match against DSO's `VGAColorCycle`
   `0x0009EAA3 f`**. Look for the byte signature of the
   DSO function in DS2 DSUN.EXE: a small loop reading from
   a state global, iterating a table, writing to VGA ports.
   The shape is distinctive.

### Scope (in)

- One more focused attempt at locating the cycle routine
  using surface (1): the segment-selector trick from §3.3,
  applied to `write_palette_range`'s segment.
- If located: implement cycle-table parser + `--animate
  PNG-sequence` output. Document fully in `dsun-exe-re.md`.
- If NOT located in ~3 passes: ship a docs-only `§4` update
  that documents what we tried, what we ruled out, and the
  current next-step direction. `region-render` stays at
  v0.5.0.

### Implementation steps (if found)

1. Add cycle-table reader to `region-render/src/lib.rs`.
   Given the table bytes (from DSUN.EXE's static data
   segment): parse `count × CycleRecord`.
2. Add `--animate --frames N -o region-NNN.png` CLI flag.
   For each frame `0..N-1`: advance the cycle phase by 1
   tick, apply the rotated palette to the base CPAL/PAL
   load, render. Emit numbered PNG sequence.
3. No GIF / WebP output in v0.6.0; would need a new dep.
4. Update README + version bump.

### Test plan

- Visual: pick a DS1 region known to have animated water /
  torches; render with `--animate --frames 30`; eyeball the
  sequence shows expected cycling.
- Corpus: every region renders with `--animate --frames 1`
  matching the v0.5.0 single-frame output (no regression).

### Risks

- **Third attempt also misses**. Pre-committed: ship as
  docs-only update if so. Don't fight harder.

### Effort estimate

If cycle table cracks: one to two sessions. If not: one
session for the docs-only ship.

---

## Order of operations

1. **`gpl-asm v0.6.0`** first. Lowest risk, no game files,
   cleanest session win. Unblocks `opcode-fuzz v0.2.0`'s
   recipe-templating macros.
2. **`dialog-extract v0.5.0`** second. Self-contained on
   existing CFG data. Useful improvement; doesn't unblock
   anything else but ships cleanly.
3. **`repro v0.3.0` priority 1 (session continuity)** third.
   Brandon's specific ask. Doesn't need dep approvals.
4. **`repro v0.3.0` priority 2 + 3** as a follow-on, once
   ydotool / recorder deps are approved.
5. **`opcode-fuzz v0.2.0`** after `repro v0.3.0` ships the
   input automation. Possibly in parallel with `region-
   render v0.6.0` since they don't touch the same files.
6. **`region-render v0.6.0`** last. Highest risk; the
   docs-only fallback is the realistic outcome.

This order respects [memory `feedback-tools-before-patches`]:
finish every tool's next mature version before considering
any darkfix patch work.

---

## Cross-cutting notes

- **No new third-party deps without approval**. v0.3.0's
  input automation and video capture each carry one
  potential dep (ydotool, GNOME recorder). Both require
  Brandon's sign-off before staged into the harness.
- **MEL audio gotcha** continues to apply to anything that
  runs DSUN.EXE under DOSBox. The `sound_ds`-generated
  `SOUND.CFG` files in `tools/repro/bugs/ds[12]-smoke/`
  remain the workaround; new fixtures should crib the same
  pattern.
- **Overlay-mount discipline** ([memory
  `feedback-never-break-install`]) continues to apply. Any
  GFF / save / config write happens in the C: overlay, not
  the install.
- **No em-dashes in prose**. The
  `grep -n "—"` check before every commit is the discipline.
- **Always update on a ship**: tool README, VERSION,
  Cargo.toml (Rust), patchnotes.md (newest at top),
  roadmap.md (tickboxes), tools/README.md (index row).
