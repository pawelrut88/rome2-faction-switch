#!/bin/bash
# usage: run_one.sh "save name in save_games" tag
B="python -m rome2bridge"; cd F:/ROME2/Projects/rome2-bridge
OUT="F:/ROME2/Projects/faction-switch/tests/$2"; mkdir -p "$OUT"
$B quit > "$OUT/quit_before.txt" 2>&1
$B start --save "$1" --mod-list "F:/ROME2/Projects/faction-switch/tests/vanilla_modlist.txt" --skip-intro --timeout 400 > "$OUT/start.txt" 2>&1
echo "start exit $?"; grep -E '"(current|turn|human_key|human_turn|screen|alive)"|why|warning|crash' "$OUT/start.txt"
$B screenshot "$OUT/loaded.png" >/dev/null 2>&1
$B lua "local w=scripting.game_interface:model():world(); local fl=w:faction_list(); local h={}; for i=0,fl:num_items()-1 do local f=fl:item_at(i); if f:is_human() then h[#h+1]=f:name() end end; local loc='?'; for i=0,fl:num_items()-1 do local f=fl:item_at(i); if scripting.game_interface:model():faction_is_local(f:name()) then loc=f:name() end end; return 'humans='..table.concat(h,',')..' local='..loc..' turn='..scripting.game_interface:model():turn_number()" > "$OUT/humans.txt" 2>&1; cat "$OUT/humans.txt" | tail -2
