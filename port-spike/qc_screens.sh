#!/bin/zsh
# Renders every built UI screen to SPIKE_OUT PNGs for the parity diffs.
# Always runs from this script's own directory.
cd "$(dirname "$0")" || exit 1
renders=(
  "13500 inventory inv"
  "11500 sheet sh"
  "10500 gamemenu gm"
  "17500 spells sp"
  "16500 prefs pf"
  "3011 creation cre"
  "11500 combathud hud"
)
for cfg in $renders; do
  set -- $=cfg
  SPIKE_WIND=$1 SPIKE_SCREEN=$2 SPIKE_OUT=/tmp/spike-oracle/final_$3.png \
    timeout 40 godot --path . res://wind_test.tscn --quit-after 20 > /dev/null 2>&1
  echo "$3 -> /tmp/spike-oracle/final_$3.png"
done
