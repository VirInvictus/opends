# Install Variants

*Reference. Which releases of each game exist, what GOG actually
ships, and what that means for choosing a darkfix patch base.
Established empirically on 2026-06-10; the evidence trail and the
reproduction steps are at the bottom.*

## 1. DS1 (Shattered Lands)

One lineage in practice. The GOG package is a disk-style install:
no CD image, no redbook audio, MIDI music via `GM1.BNK` /
`GM2.BNK`. The canonical manifest at
[`source-hashes/ds1-gog-1.10.toml`](source-hashes/ds1-gog-1.10.toml)
describes the only base we target. No variant question arises.

## 2. DS2 (Wake of the Ravager): two product lines, three binaries

SSI shipped DS2 twice, and the two products are different builds,
not the same data on different media:

| | Floppy ("3.5" disk") | CD |
|---|---|---|
| Resource bundle | `RESFLOP.GFF` (5,200,334 B) | `RESOURCE.GFF` (5,782,746 B in 1.0) |
| Music | MIDI, stored inside `RESFLOP.GFF` | Redbook CD audio (40 tracks); **no MIDI exists** |
| Speech | None | `SPCH*.VOC` / `INTR*.VOC` voice acting |
| Cinematics | None (FLI not shipped) | `CINE/1.FLI`..`5.FLI` |
| 1.0 `DSUN.EXE` | 634,208 B, `bc9cdcbd…` | 634,704 B, `e73f79c3…` |
| 1.10 `DSUN.EXE` | unknown (see §5) | 634,416 B, `ce02ee1f…` |

All three known `DSUN.EXE` binaries self-identify via embedded
strings: the two 1.0 builds carry `VERSION 1.0` and MEL audio
driver 2.2.5 (4/28/94); the CD 1.10 build carries `VERSION 1.1`
and MEL 2.2.7 (10/14/94).

**The GPL scripts are shared across the two lines.** Floppy 1.0
and CD 1.0 have byte-identical `GPLDATA.GFF`
(`11fda69162ad2aaf…`, 2,191,945 B). The 1.10 patch modifies
GPLDATA (GOG's is `be5efb2b76a5f77b…`, same size). This matters
for darkfix: GPL-level fixes, our primary fix surface, are very
likely portable across floppy and CD installs at the same patch
level. Only `DSUN.EXE` binary patches are variant-specific.

## 3. What GOG actually ships (proven, not inferred)

The GOG DS2 package is **the retail CD 1.0, selectively
installed, with SSI's official 1.10 CD patch applied**:

- `game.gog` (109 MB) is the raw retail CD image (Mode 2/2352
  data track). Its install tree carries the 1.0 `DSUN.EXE`
  (`e73f79c3…`), the AIL sound drivers, `INSTALL.EXE`, and demo
  installers for *Menzoberranzan* and *Panzer General*. DOSBox
  mounts it as E: via the `game.ins` cuesheet, with the 40
  redbook tracks remapped to GOG's OGG re-encodes.
- Applying `WAKECD11` (SSI's official 1.10 CD patch, RTPatch
  format, Internet Archive `WAKECD11_ZIP`) to the files from
  `game.gog` reproduces the GOG install tree **byte-identically
  for all 31 shared game files**, including
  `DSUN.EXE = ce02ee1f…` exactly matching
  [`source-hashes/ds2-gog-1.10.toml`](source-hashes/ds2-gog-1.10.toml).
- The patch applies directly to CD 1.0; no intermediate version
  is needed on the CD chain. It modifies `CHARSAVE.GFF`,
  `DSUN.EXE`, `GPLDATA.GFF`, `OBJEX.GFF`, `RESOURCE.GFF`,
  `SOUND.INI`, `STDPATCH.AD` and adds `README.BAT`, `SVIEW.EXE`.
- The only file GOG itself authored is their 114-byte
  `SOUND.BAT` launcher (the retail one is 4,873 B). GOG drops
  the DOS sound-driver `.ADV` files and the installer batches.

So "GOG ships 1.10" is exact: their tree is the official patch
output, byte for byte, with one launcher swapped.

## 4. The community recommendation, and what holds up

A community member recommended targeting the floppy 1.10 rather
than the GOG CD as the darkfix patch base, on player-experience
grounds: the CD version locks music to redbook (no MIDI music
with SB16 digital effects), adds voice acting of debatable
quality, and plays unskippable CD audio during loading screens.

The factual basis checks out. The CD line has no MIDI music at
all (none on the CD, none in the install; the floppy line's MIDI
lives inside `RESFLOP.GFF`), and the speech/redbook hardware
audio paths are CD-line-only.

## 5. But floppy 1.10 is not publicly reconstructible today

Every publicly archived path to a floppy 1.10 install fails:

| Artifact | What it is | Result against pristine floppy 1.0 |
|---|---|---|
| `WAKEDK11_ZIP` (IA) | Official disk 1.10 RTPatch (RTP dated 1995-01-05) | **Refused**: `ept0036` old-file fingerprint mismatch on `DSUN.EXE` |
| `wake3511.exe` (IA, 2004 repack) | Disk 1.10 patch, RTPatch 3.20 SFX (`wake3511` = "Wake 3.5-inch 1.1" per SSI's naming, cf. `rlft3511`) | **Refused**, same error; also refuses the cracked HotU EXE |
| `wake11jc.zip` (Patches Scrolls) | "Jewel case edition" 1.10 RTPatch (RTP dated 1996-01-23) | **Refused**, same error |
| `WAKECD11_ZIP` (IA) | Official CD 1.10 patch | CD-only by design ("will only work for the CD-ROM version") |

The pristine floppy 1.0 base is well-attested: the Internet
Archive `darksun-wake-of-the-ravager` item's `dsun2_english.zip`
EXE (`bc9cdcbd…`) is byte-identical to the pre-crack original
preserved in the same item's HotU repack (`OldExe/DSUN.EXE`
alongside `CRACK.COM`).

SSI's own documentation (the mirrored `wake35.html` update page)
says `WAKE3110.EXE` updates the 3.5" disk version from 1.0 or
1.01 with no 1.02 intermediate. The best hypotheses for the
refusals: the archived dump is the 5.25" pressing and the
surviving patches target the 3.5" build, or an unarchived 1.01
revision is the expected base. Either way: **no combination of
publicly archived artifacts yields a floppy 1.10 install as of
2026-06-10.** SSI's original download site is gone (Wayback
archived the catalog page but every patch zip returns 410).

## 6. Patch-base recommendation

**Keep GOG CD 1.10 as the primary darkfix-ds2 target.**

1. **Reach.** Every GOG customer has exactly this base, and it
   is the only DS2 a player can legally buy today. A darkfix
   targeting floppy 1.10 would target an install that cannot
   currently be assembled from public artifacts (§5).
2. **Verifiability.** The existing
   `source-hashes/ds2-gog-1.10.toml` manifest pins it, and §3
   shows the base itself is reconstructible from GOG's own
   shipped CD image plus an archived official patch. There is no
   provenance ambiguity.
3. **Portability comes mostly for free.** GPL-level fixes edit
   `GPLDATA.GFF`, which the two product lines share at equal
   patch levels (§2). If a verifiable floppy 1.10 surfaces
   later, GPL fixes very likely apply as-is; only `DSUN.EXE`
   binary fixes would need re-porting (different build, offsets
   do not transfer).

Secondary target, deferred: if a pristine floppy 1.10 install or
a working 1.0-to-1.10 path surfaces, add a
`ds2-floppy-1.10.toml` manifest and verify GPL-fix portability
against it. The manifest format already supports per-base
hashes, so this is additive. This would also serve players who
prefer the floppy experience (MIDI music, no CD audio stalls);
that preference is legitimate, it just cannot define the primary
base while the floppy 1.10 is unobtainable.

Open questions, for whoever picks this up:

- Which pressing is the IA floppy dump (5.25" vs 3.5")? Box
  scans or disk labels would settle it.
- Does a floppy 1.01 or a 5.25"-targeted 1.10 patch survive
  anywhere (BBS CD-ROM compilations like the Patches Scrolls
  CDs, SimTel mirrors, cover disks)?
- Is floppy-1.10 `GPLDATA.GFF` byte-identical to CD-1.10's
  (expected, unverifiable until a floppy 1.10 exists)?

## 7. Reproducing the evidence

Local artifacts live under `.games/archive-org/` (gitignored):
the IA floppy trees (`ds2-floppy-1.0/`, `hotu/`), the patch
packages (`dk11/`, `cd11/`, `patches-scrolls/`), and the
downloaded zips.

To look inside `game.gog`: it is a raw Mode 2/2352 image, which
`7z` and `iso-info` both refuse. Strip each 2352-byte sector to
its 2048 data bytes (offset 24: 12 sync + 4 header + 8
subheader) and the result is a plain ISO9660 image that `7z x`
extracts:

```python
SEC = 2352
data = open("game.gog", "rb").read()
with open("ds2-game.iso", "wb") as f:
    for i in range(len(data) // SEC):
        f.write(data[i*SEC + 24 : i*SEC + 24 + 2048])
```

To re-run an RTPatch: stage the target tree under a DOSBox
mount, put `PATCH.EXE` + `PATCH.RTP` next to it, and run
`PATCH.EXE C:\TARGETDIR > C:\LOG.TXT` (the directory argument is
accepted; output redirects capture the per-file log). RTPatch
verifies an old-file fingerprint before touching anything and
restores original file timestamps on success.
