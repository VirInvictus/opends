# verify-install

Check a Dark Sun install against the canonical pristine-source
hash manifest. Reports matched, mismatched, missing, and extra
files. Used to confirm a player install is GOG 1.10 (and
unmodified) before applying a darkfix patch, and to capture the
canonical hash baseline from a fresh innoextract of the GOG
installer.

- **Language**: Python (stdlib only).
- **Requires**: Python 3.11+ (for `tomllib`).
- **Version**: see [`VERSION`](VERSION).
- **License**: MIT.

## Usage

### Verify (default mode)

```sh
# Verify the DS1 install at its default Wine GOG Games path.
python3 verify-install.py --game ds1

# Verify a custom path.
python3 verify-install.py --game ds2 --path /some/install

# List the extras and the runtime_state files that were skipped.
python3 verify-install.py --game ds1 --show-extras --show-skipped
```

### Capture (regenerate the canonical manifest)

```sh
python3 verify-install.py --game ds1 --capture \
    --path ../../.games/ds1 \
    --captured-from "innoextract of game-dark.sun.shattered.lands-(28043-gog).rar" \
    --ignore '__redist/**' --ignore '__support/**' \
    --ignore 'app/**' --ignore 'commonappdata/**' \
    --ignore 'tmp/**' --ignore 'DOSBOX/**' \
    -o ../../docs/source-hashes/ds1-gog-1.10.toml
```

The `[runtime_state]` block in the emitted file is a stub.
Hand-edit it to list the patterns covering files that exist in
a deployed install but are user-mutable (saves, configs, GOG
client state, DOSBox tuning).

## Exit codes

| Code | Meaning                                                  |
|------|----------------------------------------------------------|
| 0    | Install matches manifest cleanly.                        |
| 1    | One or more mismatched or missing files.                 |
| 2    | Configuration error (manifest not found, path bad).      |

## Manifest format (schema 1)

See `docs/source-hashes/<game>-gog-1.10.toml`. Three sections:

- `[meta]` — game, source, engine version, schema version.
- `[files]` — relative-path → SHA256 mapping. Verifier requires
  exact match unless overridden by `[runtime_state]`.
- `[runtime_state].patterns` — glob patterns (fnmatchcase) for
  files the verifier expects in a deployed install but whose
  contents are user-mutable. **A `[runtime_state]` pattern
  overrides a matching `[files]` entry**: an entry present in
  both is treated as runtime_state. This lets the manifest
  preserve the pristine hash of files like `SOUND.CFG` or
  `DARKRUN.GFF` while still skipping them in verify (the GOG
  installer or DOSBox writes to them post-install).

Files present in the install but in neither `[files]` nor
`[runtime_state]` are reported as **extras**. Extras are
informational and do not fail verification; pass `--show-extras`
to list them.
