# fix.ds1.serf-follow (BETA: UNTESTED, balance-class)

**Status**: beta, disabled by default (twice over: every beta fix
is off, and this one is balance-class so it stays toggle-only
after QA too), untested at runtime.

**Bug** (our triage 3.2(1a), docs/ds1-sweep-triage-2026-10-07.md):
the Fields of Draj serf escort (GPL 60) only follows the party
across the region-10 exit when within 14 cells; one further
behind stays behind without his orders and can re-run the whole
deal for a second obelisk gem (-1352).

**Cause and fix**: our triage concluded the persistent-guard
design needed chunk growth and parked it; Calvin Rodo found a
different design needing none - widen the follow-distance guard
from 14 to 127 cells, a one-byte immediate. The trade is
explicit: any distance counts as "following", which is the
balance decision the default-off toggle keeps in the player's
hands.

| Site | Kind | Change |
|---|---|---|
| GPL-60@0xCD8 | same-length | `RANGE(gname[37], -259) < 14` -> `< 127` |

**Expected patched chunk**: GPL 60, unchanged length (4423), sha256
`7bcc4185d07d3eb96ef5268cde4e42005c7608ea23545811f6979c88db162f6c`.

**Credit**: Calvin Rodo, yuan-ti (`GplRepairs.cs`, MIT); the
finding and the alternative design are ours. QA: the packet,
docs/qa-packet-ds1-script-repairs-beta.md (site S).
