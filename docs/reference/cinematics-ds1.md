# DS1 cinematics: the BMA frame codec, the ACF scripts, the player chain

The last undecoded asset family in the corpus, decoded (port-mining wave 3,
2026-09-19). Engine-derived from DSUN.EXE and cross-validated byte-exact
against the corpus: all 708 BMA frames in 48 containers, plus all 19 BMP
stills, decode cleanly under these rules (corpus validator and reference
renderer in the wave scratch; the orchestrator visually verified rendered
frames). This supersedes presentation-formats.md section 4's open item.

DS2's cinematics remain standard Autodesk FLI (verified: magic 0xAF11,
FLI_LC/FLI_COLOR256 chunks); DS1's BMA shares nothing structural with FLIC.
The frequent 0xF1 bytes in BMA streams are x-coordinates and RLE payload,
not FLI opcodes.

## 1. The BMA frame codec

A row-addressed delta format whose only shared DNA with FLIC is "RLE per
row". The pixel primitive is exactly the existing DS1-RLE of
image-extract (`decode_ds1_rle`): code byte c -> run = c/2 + 1; even c =
run literal bytes follow, odd c = next byte repeated run times.

Engine ground truth: decoder resident at file 0x1532A (segtab record 7,
entered 0x0980:0x672A), wrapper 0x22620; key inner sites 0x153D5 (container
header bounds), 0x1541F (frame body normalize; skip u16 w, u16 h), 0x15481
(opcode byte; 0xFF = end of frame), 0x154DF (record read), 0x15535 (RLE
decode), 0x1556B (four unrolled plane writers: unchained 256-color VGA,
pixel (x,y) -> plane x&3, byte 80*y + x>>2; a chunky renderer just writes
screen[y][x]).

```
frame := u16 width (=320)  u16 height (=200)  row_group*  0xFF

row_group := u8 row            # 0-based screen row (non-decreasing in the corpus)
              record*          # records continue until one has bit15 set

record := u16 xword            # bit15 (0x8000) = LAST record for this row
          u8  span             # pixels this record writes
          u8  count            # length of the following RLE byte string
          u8  data[count]      # DS1-RLE codes; decodes to EXACTLY span pixels
```

Semantics that matter for a port:

- The screen canvas PERSISTS across frames, across containers, and across
  the whole cinematic: every frame is applied onto the previous screen
  state. "Keyframes" are simply frames whose records cover all 200 rows.
- No-op frames are legal and common (52 in BMA 12 container 7 alone):
  body = just 0xFF ("hold screen one tick").
- Multiple records per row tile horizontally.
- A `flags & 3` variant exists (body starts w/h then records; bit 1 =
  bottom-up rows) for the sprite/blit path; the movie path passes flags 0.
- Invalid rows are clipped (skip-records path above/below the viewport).

Decode algorithm: walk the chunk as back-to-back standard bitmap containers
(exactly image-extract's `Bitmap::from_bytes` layout: u32 size, u16
frame_count, u32 offsets[]), and per frame apply the row/record wrapper
above onto the persistent 320x200 screen.

Corpus facts: 11 BMA chunks = 48 containers, 708 frames, 2,484,342 bytes.
The 19 CINE.GFF BMP stills are NOT DS1-RLE/PLNR-family frames:
image-extract would misparse them today; they are single-frame containers
of this same BMA codec (BMP 5's frame body is byte-identical to BMA 4
container 0 frame 0). BMA 11's two frames are registered by ACF 11 but
never played (706 op-05 calls vs 708 frames).

## 2. The ACF scripts

Encoding: an ACF chunk is an array of u16 LE words;
`instruction = (opcode << 8) | (2 * total_words)` where total includes the
opcode word; operands are the following (total-1) words; next_pc = pc +
total. Interpreter at overlay module 53 (file 0x91D10..0x92A7D; dispatch
table 0x92222, 128 entries). A full PRE-SCAN pass executes only opcode-01
records first, then pc resets and the script runs.

| Op | Semantics | Count |
|---|---|---|
| 00 | END | 13 |
| 01 | register stream segment (index 0..0x100, frames, byte_size) into table [0x9D3C]; the registrations equal BMA N's container list exactly | 48 |
| 03 / 04 | audio subsystem on / off | 5 / 0 |
| 05 | movie frame: pump 0xFA0 bytes if the buffer is low, decode + display the next BMA frame (tick-gated) | 706 |
| 06 | wait N ticks (134 of 155 uses are N=1: the per-frame pace) | 155 |
| 07 | rewind BMA stream to segment 0 | 0 (unused) |
| 08 | play sound id, then wait N ticks | 5 |
| 14-1A | palette entry writers into staging [0x458]+3*idx (14 = set entry idx/R/G/B packed in two operands; 15 = commit; 16/19/1A = variants) | ~9.5k (fades) |
| 28-2C | still/BMA stream control: 28 = load BMP still id into slot 0..4; 2A = seek the BMA stream to a frame via the op-01 table | 25/25/25/3 |
| 3C-40 | palette load (`PAL ` chunk) + the pixel-dissolve transition | 12/5/4 |
| 50-5E | staged effect scenes (only 5B used) | 1 |
| 64-67 | music: 64 = play cue id; the observed operands 0x1A..0x1D are GSEQ/LSEQ/PSEQ 26..29 exactly | 9 |
| 79-7F | BMP compositing scenes (7F = 12-operand scene draw) | 1 |

Unknown opcodes hit a poll-and-continue default (NOP); word reads past the
script end return 0 (missing terminators behave as END). Every instruction
is wrapped by a poll whose result ends playback (the skip/ESC path).
Readable specimen: ACF 11 = audio on, music 28, set 8000, palette, load
still BMP 7, stream seek, one 7F composite, wait 0x32, register BMA 11's
two containers, END without playing them.

## 3. The player chain

- Entry: overlay module 4 (file 0x56936..0x56A6C) calls module 53 entry 0
  with cinematic ids 1, 2, ... 12 sequentially for the intro, bracketed by
  sound-system on/off. Entry 2 shuts down (closes the CINE.GFF handle).
- Init (entry 1, 0x92403): opens CINE.GFF, allocates the 64 KB stream
  buffer, a 64 x dword segment table, and 5 BMP still slots.
- Streaming: the pump reads BMA chunks in RANGES via the 5-arg loader at
  file 0x2A1A6 (`load_range(fourcc, id, offset, nbytes, far*)`); container
  sizes are capped at 0x10000 by construction.
- Frame rate: op 05 gates on the tick counter [0x348]:0x2C5 vs frames
  displayed; the counter increments in the event handler at 0x36A73 on
  event 0x7F. Movies run one op 05 + one `wait 1` per frame: ONE FRAME PER
  TICK. The tick source is the audio-timer callback chain (CINE.GFF's
  CSEQ 1000 / PSEQ 26..29 are one identical 74-byte XMI timer track:
  tempo 416,538 microseconds/quarter, AIL loop controllers 0x74/0x75/0x77).
  The exact Hz is the one runtime-measurable unknown.
- Palette: ops 3C-40 load full PAL chunks; 14-1A stage per-entry RGB for
  fades.
- End: opcode 00 or pc >= length returns 1; the module-4 chain proceeds to
  the next id. NO LOOPING exists in the corpus.

## 4. Corrections to presentation-formats.md section 4

1. "the ONE undecoded piece ... no public decoder known": RESOLVED (this
   document).
2. "19 static 320x200 stills": they are BMA-codec single-frame containers,
   not DS1-RLE/PLNR frames; image-extract misparses them today.
3. "BMA 11 (2.5 MB, ids 2..12), ACF 13": refined to 48 containers / 708
   frames / 2,484,342 bytes; ACF id N streams BMA chunk id N; ACF 1 and 13
   are still-only.
4. Engine path pinned: 'ACF ' push 0x91DAF, 'BMA ' push 0x9265A (module
   53); decoder 0x1532A; wrapper 0x22620; intro chain module 4.

## 5. Open (all non-blocking for a decoder)

1. ~~The tick rate in Hz~~ SETTLED by runtime capture (2026-09-19;
   see section 6).
2. Exact bodies of the unused ACF ops (17, 18, 2C, 3D, 3E, 50-5A, 5C-5E,
   67, 79-7E).
3. The screen-slot table's non-fullscreen fields; slot 0 is the movie
   viewport.
4. Which PAL id belongs to which cinematic (extractable by walking each
   ACF's palette ops).
5. The `flags & 3` sprite path's clip arithmetic (unused by op 05).
6. Poll result semantics: skip vs abort detail.

## 6. Runtime capture: the Godot spike ground truth (2026-09-19)

A timed DOSBox run of the real intro (dosbox-staging; the factory
SOUND.CFG from the ds1-smoke fixture is required, DSUN aborts at boot
with a MEL error without it) plus the port-spike re-render settled
four questions:

- **Tick rate: about 12 Hz.** The intro runs roughly 130-140 s wall
  in DOSBox; the baked ACF timeline (1,497 wait ticks across 706
  frames plus stills) at 12 Hz plays 125 s, the residual being the
  engine's music-sync waits (the timeline drops music). One frame per
  tick with waits of 1-2 dominating, exactly as section 3 says.
- **Palette semantics.** ACF 2 stages 256 entries (op 14), commits
  them (op 15), then issues 0x3C 1 before its 80 frames, and the
  frames wear the COMMITTED palette: the starfield and dagger scene is
  near-black, not PAL 1's bright red. A committed block wins over a
  same-part later 0x3C load. The committed block is a built palette:
  index 0 black, 1-7 a dark blue ramp, 8-15 dark reds, 32-47
  browns and tans, 240-254 brights, 255 magenta.
- **Still screens are top-down and palette-switched live.** BMP 1
  (SSI) shows under PAL 1; BMP 2 (the full AD&D screen, all of its
  text baked into the bitmap) and BMP 3 (the title tablet) show under
  PAL 2, even though ACF 1 encodes the 0x3C 2 between still loads.
  A palette load re-renders the displayed screen.
- **The boot sequence** is: ACF 1 stills (SSI, AD&D, title), then
  ACF 2-4 starfield and dagger, ACF 5-8 storm, planet and story
  scrolls, ACF 9-12 gladiator/desert montage and closing text, then
  the WIND 3000 menu.

Two smaller catches from the same pass: the single dithered frame at
the gladiator-to-desert cut is the shipped data's own dissolve step
(CINE BMP 7), not a decode bug; and ACF op 19 takes note-and-channel
style args (1, 80, 95) and reads as a music-note op rather than a
hold, while op 40 takes pairs like (7,5) and (2,1) and is still
unknown (fades or dissolves).
