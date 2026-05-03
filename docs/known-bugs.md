# Known Bugs

A catalog of the engine bugs we are committing to fix. Three sources:

1. **SSI's official 1.02 README** for *Wake of the Ravager*, preserved
   verbatim in section 1 below — that's twenty bugs SSI fixed between
   the 1.0 release and the 1.02 patch. We must not regress these.
2. **The 1.10 → present** residual bugs documented on Wikipedia, VOGONS,
   GOG forums, the DOSBox compatibility list, and the Steam community
   threads.
3. **Bugs we discover during reimplementation.** Add as we go.

## 1. SSI's official 1.02 fix list (Wake of the Ravager)

Reproduced from `extracted/ds2/README.TXT` shipped in the GOG installer.
The README is dated 1994-12-14 and accompanies the 1.10 build. Each
item below was a 1.02-era fix; they are all expected to remain fixed
in OpenDS:

1. The game should no longer lock up when resting in the Pyramid.
2. The secret door to Mind Flayer Underdark should allow players to
   move freely between it.
3. The chest in the Sorrows will no longer change a character into a
   chest when the trap goes off.
4. Charmed or Fear will no longer stay on a character after combat.
5. The party will no longer disappear when moving through the caves
   of the Yaunti.
6. When you talk to Snaggle and give him the Potion of Heroism, you
   will now get experience for returning the potion only once.
7. Tapestry will no longer trap the character in one region while
   moving through the mosaic regions.
8. The volcano regions now show the correct overhead maps when
   entering the south and north wings.
9. The game should no longer crash when talking to the Tyrian guard
   in Tyr.
10. The game locking up when transferring regions should be fixed.
11. Music playing for 1–2 seconds (combat only) then stopping for
    same amount of time should be fixed.
12. The prayer spell works correctly.
13. The game speed can now be changed by sliding the top bar in the
    preference screen.
14. Saving Magnolia for the second time will no longer teleport the
    party off the screen.
15. The Umber Hulks will no longer act strange in combat, they
    should attack the party.
16. At the end of the game, the Lord Warrior will give his speech
    and combat will begin.
17. Game shouldn't randomly crash in combat.
18. When the party fixes the chandelier, the quest should continue.
19. Ranger characters will know accumulate over 1,440,000 experience.
20. When the pendant is brought to Dariya, the game will not freeze.

These are all GPL-script-driven (mostly quest flag bugs, some animation
script bugs, some combat AI bugs). All of them ship pre-fixed inside
the GOG 1.10 binary; darkfix preserves them as the **baseline** and
must not regress them.

## 2. Bugs that survived 1.10 (documented community reports)

### 2.1. Mine elevator freeze

**Symptom**: in WotR, the mines elevator freezes the level-load screen,
blocking quest progression. Reproducible across save reloads.

**Current workaround**: dismiss all party members except one, ride the
elevator solo, re-hire below.

**Surface**: likely GPL (region-transition script) or DSUN.EXE
(transition state machine). Investigation needed.

**Status**: headline target for `darkfix-ds2-v0.1`. See
[`../roadmap.md`](../roadmap.md) Phase 4.

### 2.2. Doorway / item graphics disappearance

**Symptom**: graphics for doorways or items occasionally vanish as the
camera scrolls.

**Origin**: described as an engine limitation; appears to be a
sprite/tile layering or culling defect.

**Surface**: DSUN.EXE (renderer).

**Status**: deferred — the binary fix is more invasive than other
candidates. May be addressed in DS2 v0.5 sweep.

### 2.3. Charged-weapon disappearance

**Symptom**: weapons with charge counters (Beast Club, Life Stealer,
others) vanish from inventory after their charges are spent rather
than reverting to mundane state.

**Surface**: GPL (item-use callback) or DSUN.EXE (inventory render).
Try GPL first.

**Status**: candidate for DS2 v0.5 sweep.

### 2.4. "Saves but exits"

**Symptom**: in some configurations, the game terminates after saving;
the saved game is still loadable on next launch.

**Surface**: DSUN.EXE (save path) or DOSBox interaction (less likely
since the bug predates DOSBox).

**Status**: needs reproduction first; some reports may be DOSBox-config
rather than engine.

### 2.5. Audio static / "untuned radio" noise

**Symptom**: some 1994 CD pressings (and some DOSBox setups) emit static
during music playback.

**Origin**: AIL driver mismatch, not an engine bug per se.

**Status**: out of scope for darkfix. The GOG release ships
re-encoded OGG music tracks; static is unlikely to reproduce on a
standard install. We document for completeness.

### 2.6. MEL DSP detect fail (error #26, trap #16)

**Symptom**: WotR refuses to start. "MEL fatal error #: 26 Trap #: 16
DSP detect fail."

**Origin**: SoundBlaster IRQ misconfiguration. The original expects
IRQ 5; DOSBox defaults to IRQ 7.

**Status**: out of scope — it's a DOSBox config issue, not an engine
bug. The GOG release's bundled `.conf` already uses IRQ 5.

## 3. DS1 issues

*Shattered Lands* shipped in a "somewhat unfinished state" (Designers &
Dragons, Appelcline 2011) but received only one patch (1.10). The
community-reported issues are milder than DS2's:

- Occasional region-transition delay where the screen briefly blanks.
- A handful of combat-AI issues where enemies refuse to engage.
- Rare save-corruption around region edge tiles.

These are not as well documented as the DS2 list. We will catalog
them as we find them during reimplementation.

## 4. SSI patch lineage

| Game | Patch | Distribution                                  |
|------|-------|-----------------------------------------------|
| DS1  | 1.10  | Bundled in GOG release (the only DS1 patch)   |
| DS2  | 1.02  | Floppy and CD versions; Patches Scrolls       |
| DS2  | 1.10  | Floppy and CD; Internet Archive (WAKEDK11_ZIP, WAKECD11_ZIP); GOG ships this |

GOG ships the 1.10 binary inside DOSBox, with the 1.02 README preserved.
There is **no public unofficial community patch** for either game.

## 5. Patch policy in darkfix

Each fix:

1. Ships with a stable identifier (e.g. `fix.ds2.mines-elevator`).
2. Is **on by default** if it is a clear bug.
3. Is toggleable in the patch's `manifest.toml` for purists.
4. Is documented here with the original report and the fix rationale.

Bug fixes that change balance (e.g., XP exploits, item duplication)
are **off by default**, on by toggle. See [`../spec.md`](../spec.md) §5.

## 6. Sources

- `extracted/ds2/README.TXT` — SSI's verbatim 1.02 patchnotes.
- Wikipedia — https://en.wikipedia.org/wiki/Dark_Sun:_Wake_of_the_Ravager
- VOGONS thread — https://www.vogons.org/viewtopic.php?t=10893
- DOSBox compat list — https://www.dosbox.com/comp_list.php?showID=148&letter=D
- Internet Archive — https://archive.org/details/WAKEDK11_ZIP
- Internet Archive — https://archive.org/details/WAKECD11_ZIP
- Patches Scrolls — https://www.patches-scrolls.de/patch/1112/7/22585
