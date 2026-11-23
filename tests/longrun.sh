#!/bin/sh
# Long run (2026-11-23): switch among several factions, one end turn as each, N rounds. Game already running with
# @rome2_bridge.pack + @@@@@@PAW_faction_switch.pack and <game>/faction_switch/faction_switch_helper.exe, on a human turn.
# usage: sh tests/longrun.sh OUTDIR faction1 faction2 ...   (cycles through the list; ROUNDS env, default 10)
OUT=$(cd "$(dirname "$1")" && pwd)/$(basename "$1"); shift; mkdir -p "$OUT"; LOG="$OUT/longrun.log"
G="/f/Steam/steamapps/common/Total War Rome II"; FSD="$G/faction_switch"
SAVES="$APPDATA/The Creative Assembly/Rome2/save_games"
B() { (cd /f/ROME2/Projects/rome2-bridge && python -m rome2bridge "$@"); }
say() { echo "$(date +%T) $*" | tee -a "$LOG"; }
field() { B status 2>/dev/null | grep "\"$1\"" | head -1 | sed 's/.*: *//; s/[",]//g'; }
ROUNDS=${ROUNDS:-10}; i=0
B autoclick test >/dev/null 2>&1
while [ $i -lt "$ROUNDS" ]; do
  for F in "$@"; do
    [ $i -ge "$ROUNDS" ] && break; i=$((i+1))
    cur=$(field human_key); turn=$(field turn)
    if [ "$cur" = "$F" ]; then say "round $i: already $F, skipped"; continue; fi
    n0=$(grep -c "done: loading" "$FSD/helper.log" 2>/dev/null || echo 0); t0=$(date +%s)
    B click fs_switch_button >/dev/null 2>&1; B click "fs_row_$F" >/dev/null 2>&1; B click fs_button_ok >/dev/null 2>&1
    S=$(date +%s)
    until [ "$(grep -c 'done: loading' "$FSD/helper.log" 2>/dev/null)" -gt "$n0" ] || [ $(( $(date +%s) - S )) -gt 240 ]; do sleep 3; done
    t1=$(date +%s)
    if [ "$(grep -c 'done: loading' "$FSD/helper.log")" -le "$n0" ]; then
      say "round $i: $cur -> $F FAILED (no load in 240 s)"; tail -5 "$FSD/helper.log" >> "$LOG"; tail -5 "$FSD/lua.log" >> "$LOG"; break 2
    fi
    name=$(grep 'done: loading' "$FSD/helper.log" | tail -1 | sed 's/.*done: loading //')
    size=$(stat -c %s "$SAVES/$name.save" 2>/dev/null)
    sleep 20
    B wait --timeout 240 >/dev/null 2>&1
    B wait-turn --timeout 600 >/dev/null 2>&1
    now=$(field human_key); turn2=$(field turn); ht=$(field human_turn)
    say "round $i: $cur t$turn -> $F: switch $((t1-t0)) s, save $size bytes ($name); now human $now t$turn2 human_turn=$ht"
    [ "$now" != "$F" ] && { say "  WRONG human after switch"; }
    B screenshot "$OUT/r${i}_$F.png" >/dev/null 2>&1
    B end-turn --timeout 900 >/dev/null 2>&1
    say "  end turn -> $(field human_key) t$(field turn) human_turn=$(field human_turn)"
  done
done
B status 2>/dev/null | grep -i "crash\|dump" >> "$LOG"
say "finished"
