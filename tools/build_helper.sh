#!/bin/sh
# Build faction_switch_helper.exe (tools/fs_ingame.py + fs_loop + the vendored IA ESF code + liblzma-5.dll) with
# PyInstaller from the project venv (.venv, PyInstaller 6.22.3). usage: sh tools/build_helper.sh  (project folder)
# Output: build/release/faction_switch/faction_switch_helper.exe (the folder players copy into the game folder).
set -e
P=/f/ROME2/Projects/faction-switch
cd "$P"
rm -rf build/pyi build/release/faction_switch
mkdir -p build/release/faction_switch
.venv/Scripts/python -m PyInstaller --noconfirm --clean --onefile --windowed \
  --name faction_switch_helper \
  --paths F:/ROME2/Projects/faction-switch/tools --paths F:/ROME2/Projects/faction-switch/tools/vendor_ia \
  --hidden-import fs_loop --hidden-import switch_faction --hidden-import savelib --hidden-import shroud \
  --hidden-import esf --hidden-import startpos_tool --hidden-import lzwin --hidden-import addfac --hidden-import lib \
  --add-binary "F:/ROME2/Projects/faction-switch/tools/vendor/liblzma-5.dll;." \
  --workpath build/pyi --specpath build/pyi --distpath build/release/faction_switch \
  tools/fs_ingame.py 2>&1 | grep -E "ERROR|WARNING: (Hidden|lib not)|completed successfully" || true
# missions gap fix: start file(s) with harvested turn-1 missions (tools/build_mission_start.py) -> missions/
mkdir -p build/release/faction_switch/missions; cp data/missions/*.esf build/release/faction_switch/missions/
ls -la build/release/faction_switch/
sha256sum build/release/faction_switch/faction_switch_helper.exe | cut -c1-12
