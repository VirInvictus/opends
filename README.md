<p align="center">
  <img src="logo.svg" alt="darkfix" width="360">
</p>

# darkfix

Community bugfix patches for SSI's Dark Sun CRPGs:

- `ds1-patch/` — *Dark Sun: Shattered Lands* (1993)
- `ds2-patch/` — *Dark Sun: Wake of the Ravager* (1994)

The first unofficial patches ever attempted for either game.

## Why

The original engine never shipped finished. *Wake of the Ravager* in
particular is famous for game-breaking bugs that even SSI's 1.02/1.10
patches did not fully resolve. The GOG releases ship the original DOS
binaries inside DOSBox — there is no fan patch and no public
reimplementation that plays end-to-end.

This project takes the patches-first route:

- **Data patches** to the game's `.GFF` files (quest scripts,
  region data, item flags) — applied with `gff-tool` from the
  `dsun_music` project.
- **Binary patches** to `DSUN.EXE` — surgical fixes for bugs that
  live in the engine itself (combat AI, sprite culling, save/exit).
- **Distributed as scripts** that apply edits to a player's GOG
  install. The game still launches via DOSBox; the bugs they hit,
  they don't.

What you give up vs a from-scratch reimplementation: native Linux,
arbitrary resolution, modern UI. What you gain: a finished thing,
realistically, this year.

## Long-term aspiration

A from-scratch open-source engine ("OpenDS") remains the dream. The
patch work directly feeds into it — disassembling GPL bytecode to
fix quest bugs is the same work an eventual GPL VM would need.
For now the focus is patches; engine deferred.

## Status

Day zero. Documentation phase. See:

- [`spec.md`](spec.md) — design spec and invariants
- [`roadmap.md`](roadmap.md) — phased plan
- [`docs/`](docs/) — engine research, file formats, known bugs, build setup
- [`ds1-patch/`](ds1-patch/) and [`ds2-patch/`](ds2-patch/) — per-game patch sources

## Quick start (developer)

You need a legitimate copy of one or both games (GOG installers
recommended). Place the GOG `.exe` installers under `.games/`
(gitignored) and run the extraction script (forthcoming) to populate
`extracted/<ds1|ds2>/`. See [`docs/build-environment.md`](docs/build-environment.md).

## License

TBD. Patches and tooling will be open-source. Game data files are
not redistributed and remain the property of Wizards of the Coast /
the original copyright holders.

## Credits

Standing on the shoulders of:

- **paulofthewest** and the [dsoageofheroes](https://github.com/dsoageofheroes)
  organization (`libgff`, `soloscuro`) — primary GFF reverse-engineering.
- **John Glassmyer** ([dsun_music](https://github.com/JohnGlassmyer/dsun_music))
  — the GFF editor that makes data-patches feasible at all.
- **Greg Kennedy** ([DarkSunOnline](https://github.com/greg-kennedy/DarkSunOnline))
  — DSO protocol RE; the v1.0 client's debug symbols cross-reference WotR
  internals.

See [`docs/upstream-projects.md`](docs/upstream-projects.md) for the
full upstream catalog.
