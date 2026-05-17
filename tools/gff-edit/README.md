# gff-edit

Pure-Rust reader and writer for SSI's **GFF** container format,
the on-disk container used by SSI's Dark Sun CRPGs (and other
SSI titles of the era). The first foundation tool of the OpenDS
toolkit: every later tool reads or writes GFFs through this
crate.

- **Language**: Rust (edition 2024).
- **Version**: see [`VERSION`](VERSION).
- **License**: MIT.

Provides a library (`gff_edit`) and a CLI (`gff-cat`).

## What is GFF?

A small file container: 28-byte header, a contiguous chunk-data
area, a table of contents, and a free list. Each chunk has a
4-byte FOURCC type, a 32-bit resource id, an offset, and a
length. The on-disk layout is documented in
[`../../docs/file-formats.md`](../../docs/file-formats.md) §1.

Not to be confused with **BioWare's GFF** (Aurora / NWN / Dragon
Age), which shares only the abbreviation. SSI's GFF predates
BioWare's by years and is structurally unrelated.

## Library

```rust
use gff_edit::Gff;

let gff = Gff::open("path/to/RGN02.GFF")?;
for chunk in gff.chunks() {
    println!(
        "{} id={} offset={} len={}",
        chunk.kind(), chunk.id(), chunk.location(), chunk.len()
    );
}
let bytes = gff.read(b"GPL ", 7)?;  // get the bytes of GPL chunk id 7
```

To build a GFF from scratch (v0.5.0+, indexed-only):

```rust
use gff_edit::{FourCC, GffBuilder};

let mut b = GffBuilder::new().with_data0(1);
b.add_chunk(FourCC::from_str("GPL ").unwrap(), 0, gpl_bytes);
b.add_chunk(FourCC::from_str("MAS ").unwrap(), 0, mas_bytes);
let gff_bytes: Vec<u8> = b.build()?;
std::fs::write("synth.gff", gff_bytes)?;
```

API surface lands incrementally; see
[`../../roadmap.md`](../../roadmap.md) Phase 1.

## CLI: `gff-cat`

```sh
gff-cat info  <file> [--json]           # print header + TOC summary
gff-cat list  <file> [--json]           # one row per chunk: kind, id, offset, len
gff-cat extract <file> <kind> <id>      # write chunk bytes to stdout (or -o <file>)
gff-cat extract <file> --all -o <dir>   # dump every chunk to <dir>/<kind>-<id>.bin
gff-cat replace <file> <kind> <id> <bytes-file> -o <out>
                                        # swap a chunk and write modified GFF to <out>
gff-cat dump-text <file> -o <dir>       # write TEXT/ETME/MERR/NAME/SPIN as .txt files
gff-cat pack-text <file> <dir> -o <out> # repack <kind>-<id>.txt files into a new GFF
gff-cat kind <FOURCC>                   # print the FOURCC's catalogue entry
gff-cat kind --list                     # print every catalogue entry
```

## Build

```sh
cd /path/to/opends
cargo build -p gff-edit --release
./target/release/gff-cat info /path/to/some.gff
```

## Roadmap

- **v0.1.0** — header + TOC parser, chunk iteration,
  `gff-cat info`, `gff-cat list`. Read-only, indexed types only.
- **v0.2.0** — segmented chunks fully resolved via the GFFI
  cross-reference; `gff-cat extract`; library `read()` works
  for both indexed and segmented chunks. Verified against 128
  GFFs across DS1 and DS2 with 63,080 chunks resolved.
- **v0.3.0** — writer: `Gff::replace_chunk` and `gff-cat
  replace`. In-place if the new bytes fit, append at
  end-of-file otherwise. Round-trip verified byte-identical
  across all 128 corpus GFFs.
- **v0.4.0** — modder readability layer.
  `gff-cat extract --all` (bulk chunk dump).
  `gff-cat info --json` / `list --json` (machine-readable).
  `gff-cat dump-text` / `pack-text` for TEXT/ETME/MERR/NAME/
  SPIN chunks (the lowest-friction mod loop: dump → edit
  `.txt` files → repack). `gff-cat kind <FOURCC>` for
  catalogue lookups. 17/17 text-bearing GFFs round-trip
  byte-identical.
- **v0.5.0 (current)** — construction from scratch via
  `GffBuilder` (library-only; no CLI surface). Indexed types
  only: `GffBuilder::new()`, `add_chunk(kind, id, payload)`,
  `with_data0`, `with_file_flags`, `build()`. Corpus
  round-trip verified structural equivalence on 50
  indexed-only GFFs across DS1 + DS2; 78 segmented-type GFFs
  skipped pending v0.6.0. Powers opcode-fuzz recipe
  synthesis (single-chunk synthetic GFFs).
- v0.6.0 — segmented-type build (secondary table + GFFI
  cross-reference dance) so the builder covers the full GFF
  feature set.
- v1.0.0 — API frozen; full DS1 and DS2 corpus covered.
