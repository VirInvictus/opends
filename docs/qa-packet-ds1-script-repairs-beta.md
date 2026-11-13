# QA packet: darkfix-ds1 v0.2.0-beta.1 script repairs

How to test the beta fixes and report what you see. Every check
below is a local scene: a save anywhere near the site, one or two
actions, one observable. Each site is a two-minute check once the
setup is done. You can test one site or all of them; every report
helps.

## Setup (five minutes, once)

1. **Back up your install folder.** The applier also keeps a
   `darkfix-backup/` copy inside the game folder and can revert
   everything, but an out-of-band copy is free insurance.
2. **DOSBox with an overlay mount.** The game must never write to
   the real install folder (the original engine zeroes
   `DARKRUN.GFF` on boot if it can write there). In your DOSBox
   config or on the command line, mount the install read-only and
   an empty folder as an overlay:

   ```
   mount c /path/to/install -readonly
   mount c /path/to/writable-overlay -t overlay
   ```

   (`tools/repro/` in this repo does this automatically with
   `python3 tools/repro/repro.py ds1-smoke --play`.)
3. **Sound on.** The game's MEL DSP detect fails without sound and
   some scenes misbehave.
4. **Get the beta zip** from the
   [release page](https://github.com/VirInvictus/opends/releases/tag/darkfix-ds1-v0.2.0-beta.1)
   (the zip is the release), unzip it, and apply with the default
   set (001 + 002, enabled, previously shipped):

   ```
   python3 apply.py /path/to/your-install-copy
   ```

5. **Enable the beta fixes you want to test**: edit
   `manifest.toml` in the zip folder, flip the ones you want from
   `enabled = false` to `enabled = true`, and run the apply again
   on a FRESH copy of your install (the applier refuses an
   already-patched file; `--unapply` first if you applied
   before). Verify with `python3 apply.py /path/to/install
   --verify`.

Run the game, make a save near each site (the game's own save
menu), and work through the checks.

## The checks

Shipped fixes (001 + 002, enabled by default in this beta):

- **D1. Darkhold wyvern (regions 30/31)**: approach the wyvern
  scene's creature and LOOK at it. Pass: the look text appears
  (unpatched: silence, the trigger is dead).
- **D2. Darkhold portcullis guard**: attack the portcullis guard
  (-255). Pass: it fights back (unpatched: it never registers an
  attack trigger).
- **D3. Darkhold queen's chamber**: look at the chamber creatures
  (-2263, -1209). Pass: look text for each.
- **D4. Lava Rifts ranger**: approach the ranger, leave, return,
  twice. Pass: the ranger's own scene plays once, no endless
  loop, no duplicate Iron Necklace in your inventory.
- **D5. Gedron, Linara**: deliver the extract, then talk to
  Linara again. Pass: her menu opens (unpatched: a one-line dead
  end), and Jasmine's spellbook topic is discussable.
- **D6. Final battle stages**: clear a stage of the final battle
  quickly (inside the inter-stage time window). Pass: the next
  stage still starts (unpatched: the battle strands).

Beta fixes (enable in the manifest, fresh install copy):

- **T. Tracking (fix.ds1.tracking)**: with a ranger (levels 13-16
  class code) in the party, go to the bodies on region 8's
  outskirts and use the tracking interaction. Pass: the roll can
  succeed and reads as a roll (roughly score-minus-chance);
  unpatched: it never succeeds no matter what.
- **G. Sewer grate (fix.ds1.grate-hack)**: in the slave pens,
  with a weapon in hand: (a) the grate's use menu offers "hack
  the lock off"; (b) a successful hack prints "<name>
  successfully hacks the lock off with his/her <weapon>. The
  grate opens." and the grate opens; (c) attacking the grate
  breaks the lock on a Strength-sized roll (sometimes fails),
  not always. Unpatched: (a) never offered, (b) never opens, (c)
  always breaks.
- **W. Rebel Mindhome (fix.ds1.mindhome-award)**: complete the
  spider task, then talk to the leader twice more. Pass: the
  +5000 XP award appears exactly once. Unpatched: every re-talk
  awards it again.
- **M. Region 9 messenger (fix.ds1.messenger-trigger)**: enter
  region 9, stay through the elves' departure (do NOT leave the
  region). Pass: the messenger arrives and his scene plays
  without a region re-entry. Unpatched: he only ever arrives if
  you re-enter the region after the elves leave.
- **S. Draj serf (fix.ds1.serf-follow, balance-class)**: during
  the Fields of Draj escort, walk far ahead (> 14 cells) before
  the region-10 exit and exit. Pass: the serf comes along and
  the obelisk gem is awarded once. Unpatched: he stays behind
  and a later re-talk can yield a second gem.
- **H. Halfling party member (fix.ds1.halfling-race)**: with a
  halfling in the party, talk to the slave pens' halfling
  (GPL 31). Pass: the greeting addresses a halfling as one, and
  the insult names the race. Unpatched: generic greeting, the
  insult names nothing.

Not in this beta: the six Legcrusher dialog guards (they need
tooling that is not built yet) and the re-ask half of the
Mindhome bug.

## Reporting

Open an issue at
[github.com/VirInvictus/opends/issues](https://github.com/VirInvictus/opends/issues)
titled `beta QA: <site letter(s)> <pass/fail>` with:

```
site(s):      D1..D6, T, G, W, M, S, H
result:       pass / fail per site
game version: GOG 1.10
fixes enabled: (which manifest entries)
what happened: one or two sentences per site, screenshots welcome
                 (DOSBox Ctrl+F5)
```

A FAIL is as useful as a PASS: say what you saw instead. Anything
unexpected (a crash, a wrong line, a scene that misbehaves
nowhere near a fix) is worth reporting even without a site
letter. Thanks: every report moves these fixes from beta to
default-on.
