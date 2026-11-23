# Faction Switch for Total War: Rome II

Play several factions in one Grand Campaign. A "Switch faction" button opens a list of the playable factions. Pick
one and press OK: the game saves, a small helper program makes a copy of that save with the chosen faction as the
player, and the game loads it (about a minute). The faction you leave is played by the AI until you switch back.

**Download:** see [Releases](../../releases): `@@@@@@PAW_faction_switch.pack` and the `faction_switch` folder (helper exe and
missions file). Install steps: [INSTALL.txt](INSTALL.txt).
**Steam Workshop:** [Faction Switch](https://steamcommunity.com/sharedfiles/filedetails/?id=3844730726) (the pack;
the helper folder still comes from Releases).

## Status
- Vanilla Rome II, Grand Campaign (main_rome). Tested in game: switching back and forth between 4 factions for 12
  turns, windowed 1280x720, 1280x1024 and 1920x1080, with Consul Scriptum. Newly played factions get their
  victory conditions and chapter objectives.
- Full screen: tested at 2560x1440 (switch to a faction played for the first time).
- Not tested: battles after a switch.
- Divide et Impera version: `@@@@@@PAW_faction_switch_dei.pack` (`tools/build_pack_dei.sh`), DeI 1.3.5 and the 1.3.6
  beta, with DeI's faction names. Tested in game on DeI with the author's DeI mod list: switches, camera, a DeI event
  popup over the Load window, first-time factions' objectives. Not checked in detail: DeI's player-only rules after
  a switch. The pack carries DeI's own `campaigns/main_rome/scripting.lua` (plus two lines). Install steps:
  [INSTALL_DEI.txt](INSTALL_DEI.txt). The `faction_switch` folder (helper and missions files for vanilla, DeI 1.3.5
  and the beta) is shared by both versions.

## How it works
- `pack_src/lua_scripts/paw_fs_switch.lua` (in the pack): the button and window, asks the game for an autosave, starts
  the helper, then opens Menu > Load and tells the helper where to click.
- `tools/fs_ingame.py` (the helper, built into `faction_switch_helper.exe`): copies the autosave and runs
  `tools/fs_loop.py switch`, then clicks OK in the Load window.
- `tools/fs_loop.py` / `tools/switch_faction.py`: the save edit. Moves the "human" marks of the player setup to the
  new faction, sets the turn to continue after the old faction, and gives the new faction its fog of war and
  missions: from its own last save if it was played before, else from the campaign start (with turn-1 missions
  from `missions/<campaign>_<start file hash>.esf`, built by `tools/build_mission_start.py` from turn-1 saves of
  every faction, `tests/harvest.py`).
- Save files are ESF with an LZMA-packed body; `tools/vendor_ia/` is the ESF reader/writer,
  `tools/vendor/liblzma-5.dll` is xz's liblzma (public domain / 0BSD).

## Building
Windows, Python 3, Git Bash. The scripts use the author's local paths (`F:\...`); change them at the top.
- Pack: `sh tools/build_pack.sh`. Needs RPFM (`rpfm_cli`), Ruby with etwng's `xml2ui`, `luac5.1`, and the game's
  vanilla `campaigns/main_rome/scripting.lua` and `text/db/factions.loc` (as TSV) in `work/vanilla/`, extracted from
  `data_rome2.pack` (not included: CA's files).
- Helper: `sh tools/build_helper.sh` (PyInstaller in `.venv`).
- `ui_src/` holds three of the game's UI layouts as etwng XML (`ui2xml`), the base for the button and window.

The tests in `tests/` drive the game with a separate tool (rome2-bridge), not included here.

Made by vibe coding.
