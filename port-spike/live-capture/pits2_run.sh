#!/bin/zsh
(sleep 8
 # 22s prescan + 22 keys x 3s pace + margin
 sleep 105
 wf-recorder -g "14,54 939x1132" -f /tmp/pits2.mp4) &
sleep 9
dosbox --nolocalconf --conf /tmp/ds1-pits.conf
sleep 2
pkill wf-recorder
