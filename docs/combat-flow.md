# The native combat loop: entry, rounds, resolution, death, XP

The combat state machine of both engines, read to pseudocode level
(port-mining wave 1, 2026-09-19). Module ownership, runtime state, entry,
round structure, attack resolution, damage/death, saves and special attacks,
victory/XP/loot, morale, and the explicit boundary of what cannot be
settled statically. The rules TABLES this flow consumes are decoded in
rules-tables.md. Verified on the GOG 1.10 corpus.

Addresses are file offsets unless marked overlay-local. DS1 =
`.games/ds1/DSUN.EXE`, DS2 = `.games/ds2/DSUN.EXE` ("DS2.EXE" in older
docs). Far calls with small segment words (DS1 `0x4e0:*`, `0x530:*`,
`0x4e8:*`, `0x600:*`; DS2 `0x570:*`, `0x630:*`, `0x618:*`, `0x628:*`) are
"module frame" references: their segment words are segtab byte-offsets /
pool-frame constants (see overlay-formats.md section 6 for resolution and
its open caveat).

## 1. Module map

| Role | DS1 | DS2 |
|---|---|---|
| GPL opcode 0x35 fight handler (resident VM code) | 0xacfb | 0xd70c |
| GPL opcode 0x36 flee handler | 0xad27 | 0xd72d |
| Combat driver overlay (entry gate, placement orders, teardown) | ovr22 (0x6a3b0..0x6bb96), 49 stubs | ovr19 (0x72ea0..0x747e6), 49 stubs, order-identical |
| Combat resolution library (round init, AI, resolver, damage, death, XP) | ovr5 (0x56cc0..0x5a031), 43 stubs | ovr4 (0x5a920..0x5ea7c), same 43 + 3 extra |
| Combatant placement (writes the position table) | ovr21: 0x69446, 0x6970c | ovr18: 0x70f22, 0x711d4 |
| MONR random-encounter selection | ovr38 local 0xcb4 (file 0x80bc4) | ovr35 (~0x8d32e pushes) |
| Resident combat executors (attack/AI glue) | 0x9a00..0xd663, 0x1ae40..0x26cd6 | 0xd100..0xf900, 0x1e000..0x2b000 |

The ovr5/ovr22 and ovr4/ovr19 stub tables are position-by-position twins.

## 2. Runtime state

(The "segment" values below are segtab data records reached via frame
constants; see overlay-formats.md 6. Records: GSTATE = rec87 (DS1) / 92
(DS2), MISC = rec88/93, CSTATE2 = rec92/97, STATE = rec108/113. Wave 2
correction: STATE holds 320 stride-3 entries, not 48; the combat loops
that walk it use the 48-slot range.)

- GSTATE = 0x2b8 (DS1) / 0x2e0 (DS2): +0x19 word = combat-active flag.
- MISC = 0x2c0 (DS1) / 0x2e8 (DS2): +0x35b dword = round counter (+60 per
  round), +0x357 treasure tally, +0x369 current leader (DS1).
- STATE = 0x360 (DS1) / 0x388 (DS2): slot table at +0xc36 (DS1) / +0xc33
  (DS2), 320 slots x 3 bytes {type:u8, combat_idx:u16} (wave 2
  correction; the combat drivers walk 48, kick1 scans all 320); type 0
  empty, 1 party-out-of-combat, 2 active combatant; +0x333 = per-
  object-id status shadow.
- CSTATE2 = 0x2e0 (DS1) / 0x308 (DS2), per-combatant scratch indexed by
  combat idx (DS2 cells all +3 vs DS1): +0x5b last-attack-direction,
  +0x85 AI state, +0xaf hit flag, +0x181 attacks-made tally (cap 99),
  +0x1ab attacks budget, +0xd9/+0xdb (DS2 +0xdc/+0xde) morale threshold +
  pre-rolled d200 (word, stride 4), +0x1d5 (DS2 +0x1d8) current-target
  word (0x3ff = none; bit 0x200 = "use special attack"), +0x22b (DS2
  +0x22e) movement points. Death queue: [0x4] count (max 42), entries at
  [0x7 + 2n].
- Position table (DGROUP, 32-byte stride): DS1 0x669d/0x669f pixel words
  (>>4 = tile); DS2 0x67c5/0x67c7.
- DGROUP far pointers (written by ovr22/ovr19 init entry 0): [0x165d]
  (DS1) / [0x19c1] (DS2) item-instance list (400 x 21/23 B), [0x1661]/
  [0x19c5] charrec array (stride 0x47/0x42), [0x1665]/[0x19c9] combat
  array (42 x 58B DS1 / 49B DS2), [0x1669]/[0x19cd] ITR1 item templates
  (20B DS1 / 15B DS2; +0xb blows(missile), +0xc sides, +0xd dice, +0xe
  bonus, +2 damage word).

## 3. Combat entry and encounters

```
GPL fight (opcode 0x35), DS1 0xacfb / DS2 0xd70c:
  push [VMCFG+0x1d], [VMCFG+0x1b]        ; the tile words Getxy wrote
  call stub 0x6b -> fight_enter          ; DS1 ovr22 local 0x30b (0x6a6bb) / DS2 ovr19 local 0x4a0 (0x73340)

fight_enter(x, y):
  DS2 only: call UI(1)                   ; 0x73345 mode switch
  if GSTATE[0x19] != 0: return           ; already in combat
  if !gate(): return                     ; 0x4e0:0xac -> ovr5 stub 28 (0x594df): the section 8 victory/defeat poll, reused as the entry gate
  GSTATE[0x19] = 1
  DS1: kick1(x, y)                       ; 0x4e0:0xe3 -> ovr5 stub 39 (0x59c79): first hostile with dist <= 24 AND line of sight
       kick2(slot)                       ; 0x530:0x9d -> ovr15 stub 25 (0x62f2a): the COMBAT MUSIC starter (per-slot bank byte off the active-music table)
```

Out-of-combat scripted damage goes through the resolver directly: DS1 ovr5
local 0x13b4 (file 0x58074) picks a default victim when GSTATE[0x19] == 0.

Encounter sources:

- Script triggers: GPL fight and attacktrigger-registered scripts.
- MONR random encounters (DS1 ovr38 local 0xcb4, file 0x80bc4): loads MONR
  chunk 1, count = size/0x2a (42-byte records); per record walks three
  4-byte candidate slots (rec+si*4+{2,4}, si 0..2), rolls d10
  (RNG*10/32768), keeps the candidate nearest a key; group count =
  clamp(party_metric*2 / rec_field, 1, 6) (0x80da2): spawn size is
  party-strength-scaled AT SPAWN TIME (matches the known-bug note that
  difficulty only affects not-yet-spawned creatures).

Placement (DS1 ovr21 ~0x69380..0x69480): party members from per-member
formation offsets, written to the position table as pixels, sprites placed
via 0xb8:0x909. Monsters (slots >= 5) must pass a target scan
(`enumerate(y, x, 0x180001, list, 0) > 0`, ovr5 local 0x7ca): a monster
with no visible party-side target is SKIPPED FOR THE ROUND (the mechanical
root of the "enemies refuse to engage" bug family).

No surprise-roll site exists in the modules read. The only first-round
special case is the one-shot flag [0x55a] (DS1) / [0x54e] (DS2): when set,
round-init skips clock/effect advance. The nearest "ambush" mechanic is
directional (section 5).

## 4. Round structure and initiative

Round init (DS1 ovr5 local 0x754, file 0x57414; DS2 ovr4 local 0xc65, file
0x5b585):

```
if [0x55a]!=0: [0x55a]=0                   ; first round: no clock advance
else:
  MISC[0x35b] += 60                        ; round counter (dword)
  clock(); per_round_effects() x2          ; poison/durations (0x5a8:0x3e / 0x5a8:0x39)
for slot in 0..0x2f where STATE[slot].type == 2:
  ci = STATE[slot].combat_idx
  if combat[ci].status(+0x1c) != 1: morale=-1; movepts=0; continue
  if slot >= 5 and enumerate(...,0x180001,...) <= 0: continue   ; needs a target
  if combat[ci].allegiance & 3 == 0: continue                   ; NEUTRALS (4) never act
  CSTATE2[ci*4+0xd9] = 20 (DS1) / 30 (DS2) + dex_reaction(slot) + status_flags(slot)
      ; dex_reaction = 0x508:0x66 = ovr10 stub 14 (0x5ea5f): the rules-tables DEX missile table
      ; status_flags  = 0x5b8:0xe8 = ovr32 stub 40 (0x7c3b1): -2/+2 per active-effect flag bits (DS2's twin at ovr28 stub 13 is richer, incl. a +40 category)
  CSTATE2[ci*4+0xdb] = d200()              ; r*200/32768 (DS2: one branch pins 200)
  CSTATE2[ci*2+0x22b] = combat[ci].move(+27/+19) * 10; haste/slow adjust
  reset +0x85, +0x5b, target=0x3ff, +0x181=0, +0x1ab=0, +0xaf
```

THERE IS NO PER-ROUND INITIATIVE LIST. Ordering is:

1. Probabilistic act test per animation tick (ovr22 local 0x67d, file
   0x6aa2d): `roll = RNG()*20/32768` (0..19, no +1); roll == 19 never acts;
   `val = (s8)combat[ci + 0x22 + prio_sel]` (the combat+34 PRIORITY byte;
   the docs' {5,6,7}) plus a per-actor modifier `[0x358:other + 4]`; acts
   when `val + modifier > roll`. Higher priority = acts more often.
2. AI actor selection (ovr5 local 0x9b6, file 0x57676): next monster actor
   = max morale threshold, tie-broken by the pre-rolled d200; guards on
   combat_active(); skips actors with no target; probes spell/psionic AI
   (CORRECTED by wave 2: the 0x88:0x34b6 site is an animation/sprite
   driver, not a spell probe; DS2's real AI spell rating is the all-320
   loop in ovr4 local 0x3540..0x3687, gated by combat+33 & 0x20; DS1's
   twin not pinned).

Attacks per round: the resolver loops the per-round attack budget
(+0x1ab); blow counts come from charrec+0x2a (melee) or ITR1[tpl+0xb]
(missile), HALVED WITH ROUND PARITY: `blows = (stored + ((MISC[0x35b]/60)
& 1)) / 2` (ovr5 0x1c85..0x1cb1), the "3 attacks per 2 rounds"
alternator. The +0x181 tally caps at 99 and grants an extra attack step
(0x178e..0x17ba).

## 5. Attack resolution

Resolver: DS1 ovr5 local 0x1359 (file 0x58019; THAC0 read 0x58113,
combat+31); DS2 ovr4 local 0x1cc1 (file 0x5c5e1; THAC0 0x5c6e9, combat+22,
stride 0x31).

```
resolve_attack(...):
  resolve_actor(...) -> attacker_ci, charrec_row      ; 0xa0:0x32ef charm/mirror redirect
  if out of combat: pick default victim; seed target cell
  loop attack budget: attack_slot = next_attack_slot(...)  ; local 0x234a; weapon selection
        (local 0x252: best ready weapon, sched +2==1, weapon-class filter, flags&3)
  THAC0 = (s8)combat[attacker+31]
  armed:    item = sched[slot*10+4]; tpl = item[+0xa]
            bonus = enchant(item[+0x14]) + weapon_special(item,tpl) + strength_bonus   ; local 0x292c
            backstab mode gate (local 0x1fcf)
  unarmed:  dmg_word = 8 for PC races (charrec+0x18 in 1..8); else (HD-2)/2 from charrec+0x24
  enchant 1/2/3+ sets bits 0x1000/0x2000/0x8000 in the attack word
  dir = (distance(attacker,target) + 4) mod 8; combat[attacker+0x38] = dir
  if CSTATE2[target+0x5b] == dir:                      ; struck from the same direction before
     THAC0 -= 2                                        ; flank/rear bonus
     if attacker legal_class & 0x400 (thief) and mode==1 and ITR1[tpl+4] <= 40:
        THAC0 -= 2; backstab = 1
  else: CSTATE2[target+0x5b] = dir
  target_AC = compute_AC(target)                       ; local 0x2113: base 10; out-of-combat PC = 5;
                                                       ; combatant = charrec base_AC(+0x27) + equipment walk
  apply_hit(sched, THAC0 - hit_adjustments(mode,sched,atk,tgt) [0x5b8:0xed], AC, ...)
```

apply_hit = ovr5 local 0x1b7a (file 0x5873a):

```
  blows = mode>1 ? ITR1[tpl+0xb] : charrec[row+0x2a]; blows = (blows + round_parity)/2
  dice/sides/bonus from ITR1[tpl+0xd/0xc/0xe] + item + weapon_special
  crit-adjust: crit()==4 -> blows*2 ; crit()==1 -> blows/2
  per blow:
     d20 = RNG()*20/32768 + 1
     nat 20 -> hit (crit path); nat 1 -> miss + sound 7
     needed = THAC0_eff - target_AC; miss if needed > d20      ; classic d20 >= THAC0-AC
     hit: dmg = roll_dice(dice, sides, bonus) (local 0x1f92); difficulty_adjust if mode<=1
          backstab: dmg *= (thieflevel-1)/4 + 2, cap 5 (local 0x2904)
          apply_damage(target, dmg*2 passed via 0x5b8:0x20)    ; arg shl 1 at 0x1e50, halved inside: display parity
          mirror-image: if retargeted and mode==1 and 25% check (0x598:0x20): redirect
  weapon effect id item[+0xf] -> status applier 0x598:0x89; charges 0x580:0xde
  tally +0x181 per blow; at >= 99 an extra attack step
```

Monster attackers (si >= 4) add `[0x11ae]-1` to the damage bonus (0x16b7).

## 6. Saving throws, special attacks, spells in combat

- Saves: the five bytes are charrec+0x37..0x3b (DS1) / +0x31..0x35 (DS2,
  stride 0x42). RESOLVED by wave 2 (spell-effects.md 4): the in-combat
  spell/effect save is DS1 ovr32 stub3 (0x79a71): gate on the savable
  bit, save_type -> column, save number = charrec[row + 0x36 + idx], 1d20
  (nat 1 fails, nat 20 saves), `special & 0x86` doubles the roll as a
  penalty, plus the situational modifier and the signed save_mod nibble;
  saves when total >= number. The RDFF-keyed chains: DS1 ovr22 local
  0xa44 (file 0x6adf4), DS2 ovr19 local 0xc00 (file 0x73aa0), both
  defaulting the save number from the charrec DESCRIPTOR byte (DS1 +0x3d
  / DS2 +0x37; object-formats.md labels it "size") + a status modifier.
  The five stored save bytes have NO reader in normal play (write-only
  outside level-up). Threshold tables: rules-tables.md.
- Special attacks (DS1 33-value enum, combat+22 read as a word with +23;
  DS2 combat+14 low byte): identical dispatch shape. AI action selection
  (DS1 ovr5 ~0xe70-0xf22): if target word & 0x200 (armed), global
  suppressor [0x4946]/[0x420c] != 1, and the enum field != 0: probe
  (module-frame 0x4e8:0x48 DS1 / 0x570:0x48 DS2), clear target
  bookkeeping, action_kind = 2, execute. DS2 additionally passes the enum
  to 0x630:0x20(enum, 0) (ovr4 0x15dd, file 0x5bafd) for the per-enum
  parameter record. The per-enum execution BODIES are behind the frame
  wall.
- Spells: the AI probes casting x3 via 0x88:0x34b6 (gated by combat+33 &
  0x20); spell/missile damage reuses the ovr4/ovr5 dice machinery (DS2
  ovr4 0x25cd..0x2672, rolls via 0x628:0x34, crit==4 doubles). The cast
  action itself lives in the spell overlay (wave 2 lane).

## 7. Damage application and death

apply_damage = ovr5 local 0x18da (file 0x5859a); the call site passes
damage DOUBLED (shl ax,1) and the body halves it (display parity).

```
type-2 combatant:
  amount >= hp + 10  -> status = 8 if amount >= 10000 (annihilated) else 5 (dead); hp = 0
  amount >= hp       -> status = 3 (dying); hp = 0
  else               -> hp -= amount
  |object id| < 0x33: STATE[id + 0x333] = status       ; script-visible death shadow
  if status > 2: clear own targeting; append to DEATH QUEUE (max 42);
     clear other attackers' target cells; award_monster_xp(ci)
type-1 (out-of-combat party): template-toughness check; can enqueue death
```

HP never goes negative: floor 0, with the hp+10 instant-death band encoded
as status. Death queue drained by ovr5 local 0x1ae1 (file 0x5883a; called
from resident 0x1b7cd): per entry plays the death effect (0x600:0x3e,
module-frame), then the party-death path if out of combat.

## 8. Victory, XP, loot, teardown

Victory/defeat poll = ovr5 local 0x281f (file 0x594df), the AI driver's
loop guard: combat continues while a hostile has been seen (enumerate
0x180002) and party_alive > 0 (slots < 4, status < 3) or the leader's
allegiance has bit 4.

XP award = ovr5 local 0x25f2 (file 0x592b2); DS2 ovr4 local 0x30c7 (file
0x5d7e7):

```
award_monster_xp(ci):
  DS1: if allegiance != 2 (hostile): return
  DS2: if ((1 << allegiance(+0x15)) & 0xf80) == 0: return   ; allegiances 7..11 award
  each = charrec[char_index + 4] (dword) / party_count()     ; DS1 idiv / DS2 unsigned
  award to the four fixed party slots
```

The per-monster XP source is the CHARREC DWORD AT +4 (not +0, which this
path never reads); object-formats.md's +0 "XP value" reading needs a
re-pin for monster rows. DS2 also tracks last-hitter/chain in
CSTATE2[0x2]/[0x0] (ovr4 0x2f1b).

Loot: no drop-to-ground site inside the combat modules; corpse/loot
creation rides the death-effect module (0x600:0x3e) and the placement
overlay. Pickup narration: DS1 ovr26 file 0x73a78 ("YOU FIND %u$", value
to MISC[0x357]) and "%Fs GETS ITEM" at 0x73e9c. The death-then-search
split matches the DS1 known bug "bodies vanish on map reload".

Teardown = ovr22 local 0xb65 (file 0x6af15; DS2 twin ovr19 local 0x172c,
file 0x745cc): GSTATE[0x19] = 0, restore UI/music ids, clear STATE arrays
(far-memset of the slot table), per-slot 0xff resets, destroy objects
0x30..0x207, return to exploration. All GSTATE:0x19 writers: DS1 set
0x5857e / 0x6a6e2 / 0x75597, clear 0x6af2f / 0x77fd2 / 0x1a878; DS2 set
0x5cbd7 / 0x7336f / 0x7e823, clear 0x73bb3 / 0x8162b / 0x1ce55.

## 9. Morale / fleeing

Morale is pre-computed per round (threshold = 20 DS1 / 30 DS2 + two
module-frame modifier services; d200 pre-rolled beside it; 0xffff removes
the actor from scheduling). The scheduler consumes exactly these two cells
(0xa0c..0xa65 DS1): max threshold, tie max roll. Morale ORDERS TURNS and
GATES PARTICIPATION. The explicit morale-failure -> flee transition was
not found in statically readable bodies (frame wall). GPL flee (opcode
0x36) merely enqueues a party movement order (kind 1).

## 10. DS1 vs DS2 differences

1. Combat-record stride 58 vs 49; THAC0 at +31 vs +22; special-attack word
   at +22 vs +14 (DS2 passes only the low byte to the enum service).
2. CSTATE2 cells shifted +3 in DS2 (0x5b -> 0x5e ... 0x22b -> 0x22e;
   target word 0x1d5 -> 0x1d8).
3. Morale base 20 -> 30; DS2 has a branch pinning the d200 cell to 200
   (auto-pass category; identity a runtime question).
4. XP gate: DS1 allegiance == 2; DS2 (1 << allegiance) & 0xf80. DS2
   divides unsigned, DS1 signed.
5. DS2 fight_enter adds an explicit UI-mode call before gating and DROPS
   the kick pair entirely (no combat-music starter in fight_enter; where
   DS2 starts combat music is open).
6. DS2 ovr4 has 3 extra exports (0x2f1b last-hitter among them) and its
   round-init resets CSTATE2[0x6] = 0xff.
7. ovr4's damage path adds an item bonus at item[+0x16] (23-byte items)
   with no DS1 counterpart.

Everything else (gate structure, round-init skeleton, priority-roll
initiative, hit/damage flow, statuses 3/5/8, hp+10 band, death queue, XP
division, teardown) is structurally identical.

## 11. Wave-2 status of the former runtime-capture list

Wave 2 (spell-effects.md, overlay-formats.md 6) resolved most of this
list statically:

- RESOLVED: the module-frame mapping (the frame wall never existed; every
  constant is a segtab byte-offset). The gate = the section 8 poll reused;
  kick1 = first hostile within 24 tiles AND LOS; kick2 = the combat-music
  starter. The morale modifiers = DEX reaction + active-effect flags.
  party_count = the four fixed party slots. The round cadence = the
  two-phase divider at record 116 (byte 0 counts 0..9, wraps byte 1
  toward 60). The in-combat save comparison = spell-effects.md 4. The
  death effect = corpse-sprite scatter animation (random pieces over a
  rect, death module ovr41 stub 6). The enumerate "0x180001/0x180002"
  dwords are TWO WORD ARGS: allegiance mask (1 party / 2 hostile), range
  = 24 tiles, plus a separate LOS flag; monster scans pass LOS = 0 (the
  mechanical root of "enemies engage through walls").

Still open after wave 2:

1. The special-attack enum bodies beyond the probe: the enum-to-effect
   maps are decoded (spell-effects.md 5); full semantics of ~35 status
   bits remain.
2. The morale-failure -> flee transition.
3. The exact driver that steps the round/tick clocks (the divider is
   decoded; its interrupt/tick source is not).
4. Loot OBJECT creation inside the rec7 placement services (the corpse
   scatter is decoded; the item drops are not).
5. Whether STATE slots 48..319 are ever populated (kick1 scans 320).

## 12. Confident negatives

- No per-round initiative table or ordered turn list; no weapon-speed
  input to initiative.
- No surprise-round dice roll; only the one-shot first-round flag and the
  directional ambush bonus.
- The combat modules never read XP thresholds or level-up tables.
- Neutral combatants (allegiance & 3 == 0) never act; monsters with no
  0x180001 target are inert.
- HP floors at 0; the hp+10 band is status, not negative HP.
- The XP award path never reads charrec+0, only +4.
