# Engine Research

A compiled overview of what is publicly known about the Dark Sun engine.
Source for the high-level facts: open web reverse-engineering work
(libgff, soloscuro, dsun_music, DarkSunOnline), Wikipedia, the Crimson
Sands Gamasutra postmortem, and the SSI 1.02 README distributed with the
GOG copy of *Wake of the Ravager*.

This document is the elevator-pitch version. Format details live in
[`file-formats.md`](file-formats.md); known bugs live in
[`known-bugs.md`](known-bugs.md); upstream code is catalogued in
[`upstream-projects.md`](upstream-projects.md).

## 1. The engine, briefly

There is no widely-attested marketing or codename for the engine. Sources
refer to it simply as "the Dark Sun engine."

What it is **not**:

- **Not the Gold Box engine.** Wikipedia explicitly states that *Shattered
  Lands* "does not use SSI's older Gold Box engine." SSI moved away from
  Gold Box for Dark Sun.
- **Not the Eye of the Beholder engine.** Westwood's EOB engine is
  unrelated; ScummVM supports EOB but does not (yet) support Dark Sun.
- **Not Al-Qadim's engine.** *Al-Qadim: The Genie's Curse* (Cyberlore /
  SSI, 1994) is sometimes cited as a sibling but used a separate codebase
  written by Cyberlore (lead programmer Ken Grey).
- **Not Menzoberranzan's engine.** Menzoberranzan was DreamForge using a
  derivative of their *Ravenloft: Strahd's Possession* engine.

What it **is**:

- A custom SSI in-house DOS engine. Lead programmer of *Wake of the
  Ravager*: Robert W. Calfee.
- Reused exactly once: *Dark Sun Online: Crimson Sands* (1996) was
  explicitly built by adapting the WotR codebase to a peer-to-peer
  multiplayer client. The Gamasutra postmortem says the team "was tasked
  to take the DARK SUN II single-player code base and turn it into a
  large-scale multiplayer online game." That same postmortem reveals the
  engine's scripting language is called **GPL** ("Game Programming
  Language").

## 2. Implementation guess

No published statement of the language or DOS extender is available, but
the available evidence converges:

- **Era**: 1993 release for DS1, so DOS-protected-mode is plausible
  (DOS/4GW or HMI's Sound Operating System were the standard candidates).
  The Crimson Sands postmortem describes the conversion path as
  "DOS application communicating with Windows 3.1 TCP/IP stack; later
  ported to true Win32 application," strongly implying C as the source
  language.
- **Audio**: The Wake of the Ravager error code "MEL fatal error #: 26
  Trap #: 16 / DSP detect fail" reveals the audio layer is John Miles'
  AIL/Miles library (MEL = Miles 1.x driver loader). Confirmed
  independently by libgff's `GFF_DADV` chunk type comment: "AIL and .COM
  drivers (MEL version 1.x only)."
- **Graphics**: VGA Mode 13h, 320×200, 8-bit indexed. Storage is
  palettized 8-bit — confirmed by libgff's chunk catalog (`PAL`, `BMP`,
  `PORT`, `WALL`, `ICON`, `TILE`, `FONT`).

For OpenDS planning, treat the original as: DOS C with VGA Mode 13h
graphics, AIL/Miles audio, custom byte-coded scripting (GPL), with
DS1/DS2/DSO sharing the engine but each having distinct schemas for some
record types.

## 3. The lineage tree

```
Shattered Lands (1993, SSI) ──► Wake of the Ravager (1994, SSI)
                                      │
                                      ▼
                                Crimson Sands (1996, SSI; multiplayer adapt)
```

That is the entire family. No siblings.

Asset reuse from *Al-Qadim: The Genie's Curse* into Crimson Sands is
documented (sprites, sounds), but the engines are different.

## 4. What the GOG installers ship

Verified locally (extracted to `/home/bdkl/.gitrepos/opends/.games/...`
via `innoextract`):

### Shattered Lands

- `DSUN.EXE` (611 KB) — main executable.
- `SOUND_DS.EXE` (43 KB) — sound configurator.
- `MIDITSR.EXE`, `ULTRAMID.EXE`, `GRAVIS.EXE` — DOS TSR drivers for
  Roland MPU-401 and Gravis Ultrasound.
- `RESOURCE.GFF` (3.4 MB) — main resource bundle (UI, common art, etc.).
- `CINE.GFF` (3.1 MB) — cinematic frames and scripts.
- `GPLDATA.GFF` (1.4 MB) — compiled GPL bytecode and master index.
- `SEGOBJEX.GFF` (5.1 MB) — segmented object data (items, entities).
- `DARKRUN.GFF` (991 B) — runtime state stub.
- `RGN02.GFF` ... `RGN29.GFF`, `RGN0A.GFF` ... `RGN2D.GFF`, `RGNFF.GFF`
  — region (map) files. Names are hex IDs.
- `GM1.BNK`, `GM2.BNK` — Roland sound banks.
- `STDPATCH.AD` — AdLib FM patch table.
- `SSI1.INI`, `UM200.INI`, `UM206.INI`, `UM206A.INI` — config files.
- `DARKSUN.BAT`, `SOUND.BAT`, `SOUND.CFG` — launchers.

### Wake of the Ravager

- `DSUN.EXE` (634 KB) — main executable.
- `SOUND_DS.EXE` (205 KB) — much larger; bundles AIL drivers directly.
- `RESOURCE.GFF` (5.7 MB), `OBJEX.GFF` (6.8 MB), `GPLDATA.GFF` (2.2 MB).
- `RGN001.GFF`, `RGN03A.GFF` ... — region files (note the schema is
  three hex digits in DS2 vs two in DS1).
- `*.FLI` — five Autodesk Animator FLIC cinematics: `1.FLI` through
  `5.FLI`.
- `SOUND001.VOC`, `SOUND002.VOC`, ... and `SPCH50.VOC` ... `SPCH300.VOC`
  — digital sound effects and voiced speech.
- `game.gog` (109 MB) — CD-ROM image (Mode 2/2352 data track) mounted
  as a virtual CD by DOSBox.
- `MUSIC/Track02.ogg` ... `Track41.ogg` — 40 redbook audio tracks
  re-encoded by GOG. The original CD shipped these as redbook audio;
  there is no MIDI music for DS2 (per the SSI 1.02 README:
  "Since there is no MIDI music (just off the CD)…").
- `PATCH.EXE`, `PATCH.RTP` — RTPatch binary patcher leftovers.
- `CHARTRAN.EXE` — character transfer tool from DS1 saves to DS2.
- `SVIEW.EXE` — slideshow / FLI viewer utility.
- `README.TXT` — official 1.02 patchnotes (preserved in
  [`known-bugs.md`](known-bugs.md)).

### GFF magic

All GFFs verified to start with `GFFI\0\0\x03\0\x1c\0\0\0` — magic
"GFFI", version 3, header size 0x1C (28 bytes). The next 4 bytes are
the offset to the table of contents. Identical magic across DS1, DS2,
and (per other sources) DSO.

## 5. The darkfix opportunity

WotR shipped buggy in 1994; SSI's 1.02 and 1.10 patches reduced but
did not eliminate the problems. **No public unofficial community
patch has ever existed for either Dark Sun game.** GOG ships the
1.10 binary inside DOSBox. This means:

- The state of the art for "play Wake of the Ravager today" is
  identical to the state of the art in 1995 modulo DOSBox
  conveniences.
- The first community patch will, by definition, be the most
  reliable way to play the late game.

That is the project's pitch in one sentence: **darkfix ships the
version of *Wake of the Ravager* that should have shipped.**

A from-scratch open-source engine ("OpenDS") remains the long-term
aspiration; the patch work is the route that gets there. See
[`../spec.md`](../spec.md) §12.

## 6. Sources

Primary research, with URLs:

- libgff and family — https://github.com/dsoageofheroes
- John Glassmyer's `dsun_music` — https://github.com/JohnGlassmyer/dsun_music
- Greg Kennedy's `DarkSunOnline` — https://github.com/greg-kennedy/DarkSunOnline
- Crimson Sands postmortem — https://www.gamedeveloper.com/design/postmortem-ssi-s-i-dark-sun-online-crimson-sands-i-
- Wikipedia: *Dark Sun: Shattered Lands* — https://en.wikipedia.org/wiki/Dark_Sun:_Shattered_Lands
- Wikipedia: *Dark Sun: Wake of the Ravager* — https://en.wikipedia.org/wiki/Dark_Sun:_Wake_of_the_Ravager
- Wikipedia: *Dark Sun Online: Crimson Sands* — https://en.wikipedia.org/wiki/Dark_Sun_Online:_Crimson_Sands
- Wikipedia: Miles Sound System — https://en.wikipedia.org/wiki/Miles_Sound_System
- VGMPF: Audio Interface Library — https://www.vgmpf.com/Wiki/index.php/Audio_Interface_Library
- VOGONS: WotR DSP issues — https://www.vogons.org/viewtopic.php?t=10893
- Athas community RE thread — https://arena.athas.org/t/reviving-dark-sun-online/1901
- GOG product database — https://www.gogdb.org/product/1432723859 (DS1),
  https://www.gogdb.org/product/1432903719 (DS2)
- DOSBox compat list — https://www.dosbox.com/comp_list.php?showID=148&letter=D
- Patches Scrolls (WotR 1.10) — https://www.patches-scrolls.de/patch/1112/7/22585
- Internet Archive: WAKEDK11_ZIP — https://archive.org/details/WAKEDK11_ZIP
- Internet Archive: WAKECD11_ZIP — https://archive.org/details/WAKECD11_ZIP
- CRPG Addict on DS1 — http://crpgaddict.blogspot.com/2021/10/game-434-dark-sun-shattered-lands-1993.html
