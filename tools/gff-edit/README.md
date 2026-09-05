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
                                        # --json: {size, header: {identity,
                                        #   version, data_location, toc_location,
                                        #   toc_length, file_flags, data0}, types: [...]}
gff-cat list  <file> [--json]           # one row per chunk: kind, id, offset, len
gff-cat extract <file> <kind> <id>      # write chunk bytes to stdout (or -o <file>)
gff-cat extract <file> --all -o <dir>   # dump every chunk to <dir>/<kind>-<id>.bin
gff-cat replace <file> <kind> <id> <bytes-file> -o <out>
                                        # swap a chunk and write modified GFF to <out>
gff-cat dump-text <file> -o <dir>       # write TEXT/ETME/MERR/NAME/SPIN as .txt files
gff-cat pack-text <file> <dir> -o <out> # repack <kind>-<id>.txt files into a new GFF
gff-cat kind <FOURCC>                   # print the FOURCC's catalogue entry
gff-cat kind --list                     # print every catalogue entry
gff-cat what  <file> <kind> <id>        # describe one chunk: purpose, header-derived
                                        # facts, and a next-step tool pointer
```

## Build

```sh
cd /path/to/opends
cargo build -p gff-edit --release
./target/release/gff-cat info /path/to/some.gff
```

## Roadmap

The version history lives in [`../../patchnotes.md`](../../patchnotes.md);
phased plans in [`../../roadmap.md`](../../roadmap.md). Remaining here:
segmented-type *construction* (the builder covers indexed GFFs only;
reading and replacing already work for both) and the v1.0.0 API freeze.
