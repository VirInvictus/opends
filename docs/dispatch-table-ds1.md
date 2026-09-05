# DS1 GPL dispatch table (machine-generated, 2026-09-05)

Resolved from the dispatch table at DGROUP:0xc0 (file `0x48a20`),
reached by the interpreter's `shl ax,1; mov bx,ax; call near
[bx+0xc0]` at file `0x99c5` (the dispatch site has an intervening
`mov bx,ax` vs DS2's direct `mov bx,ax` pattern). Handler file
addresses use code segment base `0x97d0` (paragraph `0x43d`) —
**confirmed** by 783 MZ relocations carrying segment ordinal
0x43d, and by 129/129 entries landing on valid Borland function
entries (114 frameless stack-check, 11 overlay-marked frame,
4 stack-check + frame). The earlier base of 0x7900 in this file
was wrong (no reloc support; handlers landed mid-instruction).
The 15 unknown bytes share the single default entry `0x264c`
(file `0xbe1c`): reserved and unimplemented, same set as DS2.
See `../roadmap.md` Phase 5.6.1 and `dispatch-table-ds2.md`.

| opcode | mnemonic | handler (file) |
|---|---|---|
| `0x00` | Zero | `0xbcad` |
| `0x01` | LongDivideEqual | `0xa2ec` |
| `0x02` | ByteDec | `0xa327` |
| `0x03` | WordDec | `0xa346` |
| `0x04` | LongDec | `0xa365` |
| `0x05` | ByteInc | `0xa385` |
| `0x06` | WordInc | `0xa3a4` |
| `0x07` | LongInc | `0xa3c3` |
| `0x08` | Hunt | `0xa3e3` |
| `0x09` | Getxy | `0xadb8` |
| `0x0a` | StringCopy | `0xa409` |
| `0x0b` | PDamage | `0xa436` |
| `0x0c` | Changemoney | `0xbc94` |
| `0x0d` | Setvar | `0xbce0` |
| `0x0e` | ToggleAccum | `0xa56c` |
| `0x0f` | Getstatus | `0xad73` |
| `0x10` | Getlos | `0xa5f4` |
| `0x11` | LongTimesEqual | `0xa6ab` |
| `0x12` | Jump | `0xa6e2` |
| `0x13` | LocalSub | `0xa705` |
| `0x14` | GlobalSub | `0xa719` |
| `0x15` | LocalRet | `0xa744` |
| `0x16` | LoadVariable | `0xa753` |
| `0x17` | Compare | `0xa765` |
| `0x18` | LoadAccum | `0xa890` |
| `0x19` | GlobalRet | `0xa8ad` |
| `0x1a` | Nextto | `0xa639` |
| `0x1b` | Inlostrigger | `0xac65` |
| `0x1c` | Notinlostrigger | `0xaca5` |
| `0x1d` | ClearLos | `0xace5` |
| `0x1e` | Nametonum | `0xae17` |
| `0x1f` | Numtoname | `0xae38` |
| `0x20` | Bitsnoop | `0xa5a3` |
| `0x21` | Award | `0xa8bc` |
| `0x22` | Request | `0xa978` |
| `0x23` | SourceTrace | `0xa953` |
| `0x24` | Shop | `0xa962` |
| `0x25` | Clone | `0xa9c1` |
| `0x26` | gpl default (unimplemented) | `0xbe1c` |
| `0x27` | Ifcompare | `0xa7cd` |
| `0x28` | TraceVar | `0xaa1c` |
| `0x29` | Orelse | `0xa830` |
| `0x2a` | Clearpic | `0xaa2b` |
| `0x2b` | Continue | `0xaa3c` |
| `0x2c` | Log | `0xaa4d` |
| `0x2d` | Damage | `0xa448` |
| `0x2e` | SourceLineNum | `0xaa66` |
| `0x2f` | Drop | `0xaa75` |
| `0x30` | Passtime | `0xab68` |
| `0x31` | ExitGpl | `0xab7e` |
| `0x32` | Fetch | `0xab8e` |
| `0x33` | Search | `0xabbd` |
| `0x34` | Getparty | `0xac38` |
| `0x35` | Fight | `0xacfb` |
| `0x36` | Flee | `0xad27` |
| `0x37` | Follow | `0xad44` |
| `0x38` | Getyn | `0xad97` |
| `0x39` | Give | `0xadce` |
| `0x3a` | Go | `0xae59` |
| `0x3b` | InputBignum | `0xae88` |
| `0x3c` | Goxy | `0xaec4` |
| `0x3d` | Readorders | `0xaef8` |
| `0x3e` | If | `0xb0db` |
| `0x3f` | Else | `0xb141` |
| `0x40` | Setrecord | `0xaf1e` |
| `0x41` | Setother | `0xb065` |
| `0x42` | InputString | `0xb17a` |
| `0x43` | InputNumber | `0xb1b8` |
| `0x44` | InputMoney | `0xb1dd` |
| `0x45` | Joinparty | `0xb202` |
| `0x46` | Leaveparty | `0xb228` |
| `0x47` | Lockdoor | `0xb24e` |
| `0x48` | Menu | `0xb265` |
| `0x49` | Setthing | `0xabda` |
| `0x4a` | gpl default (unimplemented) | `0xbe1c` |
| `0x4b` | LocalSubTrace | `0xa6f6` |
| `0x4c` | gpl default (unimplemented) | `0xbe1c` |
| `0x4d` | gpl default (unimplemented) | `0xbe1c` |
| `0x4e` | gpl default (unimplemented) | `0xbe1c` |
| `0x4f` | PrintString | `0xb274` |
| `0x50` | PrintNumber | `0xb2a3` |
| `0x51` | Printnl | `0xb2d2` |
| `0x52` | Rand | `0xb2e3` |
| `0x53` | gpl default (unimplemented) | `0xbe1c` |
| `0x54` | Showpic | `0xb325` |
| `0x55` | gpl default (unimplemented) | `0xbe1c` |
| `0x56` | gpl default (unimplemented) | `0xbe1c` |
| `0x57` | gpl default (unimplemented) | `0xbe1c` |
| `0x58` | Skillroll | `0xb367` |
| `0x59` | Statroll | `0xb413` |
| `0x5a` | StringCompare | `0xb4bf` |
| `0x5b` | MatchString | `0xb53c` |
| `0x5c` | Take | `0xb5b9` |
| `0x5d` | Sound | `0xb33b` |
| `0x5e` | Tport | `0xb67e` |
| `0x5f` | Music | `0xb351` |
| `0x60` | gpl default (unimplemented) | `0xbe1c` |
| `0x61` | Cmpend | `0xa86b` |
| `0x62` | Wait | `0xb776` |
| `0x63` | While | `0xb793` |
| `0x64` | Wend | `0xb7c1` |
| `0x65` | Attacktrigger | `0xb946` |
| `0x66` | Looktrigger | `0xb97e` |
| `0x67` | Endif | `0xb7d5` |
| `0x68` | MoveTiletrigger | `0xb7fa` |
| `0x69` | DoorTiletrigger | `0xb83f` |
| `0x6a` | MoveBoxtrigger | `0xb884` |
| `0x6b` | DoorBoxtrigger | `0xb8c9` |
| `0x6c` | PickupItemtrigger | `0xb90e` |
| `0x6d` | Usetrigger | `0xb9b6` |
| `0x6e` | Talktotrigger | `0xb9ee` |
| `0x6f` | Noorderstrigger | `0xba26` |
| `0x70` | Usewithtrigger | `0xba5a` |
| `0x71` | gpl default (unimplemented) | `0xbe1c` |
| `0x72` | gpl default (unimplemented) | `0xbe1c` |
| `0x73` | gpl default (unimplemented) | `0xbe1c` |
| `0x74` | gpl default (unimplemented) | `0xbe1c` |
| `0x75` | gpl default (unimplemented) | `0xbe1c` |
| `0x76` | BytePlusEqual | `0xba92` |
| `0x77` | ByteMinusEqual | `0xbac5` |
| `0x78` | ByteTimesEqual | `0xbaf8` |
| `0x79` | ByteDivideEqual | `0xbb2f` |
| `0x7a` | WordPlusEqual | `0xbb6a` |
| `0x7b` | WordMinusEqual | `0xbb9d` |
| `0x7c` | WordTimesEqual | `0xbbd0` |
| `0x7d` | WordDivideEqual | `0xbc07` |
| `0x7e` | LongPlusEqual | `0xbc42` |
| `0x7f` | LongMinusEqual | `0xbc6b` |
| `0x80` | GetRange | `0xa672` |

Formula: `file = 0x5400 + 0x43d*16 + table[i]`.
