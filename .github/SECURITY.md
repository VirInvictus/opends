# Security policy

## Supported artifacts

Only the latest tagged release of each artifact is supported: the
`darkfix-dsN` player zips and the tools under `tools/` (each with
its own `VERSION`, per `docs/versioning.md`). Older releases get
no backported fixes; the fix is the next tag.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting: the **Security** tab
of this repository, then "Report a vulnerability". That keeps the
report private until a fix ships. Please do not open a public
issue for anything that describes how to corrupt a player's
install, sneak a hostile patch manifest past the applier, or
defeat the refusals described below.

Include: the artifact and version (`darkfix-ds1 v0.1.0`,
`gpl-asm 0.9.1`, ...), the affected game and install variant
(GOG 1.10 unless you know otherwise), and what a hostile manifest,
zip, or fix script could do. You will get a response on best
effort timing; this is a volunteer project.

## Verifying a player zip

Every `darkfix-dsN-vX.Y.Z.zip` is built by `tools/build-release.sh`
with fixed zip-entry timestamps, so the bytes are deterministic:
rebuilding the same tag from a clean checkout is byte-identical.
The release workflow quotes the zip's sha256 in the release
notes. Verify your download against it:

```sh
sha256sum darkfix-ds1-v0.1.0.zip
```

If the hash does not match the release notes, do not run
`apply.py` from that zip.

## What the applier promises

The darkfix applier refuses to touch an install whose files do
not hash to the canonical values in `manifest.toml`; refuses any
edit whose original bytes do not match the fix's `bytes_old`
fingerprint; refuses edits that change file length; composes
refusals so two enabled fixes cannot share one target; and backs
up everything it writes to `darkfix-backup/` with a journal that
supports `--unapply`. Reports about ways around those guarantees
are exactly the reports we want above.
