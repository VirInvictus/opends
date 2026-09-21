#!/bin/zsh
# Pits take 3, the one that worked (2026-09-21). Copy ds1-pits3.conf to
# /tmp/ and rebuild the scratch rig first (see HANDOFF-wave3-4.md): the
# conf's padded AUTOTYPE (-w 40 -p 3, 35 keys with harmless repeats
# around every transition) survives the boot->title->menu->story chain
# that ate the take-2 schedule. Record the whole session; the game
# exits on its own near the end (computer control opens the EXIT
# popup), so the recording self-terminates the interesting part.
# Take 3 content map (video timeline, 420s): boot ~0-33, story pages
# 36-58, gate + announcer 62-90, walk + exhibition fight 90-160 (the
# engine's own USE screen casts Magic Missile around 130), pens walk
# 180-200, Kurzak dialog + WHAT DO YOU SAY choice strip ~200-240, more
# dialogs to ~275, GAME SAVED ~285, DOS exit ~288. The audit pair cut
# (34..274) is port-spike/audit/videos/pits_live.mp4 vs cast3.mp4.
sleep 2
dosbox --nolocalconf --conf /tmp/ds1-pits3.conf &
GEO=""
for i in $(seq 1 15); do
  GEO=$(hyprctl clients -j 2>/dev/null | python3 -c "
import json, sys
try:
    for c in json.load(sys.stdin):
        if 'dosbox' in c.get('class', '').lower():
            x, y = c['at']; w, h = c['size']
            print(f'{x},{y} {w}x{h}')
            break
except Exception:
    pass")
  [ -n "$GEO" ] && break
  sleep 1
done
echo "geo: $GEO"
[ -z "$GEO" ] && GEO="14,54 939x1132"
sleep 1
wf-recorder -g "$GEO" -f /tmp/pits3.mp4 &
sleep 420
pkill wf-recorder
sleep 1
pkill dosbox
echo "take 3 done"
