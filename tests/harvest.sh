#!/bin/sh
# Missions harvest (2026-11-23): for each faction, start a NEW main_rome campaign as it and keep its turn-1 autosave
# (state/harvest/t1_<faction>.save), for tools/build_mission_start.py. The faction is chosen with a test pack
# data/fs_harvest.pack holding a copy of the start file whose local faction is changed (tools/startpos_local.py);
# the game's own files are not changed. Game must NOT be running; the bridge's start/quit put the mod list,
# preferences and auto_save.save back.
# usage: sh tests/harvest.sh [SRC_STARTPOS] faction1 faction2 ...    (SRC default: vanilla main_rome)
P=/f/ROME2/Projects/faction-switch; cd "$P"
G="/f/Steam/steamapps/common/Total War Rome II"
VAN="$G/data/campaigns/main_rome/startpos.esf"
case "$1" in *.esf) VAN=$1; shift;; esac
R="/f/ROME2/_TOOLS/Rusted PackFile Manager/rpfm_cli.exe"
AUTO="$APPDATA/The Creative Assembly/Rome2/save_games/auto_save.save"
H=state/harvest; LOG=$H/harvest.log; mkdir -p $H
B() { (cd /f/ROME2/Projects/rome2-bridge && python -m rome2bridge "$@"); }
say() { echo "$(date +%T) $*" | tee -a "$LOG"; }
field() { B status 2>/dev/null | grep "\"$1\"" | head -1 | sed 's/.*: *//; s/[",]//g'; }
printf 'mod "@rome2_bridge.pack";\nmod "fs_harvest.pack";\nDISABLE_BINK true;\nshow_frontend_movies false;\n' > $H/modlist.txt
for F in "$@"; do
  [ -f "$H/t1_$F.save" ] && { say "$F: already harvested"; continue; }
  tasklist | grep -qi rome2.exe && { say "game running, stopping"; exit 1; }
  [ -f "$H/startpos_$F.esf" ] || python tools/startpos_local.py "$VAN" "$H/startpos_$F.esf" "$F" >/dev/null 2>&1
  [ -f "$H/startpos_$F.esf" ] || { say "$F: startpos_local failed"; continue; }
  rm -rf $H/stage; mkdir -p $H/stage/campaigns/main_rome; cp "$H/startpos_$F.esf" $H/stage/campaigns/main_rome/startpos.esf
  OUT=$(cygpath -m "$G/data/fs_harvest.pack"); rm -f "$OUT"
  "$R" --game rome_2 pack create --pack-path "$OUT" >/dev/null 2>&1
  "$R" --game rome_2 pack add --pack-path "$OUT" -F "$(cygpath -m "$P/$H/stage")" >/dev/null 2>&1
  B start --campaign main_rome --mod-list "$(cygpath -m "$P/$H/modlist.txt")" --skip-intro --timeout 600 >/dev/null 2>&1
  B wait --timeout 300 >/dev/null 2>&1
  hk=$(field human_key); t=$(field turn)
  if [ "$hk" != "$F" ]; then say "$F: started as '$hk' t$t, not $F"; B screenshot "$P/$H/wrong_$F.png" >/dev/null 2>&1; B quit >/dev/null 2>&1; sleep 5; continue; fi
  m0=$(stat -c %Y "$AUTO" 2>/dev/null || echo 0)
  B lua "scripting.game_interface:autosave_at_next_opportunity() return 'asked'" >/dev/null 2>&1
  S=$(date +%s)
  until [ "$(stat -c %Y "$AUTO" 2>/dev/null || echo 0)" != "$m0" ] || [ $(( $(date +%s) - S )) -gt 90 ]; do sleep 2; done
  sleep 4   # let the write finish
  if [ "$(stat -c %Y "$AUTO" 2>/dev/null || echo 0)" = "$m0" ]; then say "$F: no autosave in 90 s"
  else cp "$AUTO" "$H/t1_$F.save"; say "$F: t$t saved $(stat -c %s "$H/t1_$F.save") bytes"; fi
  B screenshot "$P/$H/shot_$F.png" >/dev/null 2>&1
  B quit >/dev/null 2>&1; sleep 8
done
rm -f "$G/data/fs_harvest.pack"
say "harvest done"
