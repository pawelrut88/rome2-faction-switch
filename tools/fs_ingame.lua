-- Faction switch from inside the game (vanilla Rome II). FIRST VERSION, needs the rome2-bridge loaded (uses its B
-- helpers ROME2_BRIDGE). Load it in a running campaign with:  python -m rome2bridge lua -f tools/fs_ingame.lua
--
-- How it works (see NOTES.md "In-game switch"):
--  * End turn is disabled for the played factions; pressing End Turn starts a switch instead.
--  * Lua asks for an autosave and starts the helper tools/fs_ingame.py (os.execute), which edits a copy of
--    auto_save.save so the next faction in FS_FACTIONS is the human (tools/fs_loop.py switch) and writes ready.txt.
--  * Lua (timer) sees ready.txt, opens Menu > Load. The newest save (the switched one) is the top row and selected.
--    The load panel's OK ignores SimulateClick, so Lua writes the OK button's position to click.txt and the helper
--    posts real clicks on OK and on the confirm dialog's tick.
local FS_FACTIONS = FS_FACTIONS or { "rom_rome", "rom_carthage" }   -- played factions, in switch order
local DIR = [[F:\ROME2\Projects\faction-switch\state\ingame\]]
local HELPER = [[F:\ROME2\Projects\faction-switch\tools\fs_ingame.py]]
local B = ROME2_BRIDGE
local g = scripting.game_interface

local function log(s)
  local f = io.open(DIR .. "lua.log", "a"); if f then f:write(os.date("%H:%M:%S ") .. s .. "\n"); f:close() end
end
local function wfile(name, s) local f = io.open(DIR .. name, "w"); f:write(s); f:close() end
local function rfile(name) local f = io.open(DIR .. name, "r"); if not f then return nil end; local s = f:read("*a"); f:close(); return s end

local function local_faction()
  local fl = g:model():world():faction_list()
  for i = 0, fl:num_items() - 1 do
    local n = fl:item_at(i):name(); if g:model():faction_is_local(n) then return n end
  end
end
local function next_faction(cur)
  for i, k in ipairs(FS_FACTIONS) do if k == cur then return FS_FACTIONS[i % #FS_FACTIONS + 1] end end
end
-- UI position of a component as {x, y, w, h, root_w, root_h} text
local function pos(c)
  local x, y = c:Position(); local w, h = c:Dimensions(); local rw, rh = B.root():Dimensions()
  return string.format("%d %d %d %d %d %d", x, y, w, h, rw, rh)
end

FS = { state = "idle" }   -- one global; reloading this file replaces it (old callbacks check FS.gen)
FS.gen = (FS_GEN or 0) + 1; FS_GEN = FS.gen
local GEN = FS.gen

-- disable_end_turn(true) also stops AI factions from ending their turns, and it is stored in the save (test P3,
-- 2026-11-23: a save taken with it set stalled the AI turn after loading). So it is set only during the local human's
-- own turn (End Turn button active) and cleared before the autosave.
local me = local_faction()
local function et_state() local b = B.find_shown("button_end_turn"); local st = ""; pcall(function() st = tostring(b:CurrentState()) end); return st end
if next_faction(me) and not et_state():find("inactive") then
  g:disable_end_turn(true); log("armed gen " .. GEN .. ", local " .. me .. ", end turn disabled (button " .. et_state() .. ")")
else
  g:disable_end_turn(false); log("armed gen " .. GEN .. ", local " .. tostring(me) .. ", end turn left enabled (button " .. et_state() .. ")")
end

local function start_switch()
  local old = local_faction(); local new = next_faction(old)
  if not new then return end
  local turn = g:model():turn_number()
  for _, n in ipairs({ "request.txt", "ready.txt", "click.txt", "tick.txt" }) do os.remove(DIR .. n) end
  wfile("request.txt", string.format("%s %s %d %d", old, new, turn, os.time()))
  g:disable_end_turn(false)   -- must not be in the save; the button is locked in the UI instead
  pcall(function() local b = B.find_shown("button_end_turn"); b:SetState("inactive"); b:SetInteractive(false) end)
  g:autosave_at_next_opportunity()
  os.execute('start "" /b pythonw "' .. HELPER .. '"')
  FS.state = "waiting"; log("switch " .. old .. " -> " .. new .. " t" .. turn .. ": autosave asked, helper started")
  g:add_time_trigger("fs_poll", 1)
end

-- the top row of the load list (rows are not in visual order among the list_box children)
local function top_row()
  local lb = B.find("list_box", "load-save_game"); if not lb then return nil end
  local best, by, bn
  for i = 0, lb:ChildCount() - 1 do
    pcall(function()
      local r = B.U(lb:Find(i)); local nm = B.U(r:Find("name"))
      local t = tostring(nm:GetStateText()); local _, y = r:Position()
      if t ~= "" and r:Visible() and (not by or y < by) then best, by, bn = r, y, t end
    end)
  end
  return best, bn
end

-- While the menu is open the game is paused: timers stop and nested SimulateClicks run inside the same frame, so the
-- list (filled a frame after the panel opens) can't be waited for from Lua alone. The helper posts mouse moves over
-- the window; each ComponentMouseOn event is a fresh frame where the panel is checked (on_ui_frame).
local function on_ui_frame()
  if FS.state == "opening" then
    FS.tries = (FS.tries or 0) + 1
    local _, name = top_row()
    if name == FS.target then
      local ok = B.find("button_ok", "load-save_game")
      wfile("click.txt", "OK " .. pos(ok)); FS.state = "confirm"; log("top row is the target (try " .. FS.tries .. "); OK at " .. pos(ok))
    elseif FS.tries >= 200 then
      wfile("click.txt", "ERROR top row is '" .. tostring(name) .. "', not the target"); FS.state = "idle"
      log("gave up: top row " .. tostring(name))
    end
  elseif FS.state == "tick" then
    local t = B.find_shown("button_tick", "dialogue_box")
    if t then wfile("tick.txt", "TICK " .. pos(t)); log("tick at " .. pos(t)); FS.state = "loading" end
  end
end

local function on_click(ctx)
  if FS_GEN ~= GEN then return end
  local s = ""; pcall(function() s = ctx.string end)
  if FS.state ~= "idle" then log("click " .. s .. " in state " .. FS.state) end
  if s == "button_end_turn" and FS.state == "idle" and next_faction(local_faction()) then
    start_switch()
  elseif FS.state == "confirm" and s == "button_ok" then
    FS.state = "tick"
  end
end

local function on_timer(ctx)
  if FS_GEN ~= GEN or ctx.string ~= "fs_poll" then return end
  if FS.state ~= "waiting" then return end
  -- the End Turn warning ("Are you sure you want to end your turn?") stays open: close it
  local c = B.find_shown("button_cancel", "dialogue_box"); if c then c:SimulateClick() end
  local r = rfile("ready.txt")
  if r and r:sub(1, 5) == "READY" then
    FS.target = r:sub(7):gsub("%s+$", ""); FS.state = "opening"; FS.tries = 0
    log("ready: " .. FS.target .. "; opening Menu > Load")
    local ok, e = pcall(function() B.find_shown("button_menu"):SimulateClick(); B.find("button_load"):SimulateClick() end)
    log("menu/load clicked: " .. tostring(ok) .. " " .. tostring(e))
  elseif r then
    log("helper failed: " .. r); FS.state = "idle"
  else
    g:add_time_trigger("fs_poll", 1)
  end
end

scripting.AddEventCallBack("FactionTurnStart", function(ctx)
  if FS_GEN ~= GEN then return end
  local n = ""; pcall(function() n = ctx:faction():name() end)
  if n == local_faction() and next_faction(n) and FS.state == "idle" then g:disable_end_turn(true); log("turn start " .. n .. ": end turn disabled") end
end)
-- a Lua error inside an event callback is swallowed silently by the game: log it
scripting.AddEventCallBack("ComponentLClickUp", function(ctx)
  local ok, e = pcall(on_click, ctx); if not ok then log("ERROR in click handler: " .. tostring(e)) end
end)
scripting.AddEventCallBack("ComponentMouseOn", function(ctx)
  if FS_GEN ~= GEN or FS.state == "idle" then return end
  local ok, e = pcall(on_ui_frame); if not ok then log("ERROR in mouse handler: " .. tostring(e)) end
end)
scripting.AddEventCallBack("TimeTrigger", function(ctx)
  local ok, e = pcall(on_timer, ctx); if not ok then log("ERROR in timer: " .. tostring(e)) end
end)
return "fs_ingame gen " .. GEN .. " local " .. tostring(me)
