# Attribution audit, 2026-09-20 (three upstreams)

Agent-wave audit of the three reference checkouts against
`CREDITS.md` and the in-code citations. Manifest fixes from this
audit landed in the same-day commit "credits: attribution-audit
fixes". This file records the findings and the checks that came
back clean, so the next audit starts from here.

## dsun_music (John Glassmyer)

18 substantive upstream modules cross-checked. The two existing
CREDITS rows (writer policy, GFFI segmented layout) verify exact
against `GffFile.java` and `SecondaryGffiTable.java`.

Un-credited ports found (all certain; all rows now added):

1. Region geometry port (region-render): constants 128/98/16
   (`RegionTool.java:167-169`), GMAP wall mask 0x1F (`:172`), wall
   id `region*100+idx-1` (`:275`), wall placement +8-w/2, +16-h
   (`:289-290`), ETAB 8-byte record with mirrored bit 0x80
   (`:300-317`), OJFF anchor +0x2/+0x4/+0xC (`:319-331`), mirror
   compositing (`:346`) - code comments were thorough, the manifest
   row was missing entirely (`tools/region-render/README.md`
   promises it).
2. PLAN frame decoder: `ImageReading.java:244-291`
   (`readPlanarImageFrame`, upstream RE note: DSUN.EXE 0x1A1B0) +
   `BitChomper.java:41-78` into `image-extract` `decode_plan`
   (`lib.rs:788-878`); cited in code and `docs/presentation-formats.md`
   but absent from the manifest.
3. PLNR bit-extraction swap: since image-extract v0.2.0 the
   extraction half of `plnr_get_next` is dsun_music's big-endian
   `BitChomper` (`lib.rs:700-707` documents the switch); the
   manifest row still described libgff's rotated chomp alone.

Drift fixed: the PLNR row (co-credit), the region-render README
promise, and README's Glassmyer paragraph (now lists the full
ported surface).

Missed-mining candidates (not acted on): `xmi-tool/XmiTool.java`
(full XMI/XMIDI parser with FOR/NEXT loop semantics - would give
opends its first audio tool), `GffTool.java:143-167` dead-space
gap report (natural `gff-cat gaps`), `GffFileList.java` merged
multi-GFF first-match lookup (natural `gff-edit` GffSet).

## dsoageofheroes (libgff / soloscuro-archive)

34 substantive modules inventoried, 21 cross-checked line-by-line.
**No un-credited ports found** - the 129-entry opcode table
(entry-by-entry), GPL_* constants, `gpl_retval` safe set (all 21
cases incl. 0x1a), the 0xb3 special case, the 7-bit packed-string
decoder, segmented flags/resolution, palette/RLE/PLNR, the
CHAR/combat/item/psionic structs, and all 23 cited parse.c line
anchors verify exact.

Drift fixed: three CREDITS rows cited `src/gpl/gpl.c` (an 87-line
stub) for functions that live in `src/gff.c` (`gff_read_headers`
at `src/gff.c:260`, the flag-mask test at `:293`,
`gff_find_chunk_header` at `:369`); the dead
`decode_compressed_string` consumer pointer (dialog-extract v0.2.0+
reads `gpl-disasm --json`; same stale comment in
`gpl-disasm/src/lib.rs`); gpl-asm and opcode-fuzz added to the GPL
consumers list; `KIND_CATALOGUE` and `FileHeader` comments now cite
libgff directly.

Missed-mining candidates: CPAL/VECT/PLYL/CMAT/ALL/DATA chunk kinds
(named in `gfftypes.h`, still undocumented in
`docs/format-coverage.md`), GPL variable-space capacities
(`include/gpl/var.h:78-92`), the GPL check-type registry
(`var.h:97-111`), the XMI-to-MIDI pipeline (`src/xmi.c`), SCMD
record semantics (`common.h:157-166`), SJMP shape
(`common.h:232-238`), and libgff's per-kind pretty-printers as the
template for `gff-cat kind` subcommands.

## dso-online (greg-kennedy, AGPL-3.0)

Upstream inventory: symbols.txt (3,530 functions + 2,247 labels,
verified counts), dump2sym.pl, unwatcom.pl, mdark.bin, DSOServer
(Python), LAUNCHER. ~12 distinct checks run.

One high-confidence un-credited use (row now added): the PSP cost
table at `mdark.bin` 0x10AA59 in `docs/object-formats.md` is
located via `symbols.txt:2223` (`psionicDefs` label); the doc said
"DSO" without naming the source. Cited as a symbol-name fact per
the AGPL research-only policy; no source ported.

**AGPL contamination: none.** unwatcom.pl vs the overlay tooling
(different formats, `overlay-formats.md` declares originality),
DSOServer vs opends Python (no server/packet code downstream),
dump2sym.pl vs the import scripts (independent parsers).

Drift fixed: CREDITS still listed dso-online under "Influences
(read but not yet ported)" though v0.4.0 shipped the import script
and six `dso_source` rows exist in `tools/ovr-map/syms/`; the
psionicDefs row moves it to per-feature credit.

Missed-mining candidates: the unmined symbol families
(`_AI`/combat beyond the 5 catalogued `Combat*` names, GUI 190,
GET 159), `DSOServer/Compression.py`'s RLE as a lead for the open
save-compression question in `file-formats.md`, and the call-graph
shape-matching possible against the debug-build `mdark.bin`.

## Method note

All three audits were read-only agent waves (Explore, GLM-5.3-Flash)
with every claim carrying both-side `file:line` evidence; the
manifest fixes were applied in the main thread the same day.
