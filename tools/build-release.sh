#!/usr/bin/env bash
# build-release.sh: assemble a darkfix player zip (spec.md section 4).
#
#   tools/build-release.sh <game> [version] [--out DIR]
#   tools/build-release.sh --selftest
#
#   game     ds1 or ds2; the dsN-patch/ directory must exist
#   version  optional; must match the patch's VERSION file (the
#            single source of truth per docs/versioning.md);
#            defaults to it
#   --out    output directory (default: scratch/releases/, gitignored)
#
# Writes darkfix-<game>-v<version>.zip holding the flattened tree
# spec.md section 4 defines, so the player can run
# `python3 apply.py <game folder>` from the unzipped root:
#
#   manifest.toml   VERSION   apply.py   README.md   LICENSE   darkfix/   fixes/
#
# Gates before anything is zipped, run against the staged tree:
# every manifest fix is loaded through the real contract checker
# (plus the same two-enabled-fixes-one-target refusal cmd_apply
# enforces, so a manifest the applier rejects can never ship), the
# tree byte-compiles, and the staged applier passes --selftest.
# Zip entries carry fixed timestamps, so rebuilding an unchanged
# tree yields a byte-identical zip. --selftest exercises the gate
# logic against a synthetic bad manifest (two enabled fixes on one
# target) and must refuse.

set -euo pipefail

usage() {
    sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'
}

# Gate 1 of the zip build: load every manifest fix (enabled or not;
# a player can flip any of them on) through apply.py's real contract
# checker, then replicate cmd_apply's composition refusal for the
# enabled set.
gate1_contracts() {
    python3 - "$1" <<'PY'
import importlib.util
import sys
from pathlib import Path

stage = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("staged_apply", stage / "apply.py")
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)
manifest = mod.P.load_manifest(stage / "manifest.toml")
targets = manifest["target"]["files"]
seen_targets = {}
for entry in manifest["fixes"]:
    fix = mod.load_fix_module(stage / entry["path"])
    target_rel = mod.check_fix_contract(fix, entry, targets)
    if entry.get("enabled", True):
        other = seen_targets.get(target_rel)
        if other is not None:
            sys.exit(
                f"gate 1: {fix.ID} and {other} both target {target_rel}:"
                " two enabled fixes cannot compose against one file;"
                " every player's apply would refuse this manifest"
                " (disable one of them in manifest.toml)"
            )
        seen_targets[target_rel] = fix.ID
    print(f"  contract OK: {entry['id']}")
PY
}

game=""
version=""
out=""
selftest=""
while [ $# -gt 0 ]; do
    case "$1" in
        --out)
            [ $# -ge 2 ] || { echo "build-release.sh: --out needs a directory" >&2; exit 2; }
            out="$2"; shift 2 ;;
        --selftest)
            selftest=1; shift ;;
        -h|--help)
            usage; exit 0 ;;
        -*)
            echo "build-release.sh: unknown option: $1" >&2; exit 2 ;;
        *)
            if [ -z "$game" ]; then game="$1"
            elif [ -z "$version" ]; then version="$1"
            else
                echo "build-release.sh: unexpected argument: $1" >&2
                exit 2
            fi
            shift ;;
    esac
done

root="$(cd "$(dirname "$0")/.." && pwd)"

if [ -n "$selftest" ]; then
    # Regression for the gate, not the zip: a manifest with two
    # enabled fixes on one target must be refused by gate 1, because
    # it is exactly the manifest every player's apply refuses at
    # check time. Runs against a synthetic tree; touches nothing.
    s="$(mktemp -d)"
    trap 'command rm -rf "$s"' EXIT
    mkdir -p "$s/patch/fixes"
    cp "$root/ds1-patch/scripts/apply.py" "$s/patch/"
    cp -R "$root/ds1-patch/scripts/darkfix" "$s/patch/darkfix"
    hash64="0000000000000000000000000000000000000000000000000000000000000000"
    for i in 0 1; do
        cat > "$s/patch/fixes/00$i-dup.py" <<EOF
"""Selftest fix."""
ID = "fix.selftest.dup.$i"
TARGET = "TEST.DAT"
SOURCE_SHA256 = "$hash64"
EDITS = []
def apply(source_path, dest_path):
    raise NotImplementedError
EOF
    done
    cat > "$s/patch/manifest.toml" <<EOF
[meta]
schema_version = 1
game = "ds1"
name = "selftest-dup"
license = "MIT"

[target]
source = "GOG"
engine_version = "1.10"

[target.files]

[[fixes]]
id = "fix.selftest.dup.0"
path = "fixes/000-dup.py"
enabled = true

[[fixes]]
id = "fix.selftest.dup.1"
path = "fixes/001-dup.py"
enabled = true
EOF
    if gate1_contracts "$s/patch" > /dev/null 2>&1; then
        echo "build-release.sh --selftest: FAIL: dup-target manifest passed gate 1" >&2
        exit 1
    fi
    echo "build-release.sh --selftest: PASS (dup-target manifest refused by gate 1)"
    exit 0
fi

[ -n "$game" ] || { usage >&2; exit 2; }
case "$game" in
    ds[0-9]) ;;
    *) echo "build-release.sh: game must be dsN (ds1, ds2), got: $game" >&2; exit 2 ;;
esac

patch_dir="$root/$game-patch"
[ -d "$patch_dir" ] || { echo "build-release.sh: no $game-patch/ directory" >&2; exit 2; }
# Friendly refusal while a patch has no applier (ds2 today): the
# alternative is a raw cp error after usage promised the game.
[ -f "$patch_dir/scripts/apply.py" ] || {
    echo "build-release.sh: $patch_dir has no applier yet (scripts/apply.py);" \
         "the release pipeline ships with that game's first fix" >&2
    exit 2
}

want="$(head -n 1 "$patch_dir/VERSION" | tr -d '[:space:]')"
[ -n "$want" ] || { echo "build-release.sh: $patch_dir/VERSION is empty" >&2; exit 2; }
if [ -n "$version" ] && [ "$version" != "$want" ]; then
    echo "build-release.sh: requested version $version does not match" \
         "$patch_dir/VERSION ($want); VERSION is the single source of truth" >&2
    exit 2
fi
version="$want"

stage="$(mktemp -d)"
trap 'command rm -rf "$stage"' EXIT

mkdir -p "$stage/fixes"
cp "$patch_dir/manifest.toml" "$patch_dir/VERSION" "$patch_dir/README.md" "$patch_dir/LICENSE" "$stage/"
cp "$patch_dir/scripts/apply.py" "$stage/"
cp -R "$patch_dir/scripts/darkfix" "$stage/darkfix"
# fixes/: scripts and writeups ship; caches and dir placeholders do not.
(cd "$patch_dir" && find fixes -type f \
    ! -path '*__pycache__*' ! -name '*.pyc' ! -name '.gitkeep' \
    -exec cp --parents {} "$stage/" \;)
find "$stage" -name '__pycache__' -type d -exec command rm -rf {} + 2>/dev/null || true

echo "staging $game-patch at $version:"

# Gate 1: the real contract checker plus the enabled-set
# composition refusal (see gate1_contracts).
gate1_contracts "$stage"

# Gate 2: the tree byte-compiles.
python3 -m compileall -q "$stage"

# Gate 3: the staged applier passes its own apply/verify/unapply
# selftest (synthetic cycle everywhere; the real-install cycles ride
# along when .games/ is present on the build machine).
python3 "$stage/apply.py" --selftest

# Gate 4: the direct CLI path finds its manifest in the flattened
# tree. --selftest always passes an explicit patch root, so without
# this a layout regression (manifest discovery) ships unseen.
python3 "$stage/apply.py" --status "$stage" > /dev/null

# The gates byte-compile the tree, so sweep the caches they wrote
# before anything is zipped.
find "$stage" -name '__pycache__' -type d -exec command rm -rf {} + 2>/dev/null || true

out="${out:-$root/scratch/releases}"
mkdir -p "$out"
zip_path="$out/darkfix-$game-v$version.zip"
python3 - "$stage" "$zip_path" <<'PY'
import sys
import zipfile
from pathlib import Path

stage, out = Path(sys.argv[1]), Path(sys.argv[2])
files = sorted(p for p in stage.rglob("*") if p.is_file())
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
    for p in files:
        arc = p.relative_to(stage).as_posix()
        info = zipfile.ZipInfo(arc, date_time=(1980, 1, 1, 0, 0, 0))
        info.create_system = 3  # Unix, so the exec bit below survives
        mode = 0o100755 if arc == "apply.py" else 0o100644
        info.external_attr = mode << 16
        info.compress_type = zipfile.ZIP_DEFLATED
        zf.writestr(info, p.read_bytes())
PY

echo
echo "built: $zip_path ($(find "$stage" -type f | wc -l) files)"
sha256sum "$zip_path"
