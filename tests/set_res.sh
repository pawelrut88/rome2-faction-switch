#!/bin/sh
# usage: sh tests/set_res.sh W H   -> windowed WxH in preferences.script.txt (restore from tests/backup after the test)
A="$APPDATA/The Creative Assembly/Rome2/scripts/preferences.script.txt"
sed -i -E "s/^x_res [0-9]+; ?/x_res $1; /; s/^y_res [0-9]+; ?/y_res $2; /; s/^gfx_fullscreen [a-z]+; ?/gfx_fullscreen false; /" "$A"
grep -n "^x_res\|^y_res\|^gfx_fullscreen" "$A"
