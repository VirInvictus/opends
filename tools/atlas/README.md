# atlas

Static-HTML site generator for an OpenDS toolkit run. Drives the
existing tools as subprocesses and produces a browsable directory
of HTML pages: every game's sprites, region maps, and dialog
behind one file:// URL. The closest thing the toolkit has to
"open the whole game and look around."

- **Language**: Python (stdlib only).
- **Requires**: Python 3.11+; `image-extract`, `region-render`
  (Rust binaries; built via `cargo build --release`);
  `dialog-extract.py` (Python).
- **Version**: see [`VERSION`](VERSION).
- **License**: MIT.

## Usage

```sh
cargo build --release            # build the Rust tools
python3 atlas.py build \
    --games-dir ../../.games \
    -o /tmp/opends-atlas
xdg-open /tmp/opends-atlas/index.html
```

`--games-dir` can be a directory containing multiple installs
(one subdir per game; auto-detected by presence of `DSUN.EXE`)
or a single game install. Each detected game gets its own
section.

## What v0.1.0 ships

**Three sections per game**: sprite gallery, region maps, and
dialog browser. Cross-section nav bar threaded through every
page; static HTML; no JavaScript.

```
<output>/
├── index.html              # root: links to each game
├── ds1/
│   ├── index.html          # ds1 landing
│   ├── sprites-RESOURCE.html  # gallery of every BMP/PORT/ICON
│   ├── sprites/RESOURCE/*.png # the actual sprite files
│   ├── regions.html        # all rendered regions inline
│   ├── regions/*.png       # per-region rendered map
│   └── dialog-raw.html     # dialog-extract --format html output
└── ds2/
    └── (same layout)
```

Smoke against the corpus: 1685 sprites (DS1 649 + DS2 1036), 53
region maps (DS1 33 + DS2 20), 2 dialog browsers; full site
~92 MB.

### Cross-section nav

Every page carries a top nav bar linking back to the root index,
the game index, and the three section pages. The dialog page is
the existing `dialog-extract --format html` output post-edited to
add the nav bar without rewriting its body.

### Tool discovery

Mirrors the umbrella `opends` crate's pattern: prefers
`<workspace-root>/target/release/<binary>`, falls back to
`target/debug/`, then `$PATH`. Python tools resolve to
`<workspace-root>/tools/<crate>/<name>.py` and invoke via
`python3`. Each missing tool prints a warning and skips that
section gracefully.

## What v0.1.0 does NOT ship

- **Cross-references between sections** (a sprite's page
  linking to which regions use it, a dialog NPC linking to
  their portrait). The per-section pages are independent in
  v0.1.0. Cross-references need the entity-table / OJFF /
  speaker catalogues to align, which is a v0.2.0 piece.
- **Search**. v0.1.0 is static (no JS); a JS-only search index
  is on the v0.2.0 candidate list.
- **Save-state inspector**. Will consume `save-inspect`
  output once a played-save corpus exists for both games.
- **GPL chunk index**. Will consume `gpl-disasm --json` plus
  the curated symbol catalogues from `tools/gpl-disasm/syms/`.
- **GitHub Pages publish**. Generates locally; CI publishing
  comes later.
- **Per-frame animated sprites**. Each chunk currently shows
  only its first frame; `image-extract --frames-all` output
  is the next obvious enrichment.

## Why this exists

Before atlas, "look at all the sprites" meant a one-shot
`image-extract --all` + `xdg-open` per file. "Read all the
dialog" meant running dialog-extract with the right flags and
grep'ing the JSON. atlas drops the whole game on disk as
browsable HTML in one command. The modder workflow becomes
"open `index.html`, click around, find the thing, then drop
to the underlying tool to edit." The mod author's "what is
already here?" question gets a visual answer.
