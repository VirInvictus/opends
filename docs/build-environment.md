# Build Environment

Fedora-first dev setup for authoring darkfix patches. Other
distros and OSes work too; commands below are Fedora 43.

## 1. System packages

```sh
sudo dnf install \
    innoextract \
    unrar p7zip p7zip-plugins \
    radare2 hexedit \
    python3 python3-pip \
    git \
    flac vorbis-tools
```

`ghidra` is available on Fedora as a third-party COPR or via
direct download. Optional; r2 covers most needs.

## 2. Python tooling

The applier and patch-authoring helpers are Python 3 + a small
set of pip packages. Per `~/CLAUDE.md`, prefer `uv` for
environment management:

```sh
cd ~/.gitrepos/opends    # (will be ~/.gitrepos/darkfix after rename)
uv venv .venv
source .venv/bin/activate
uv pip install bsdiff4 keystone-engine
```

`bsdiff4` for binary diff/patch. `keystone-engine` for
assembling x86 instructions on the fly when authoring code-cave
binary fixes.

## 3. DOSBox-Staging

Flatpak is the easiest path:

```sh
flatpak install flathub io.github.dosbox_staging
```

DOSBox-Staging is the modern fork of DOSBox; it has better
sound, better debugging, and is where the community has been
since ~2020. Original DOSBox 0.74-2 (which GOG bundles) also
works but offers less.

## 4. Game files

You provide a legitimate copy of one or both games. GOG
installers are the easiest:

- *Dark Sun: Shattered Lands*: GOG product ID 1432723859.
- *Dark Sun: Wake of the Ravager*: GOG product ID 1432903719.

Place the GOG installer EXEs in `.games/` (gitignored). Then
extract:

```sh
cd ~/.gitrepos/opends
tools/extract.sh    # forthcoming
```

Until that script lands, do it by hand:

```sh
mkdir -p extracted
innoextract -d extracted/ds1 \
    .games/setup_dark_sun_shattered_lands_1.1_cs_*.exe
innoextract -d extracted/ds2 \
    .games/setup_dark_sun_2_wake_of_the_ravager_1.1_*.exe
```

If you also have the GOG installers wrapped in `.rar`
(like the GOG-Games.to redistribution), unpack the rars first
into `.games/`:

```sh
unrar x .games/game-dark.sun.shattered.lands*.rar .games/
unrar x .games/game-dark.sun.wake.of.the.ravager*.rar .games/
```

## 5. Verifying your install

Once `tools/verify-install.py` lands:

```sh
tools/verify-install.py extracted/ds1
# → "GOG 1.10 / Linux / OK"
```

The script computes SHA256 of every key file and matches
against an embedded manifest of known-good hashes. Any
mismatch means your install isn't the canonical 1.10; the
patch may not apply cleanly.

## 6. Editor setup

No special config required. The project follows the
conventions in `~/CLAUDE.md`:

- Python files: `pyproject.toml`-driven if/when we add
  formatting; stdlib only otherwise.
- Markdown: 80-char wrap, GFM.
- TOML for manifests.
- No emojis in source.

`emacsclient` and `nvim` both work; this is a small project
that doesn't need an IDE.

## 7. Sanity check (Day 1 task list)

After setup, run:

```sh
ls extracted/ds1/DSUN.EXE   # exists, ~611KB
ls extracted/ds2/DSUN.EXE   # exists, ~634KB
ls extracted/ds2/MUSIC/Track02.ogg  # exists
file extracted/ds1/RESOURCE.GFF     # → "data" (binary)
head -c 4 extracted/ds1/RESOURCE.GFF  # → "GFFI"
```

If all of the above pass, you're ready to start fixing bugs.

## 8. Running the games for repro

```sh
flatpak run io.github.dosbox_staging \
    -conf extracted/ds1/DOSBOX/dosbox_darksun_single.conf
flatpak run io.github.dosbox_staging \
    -conf extracted/ds2/DOSBOX/dosbox_darksun_2_single.conf
```

(Confirm the .conf paths in `extracted/{ds1,ds2}/DOSBOX/` after
extraction; GOG ships the configurations there.)

For debugging, use `--debug`:

```sh
flatpak run io.github.dosbox_staging --debug \
    -conf extracted/ds2/DOSBOX/...
```

DOSBox's debugger lets you set breakpoints in DOS memory,
which is invaluable when correlating r2 disassembly to live
behavior.

## 9. Common gotchas

- **GOG cloud_saves**: GOG redirects in-DOSBox file writes
  (including saves) to a `cloud_saves/` directory next to the
  game. If a fix looks like it isn't applying, check that
  you're editing the actual game files and not the cloud-save
  shadow tree.
- **Permissions on extracted files**: `innoextract` may emit
  files owned by your user with `0644` — that's fine. Don't
  run with `sudo`.
- **NTFS mount**: per `~/CLAUDE.md`, `/mnt/SharedData` is NTFS
  and permissions are advisory. If you keep extracted games
  there, expect spurious mode/owner weirdness.
