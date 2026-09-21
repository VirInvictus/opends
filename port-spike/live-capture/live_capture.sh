#!/bin/zsh
# Hands-off live capture: launch dosbox (AUTOTYPE drives), record the
# whole session, kill at the end. No interactive input.
sleep 2
# find the dosbox window geometry
for i in 1 2 3 4 5 6 7 8 9 10; do
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
echo "window geo: $GEO"
# record the entire session (200s)
wf-recorder -g "$GEO" -f /tmp/live_session.mp4 -o /tmp 2>/dev/null &
REC=$!
sleep 205
kill $REC 2>/dev/null
pkill -f "dosbox" 2>/dev/null
echo "capture done"
