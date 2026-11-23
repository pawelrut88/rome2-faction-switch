#!/bin/sh
# Build build/dei/faction_switch_dei.pack: the DeI version (Divide et Impera, main_rome = DeI's Grand Campaign).
# usage: sh tools/build_pack_dei.sh   (from the project folder)
# Same as tools/build_pack.sh, except:
#   campaigns/main_rome/scripting.lua  DeI's file (work/dei, from _divide_et_impera_release_12_Part1.pack) + our tail
#   lua_scripts/fs_factions.lua        DeI's 45 playable factions with DeI's names (python tools/uibuild_fs.py dei)
#   ui/campaign ui/campaign_tactical_map  vanilla layout + our button and window (DeI doesn't replace this file)
# Contains DeI's scripting.lua: share it only with the DeI team's OK. Must load ABOVE DeI (and the 1.3.6 beta) so our
# scripting.lua wins. If DeI changes its scripting.lua, extract it again and rebuild.
set -e
P=/f/ROME2/Projects/faction-switch
R="/f/ROME2/_TOOLS/Rusted PackFile Manager/rpfm_cli.exe"
D=/f/ROME2/ConsulScriptum/.deps
export PATH="$D/ruby/bin:$PATH" GEM_HOME="$D/ruby/lib/ruby/gems/3.4.0" GEM_PATH="$D/ruby/lib/ruby/gems/3.4.0"
cd "$P"
OUT=$(cygpath -m "$P/build/dei/faction_switch_dei.pack")
python tools/uibuild_fs.py dei
S=build/stage_dei
rm -rf $S; mkdir -p "$S/campaigns/main_rome" $S/lua_scripts "$S/ui/campaign ui"
V=work/dei/campaigns/main_rome/scripting.lua
grep -q 'scripting.SetCampaign("main_rome")' "$V"
{ cat "$V"; printf '\r\n\r\n'; cat pack_src/scripting_tail.lua; } > $S/campaigns/main_rome/scripting.lua
cp pack_src/lua_scripts/fs_switch.lua $S/lua_scripts/
cp build/dei/fs_factions.lua $S/lua_scripts/
for f in $S/lua_scripts/*.lua $S/campaigns/main_rome/scripting.lua; do "$D/lua/luac5.1.exe" -p "$f"; done
ruby "$D/etwng/ui/bin/xml2ui" build/dei/campaign_tactical_map_fs.xml "$S/ui/campaign ui/campaign_tactical_map"
rm -f "$OUT"
"$R" --game rome_2 pack create --pack-path "$OUT" >/dev/null 2>&1
"$R" --game rome_2 pack add --pack-path "$OUT" -F "$(cygpath -m "$P/$S")" >/dev/null 2>&1
"$R" --game rome_2 pack list -p "$OUT" 2>/dev/null | grep -v INFO
ls -la build/dei/faction_switch_dei.pack; sha256sum build/dei/faction_switch_dei.pack | cut -c1-12
