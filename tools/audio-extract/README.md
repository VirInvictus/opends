# audio-extract

Dump the audio chunks of a Dark Sun GFF container: BVOC/FVOC digital
samples decoded to WAV, GSEQ/LSEQ/PSEQ/CSEQ/MSEQ sequence payloads
dumped verbatim, and an inventory JSON (ids, sizes, sample rates,
durations, magic sniff per sequence).

- **Language**: Python (stdlib only).
- **Requires**: Python 3.11+ (matches the rest of the toolkit).
- **Version**: see [`VERSION`](VERSION).
- **License**: MIT.

## Usage

```sh
python3 audio-extract.py .games/ds1/RESOURCE.GFF .games/ds1/CINE.GFF \
    --out ../../port-spike/generated/audio
python3 audio-extract.py .games/ds2/RESOURCE.GFF --out ../../port-spike/generated/audio
python3 audio-extract.py --selftest             # synthetic container, no games needed
python3 audio-extract.py --selftest-corpus      # measured DS1 invariants (skips if absent)
```

Output layout under `--out`:

```
<out>/RESOURCE/<KIND>-<id>.wav        # decoded BVOC/FVOC (one WAV per format run)
<out>/RESOURCE/<KIND>-<id>.xmi        # verbatim sequence payloads (FORM/CAT magic)
<out>/RESOURCE/<KIND>-<id>.bin        # sequence payloads without FORM magic
<out>/audio-inventory.json            # every chunk: id, offset, length, rate, duration
```

`--no-wav` and `--no-payloads` produce an inventory-only run;
`--kinds BVOC,GSEQ` narrows the extraction.

## What it verifies

`--selftest` builds a synthetic GFF in memory (indexed plus segmented
chunk lists, a full Creative Voice File, a bare VOC block stream) and
asserts the TOC walk and the VOC decoder against it; it needs no game
files, so CI runs it. `--selftest-corpus` asserts the measured DS1
inventory (RESOURCE.GFF: GSEQ/LSEQ 1..23, CSEQ 1000, 111 BVOC in
1..130, no MSEQ/FSEQ; CINE.GFF: tracks 26..29) and skips when
`.games/ds1` is absent.

## Format references

Chunk ids and container layout follow `docs/file-formats.md`; the TOC
walker mirrors the in-repo authority `tools/gff-edit/src/lib.rs`
(`parse_toc`, `resolve_segmented_type`). What the engine *plays* when
is routing, not format: see `docs/audio-routing.md`. VOC block
semantics are the standard Creative Voice File layout; repeat blocks
expand with a bounded cap recorded in the inventory.

Sequence-to-MIDI conversion (XMI: two-byte delta times, TIMB, RBRN)
is a separate future tool; this one only opens the boxes. Every
sequence payload observed in the corpus is a `FORM/XDIR` directory
(the XMI directory form wrapping `CAT/XMID` song forms); the
inventory records the magic rather than assuming it.
