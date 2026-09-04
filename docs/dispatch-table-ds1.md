# DS1 GPL dispatch table (machine-generated, 2026-09-04)

Resolved from the dispatch table at DGROUP:0xc0 (file `0x48a20`),
reached by the interpreter's `shl ax,1; call near [bx+0xc0]` at
file `0x99cb`. Handler file addresses assume code segment base
`0x7900` (paragraph `0x250`) — the ONLY candidate surviving the
tiny-vs-large-handler filter, with corroborating structure:
opcodes `0x01`-`0x08` map to consecutive 31-32-byte handlers (the
arithmetic family) and Getxy is displaced out-of-band (`0x8ee8`),
matching both DS2's table and DSO's independent handler order.
The 15 unknown bytes share the single default entry `0x264c`
(file `0x9f4c`): reserved and unimplemented in the DS1 engine,
as in DS2. See `../roadmap.md` Phase 5.6.1 and
`dispatch-table-ds2.md` for the DS2 half.

| opcode | mnemonic | handler (file) |
|---|---|---|
| `0x00` | Zero | `0x9ddd` |
| `0x01` | LongDivideEqual | `0x841c` |
| `0x02` | ByteDec | `0x8457` |
| `0x03` | WordDec | `0x8476` |
| `0x04` | LongDec | `0x8495` |
| `0x05` | ByteInc | `0x84b5` |
| `0x06` | WordInc | `0x84d4` |
| `0x07` | LongInc | `0x84f3` |
| `0x08` | Hunt | `0x8513` |
| `0x09` | Getxy | `0x8ee8` |
| `0x0a` | StringCopy | `0x8539` |
| `0x0b` | PDamage | `0x8566` |
| `0x0c` | Changemoney | `0x9dc4` |
| `0x0d` | Setvar | `0x9e10` |
| `0x0e` | ToggleAccum | `0x869c` |
| `0x0f` | Getstatus | `0x8ea3` |
| `0x10` | Getlos | `0x8724` |
| `0x11` | LongTimesEqual | `0x87db` |
| `0x12` | Jump | `0x8812` |
| `0x13` | LocalSub | `0x8835` |
| `0x14` | GlobalSub | `0x8849` |
| `0x15` | LocalRet | `0x8874` |
| `0x16` | LoadVariable | `0x8883` |
| `0x17` | Compare | `0x8895` |
| `0x18` | LoadAccum | `0x89c0` |
| `0x19` | GlobalRet | `0x89dd` |
| `0x1a` | Nextto | `0x8769` |
| `0x1b` | Inlostrigger | `0x8d95` |
| `0x1c` | Notinlostrigger | `0x8dd5` |
| `0x1d` | ClearLos | `0x8e15` |
| `0x1e` | Nametonum | `0x8f47` |
| `0x1f` | Numtoname | `0x8f68` |
| `0x20` | Bitsnoop | `0x86d3` |
| `0x21` | Award | `0x89ec` |
| `0x22` | Request | `0x8aa8` |
| `0x23` | SourceTrace | `0x8a83` |
| `0x24` | Shop | `0x8a92` |
| `0x25` | Clone | `0x8af1` |
| `0x26` | gpl default (unimplemented) | `0x9f4c` |
| `0x27` | Ifcompare | `0x88fd` |
| `0x28` | TraceVar | `0x8b4c` |
| `0x29` | Orelse | `0x8960` |
| `0x2a` | Clearpic | `0x8b5b` |
| `0x2b` | Continue | `0x8b6c` |
| `0x2c` | Log | `0x8b7d` |
| `0x2d` | Damage | `0x8578` |
| `0x2e` | SourceLineNum | `0x8b96` |
| `0x2f` | Drop | `0x8ba5` |
| `0x30` | Passtime | `0x8c98` |
| `0x31` | ExitGpl | `0x8cae` |
| `0x32` | Fetch | `0x8cbe` |
| `0x33` | Search | `0x8ced` |
| `0x34` | Getparty | `0x8d68` |
| `0x35` | Fight | `0x8e2b` |
| `0x36` | Flee | `0x8e57` |
| `0x37` | Follow | `0x8e74` |
| `0x38` | Getyn | `0x8ec7` |
| `0x39` | Give | `0x8efe` |
| `0x3a` | Go | `0x8f89` |
| `0x3b` | InputBignum | `0x8fb8` |
| `0x3c` | Goxy | `0x8ff4` |
| `0x3d` | Readorders | `0x9028` |
| `0x3e` | If | `0x920b` |
| `0x3f` | Else | `0x9271` |
| `0x40` | Setrecord | `0x904e` |
| `0x41` | Setother | `0x9195` |
| `0x42` | InputString | `0x92aa` |
| `0x43` | InputNumber | `0x92e8` |
| `0x44` | InputMoney | `0x930d` |
| `0x45` | Joinparty | `0x9332` |
| `0x46` | Leaveparty | `0x9358` |
| `0x47` | Lockdoor | `0x937e` |
| `0x48` | Menu | `0x9395` |
| `0x49` | Setthing | `0x8d0a` |
| `0x4a` | gpl default (unimplemented) | `0x9f4c` |
| `0x4b` | LocalSubTrace | `0x8826` |
| `0x4c` | gpl default (unimplemented) | `0x9f4c` |
| `0x4d` | gpl default (unimplemented) | `0x9f4c` |
| `0x4e` | gpl default (unimplemented) | `0x9f4c` |
| `0x4f` | PrintString | `0x93a4` |
| `0x50` | PrintNumber | `0x93d3` |
| `0x51` | Printnl | `0x9402` |
| `0x52` | Rand | `0x9413` |
| `0x53` | gpl default (unimplemented) | `0x9f4c` |
| `0x54` | Showpic | `0x9455` |
| `0x55` | gpl default (unimplemented) | `0x9f4c` |
| `0x56` | gpl default (unimplemented) | `0x9f4c` |
| `0x57` | gpl default (unimplemented) | `0x9f4c` |
| `0x58` | Skillroll | `0x9497` |
| `0x59` | Statroll | `0x9543` |
| `0x5a` | StringCompare | `0x95ef` |
| `0x5b` | MatchString | `0x966c` |
| `0x5c` | Take | `0x96e9` |
| `0x5d` | Sound | `0x946b` |
| `0x5e` | Tport | `0x97ae` |
| `0x5f` | Music | `0x9481` |
| `0x60` | gpl default (unimplemented) | `0x9f4c` |
| `0x61` | Cmpend | `0x899b` |
| `0x62` | Wait | `0x98a6` |
| `0x63` | While | `0x98c3` |
| `0x64` | Wend | `0x98f1` |
| `0x65` | Attacktrigger | `0x9a76` |
| `0x66` | Looktrigger | `0x9aae` |
| `0x67` | Endif | `0x9905` |
| `0x68` | MoveTiletrigger | `0x992a` |
| `0x69` | DoorTiletrigger | `0x996f` |
| `0x6a` | MoveBoxtrigger | `0x99b4` |
| `0x6b` | DoorBoxtrigger | `0x99f9` |
| `0x6c` | PickupItemtrigger | `0x9a3e` |
| `0x6d` | Usetrigger | `0x9ae6` |
| `0x6e` | Talktotrigger | `0x9b1e` |
| `0x6f` | Noorderstrigger | `0x9b56` |
| `0x70` | Usewithtrigger | `0x9b8a` |
| `0x71` | gpl default (unimplemented) | `0x9f4c` |
| `0x72` | gpl default (unimplemented) | `0x9f4c` |
| `0x73` | gpl default (unimplemented) | `0x9f4c` |
| `0x74` | gpl default (unimplemented) | `0x9f4c` |
| `0x75` | gpl default (unimplemented) | `0x9f4c` |
| `0x76` | BytePlusEqual | `0x9bc2` |
| `0x77` | ByteMinusEqual | `0x9bf5` |
| `0x78` | ByteTimesEqual | `0x9c28` |
| `0x79` | ByteDivideEqual | `0x9c5f` |
| `0x7a` | WordPlusEqual | `0x9c9a` |
| `0x7b` | WordMinusEqual | `0x9ccd` |
| `0x7c` | WordTimesEqual | `0x9d00` |
| `0x7d` | WordDivideEqual | `0x9d37` |
| `0x7e` | LongPlusEqual | `0x9d72` |
| `0x7f` | LongMinusEqual | `0x9d9b` |
| `0x80` | GetRange | `0x87a2` |
