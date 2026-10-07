# xmi2mid

Convert Dark Sun XMI sequence payloads to standard MIDI files,
branch-aware. Every GSEQ/LSEQ/PSEQ/CSEQ/FSEQ chunk payload (the XMI
dialect: FORM XDIR / CAT XMID / TIMB / RBRN / EVNT) becomes a
format-0 SMF at 120 Hz plus a JSON sidecar carrying the
adaptive-music data a plain MIDI cannot hold: the RBRN branch table,
the FOR/NEXT loop spans, the branch-select events, and the TIMB
patch lists.

- **Language**: Python (stdlib only).
- **Requires**: Python 3.11+ (matches the rest of the toolkit).
- **Version**: see [`VERSION`](VERSION).
- **License**: MIT.

## Usage

```sh
# inputs are the *.xmi payloads audio-extract dumps
python3 xmi2mid.py port-spike/generated/audio/RESOURCE/*.xmi --out midi-out
python3 xmi2mid.py --selftest
```

Output per input: `<stem>.mid` (the linear pass, note-ons resolved
to real note-offs, XMIDI controllers removed) and `<stem>.xmi.json`
(total ticks, duration at 120 Hz, TIMB patches, RBRN branches, loop
spans, branch selects). Ticks map 1:1, so the sidecar coordinates are
already in the MIDI's time base.

## Conversion policy

The classic public-domain xmi2mid (libgff bundles it) flattens these
songs: it skips every non-EVNT chunk, so the branch tables vanish
and DS1's adaptive loops become first-branch-only music. This
converter keeps the linear note data and moves the adaptivity into
the sidecar instead of guessing: a port's music director implements
FOR/NEXT wraps and 0x78 branch switches from the JSON, which is
exactly the machinery the engine's Mel library runs (see
docs/file-formats.md 5 and docs/port-digs-2026-10-06.md 2).

Corpus facts this tool encodes: XMI deltas are runs of bytes < 0x80
summed to the next status byte; note-ons carry a VLQ duration; RBRN
entries are (LE u16 id, LE u32 tick); and the shipped files declare
XDIR's FORM size as covering only INFO, with the CAT chunk following
as a sibling past the declared extent.

## What it verified against

All 83 DS1 sequence chunks (branch counts and patch counts match the
RBRN dig's independent per-track table; PSEQ carries no TIMB) and
the DS2 floppy set (zero branches, zero loops, matching the
no-RBRN-in-DS2 finding). The synthetic-payload selftest needs no
game files and runs in CI.
