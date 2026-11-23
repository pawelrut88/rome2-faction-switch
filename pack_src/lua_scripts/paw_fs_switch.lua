-- Faction switch for vanilla Rome II (Grand Campaign main_rome). Loaded by our campaigns/main_rome/scripting.lua.
-- Needs nothing else in game (no bridge). Outside the game: faction_switch_helper.exe (tools/fs_ingame.py built with
-- PyInstaller) edits the save. Install: the folder faction_switch (with the exe) goes into the game folder, next to
-- Rome2.exe. Paths here are relative to the game's working folder (the game folder).
--
-- The "Switch faction" button (menu bar, top left) opens a list of the playable factions. Pick one, press OK:
--   1. the game autosaves; Lua starts the helper (os.execute);
--   2. the helper copies auto_save.save and edits it so the chosen faction is the human (tools/fs_loop.py switch:
--      play resumes with the faction after the current one, so the current one's turn counts as done), writes
--      ready.txt;
--   3. Lua opens Menu > Load; the new save is the top row and preselected; Lua writes the OK button's position, the
--      helper posts a real click on it and on the confirm tick (the load panel's OK ignores SimulateClick).
-- While the menu is open the game is paused: timers stop; the helper's posted mouse moves give ComponentMouseOn
-- events, which are the frames where Lua looks at the panel.
-- End turn is never blocked (disable_end_turn is not used: it also stops the AI and is stored in saves).
local scripting = require "lua_scripts.EpisodicScripting"
local FACTIONS = require "data.lua_scripts.paw_fs_factions"     -- { {key, name}, ... } as the rows in the layout
local DIR = [[faction_switch\]]                            -- run files and logs (the helper's own folder)
local HELPER = [[faction_switch\faction_switch_helper.exe]]
local DEV_HELPER = [[faction_switch\dev_helper.cmd]]               -- development only: runs tools/fs_ingame.py
local function exists(p) local f = io.open(p, "rb"); if f then f:close(); return true end; return false end
local function helper_there() return exists(HELPER) or exists(DEV_HELPER) end

local FS = { state = "idle" }
local function g() return scripting.game_interface end

local function log(s)
  local f = io.open(DIR .. "lua.log", "a"); if f then f:write(os.date("%H:%M:%S ") .. tostring(s) .. "\n"); f:close() end
end
local function wfile(name, s) local f = io.open(DIR .. name, "w"); if f then f:write(s); f:close() end end
local function rfile(name) local f = io.open(DIR .. name, "r"); if not f then return nil end; local s = f:read("*a"); f:close(); return s end

-- UI helpers (UIComponent: global, else from the Lua registry, as the bridge and Consul find it)
local UIC
local function uic()
  if UIC then return UIC end
  if UIComponent then UIC = UIComponent; return UIC end
  pcall(function()
    for _, v in pairs(debug.getregistry()) do
      local ok, env = pcall(debug.getfenv, v)
      if ok and type(env) == "table" and env.UIComponent ~= nil then UIC = env.UIComponent; break end
    end
  end)
  return UIC
end
local function U(a)
  if type(a) == "userdata" and tostring(a):sub(1, 12) == "UIComponent " then return a end
  return uic()(a)
end
local function find(id, ctx)
  if not FS.root then return nil end
  local base = FS.root
  if ctx then local c = base:Find(ctx); if not c then return nil end; base = U(c) end
  local x = base:Find(id); if x then return U(x) end
end
local function shown(c)
  for _ = 1, 40 do
    local okv, v = pcall(function() return c:Visible() end)
    if not okv or not v then return false end
    local okp, p = pcall(function() return c:Parent() end)
    if not okp or p == nil then return true end
    local okw, pc = pcall(function() return U(p) end)
    if not okw or pc == nil then return true end
    c = pc
  end
  return true
end
local function pos(c)  -- UI position as "x y w h root_w root_h"
  local x, y = c:Position(); local w, h = c:Dimensions(); local rw, rh = FS.root:Dimensions()
  return string.format("%d %d %d %d %d %d", x, y, w, h, rw, rh)
end

local function local_faction()
  local m = g():model(); local fl = m:world():faction_list()
  for i = 0, fl:num_items() - 1 do local n = fl:item_at(i):name(); if m:faction_is_local(n) then return n end end
end
local function alive(key)
  local w = g():model():world()
  if not w:faction_exists(key) then return false end
  local f = w:faction_by_key(key)
  return f:region_list():num_items() > 0 or f:character_list():num_items() > 0
end
local function name_of(key) for _, kv in ipairs(FACTIONS) do if kv[1] == key then return kv[2] end end; return key end
-- Whose turn: kept from the game's turn events. (Before: the End Turn button's state; in the strategic map mode that
-- button isn't there, so a switch from map mode was refused: user's playtest 2026-11-23.) A save can only be made
-- during the player's own turn, so after a load (the script starts afresh) it is the player's turn.
FS.myturn = true
local function my_turn() return FS.myturn end
local function on_turn(starts)
  return function(ctx)
    local k; pcall(function() k = ctx:faction():name() end)
    if k and k == local_faction() then FS.myturn = starts; log("turn " .. (starts and "starts" or "ends") .. ": " .. k) end
  end
end

-- ---------------- the window
local function set_title(t) local c = find("fs_title"); if c then c:SetStateText(t) end end
local function close_panel() local p = find("fs_switch_panel"); if p then p:SetVisible(false) end end
local function set_ok(v) local b = find("fs_button_ok"); if b then b:SetVisible(v) end end
-- the window with no faction rows: a short title, one text line in the list (row fs_row_msg, not a faction) and the
-- close button. Used for "please wait" while the helper edits the save (the window is modal, so nothing the player
-- does in that time is lost) and for errors. The list frame stays: it is the window's dark background.
local function message_panel(title, text)
  local p = find("fs_switch_panel"); if not p then log("no fs_switch_panel: " .. title .. " " .. tostring(text)); return end
  for _, kv in ipairs(FACTIONS) do local r = find("fs_row_" .. kv[1]); if r then r:SetVisible(false) end end
  local m = find("fs_row_msg"); if m then m:SetVisible(true); pcall(function() m:SetState("unselected") end) end
  local l = find("fs_label_msg"); if l then l:SetStateText(text or "") end
  pcall(function() find("list_box", "fs_switch_panel"):Layout() end)
  set_ok(false); set_title(title); p:SetVisible(true)
end
local function open_panel()
  local p = find("fs_switch_panel"); if not p then log("no fs_switch_panel in the UI (layout not loaded?)"); return end
  if FS.state ~= "idle" then message_panel("Switching to " .. name_of(FS.new), "Please wait, about a minute..."); return end
  local me = local_faction(); FS.choice = nil
  local m = find("fs_row_msg"); if m then m:SetVisible(false) end
  for _, kv in ipairs(FACTIONS) do
    local r = find("fs_row_" .. kv[1])
    if r then
      local ok = kv[1] ~= me and alive(kv[1])
      r:SetVisible(ok); pcall(function() r:SetState("unselected") end)
    end
  end
  set_ok(true)
  pcall(function() find("list_box", "fs_switch_panel"):Layout() end)
  if not my_turn() then set_title("Switch faction: only during your own turn")
  else set_title("Switch faction (now: " .. name_of(me) .. ")") end
  p:SetVisible(true)
end
local function fail(why)   -- back to idle and show why; removing request.txt makes the helper stop (stale())
  os.remove(DIR .. "request.txt"); FS.state = "idle"; log("failed: " .. why)
  message_panel("Switch failed", why:sub(1, 90))
end

-- display positions of the new faction's characters (armies, fleets, agents) and settlements, for the helper: the
-- save edit marks the land and sea around them as explored and visible (fleets at sea stayed under the fog with
-- the Lua region reveal alone: user's playtest 2026-11-23; tools/shroud.py)
local function write_positions(key)
  local f = g():model():world():faction_by_key(key); local out, n = {}, 0
  local function add(o)
    pcall(function()
      local x, y = o:display_position_x(), o:display_position_y()
      if x and y and (x ~= 0 or y ~= 0) then n = n + 1; out[n] = string.format("%.1f %.1f", x, y) end
    end)
  end
  pcall(function() local cl = f:character_list(); for i = 0, cl:num_items() - 1 do add(cl:item_at(i)) end end)
  pcall(function() local rl = f:region_list(); for i = 0, rl:num_items() - 1 do add(rl:item_at(i):settlement()) end end)
  wfile("positions.txt", table.concat(out, "\n") .. "\n")
  return n
end

local function start_switch(new)
  local old = local_faction()
  local turn = g():model():turn_number()
  for _, n in ipairs({ "request.txt", "ready.txt", "click.txt", "tick.txt", "camera.txt", "poke.txt", "positions.txt" }) do os.remove(DIR .. n) end
  local np = 0; pcall(function() np = write_positions(new) end)
  wfile("request.txt", string.format("%s %s %d %d", old, new, turn, os.time()))
  g():autosave_at_next_opportunity()
  os.execute('start "" /b "' .. (exists(HELPER) and HELPER or DEV_HELPER) .. '"')
  FS.state = "waiting"; FS.new = new; FS.polls = 0; FS.poll_n = (FS.poll_n or 0) + 1
  message_panel("Switching to " .. name_of(new), "Please wait, about a minute...")
  log("switch " .. old .. " -> " .. new .. " t" .. turn .. ": autosave asked, helper started; " .. np .. " positions")
  -- each switch gets its own timer name (re-arming one name can make two chains; a cancelled chain must die)
  g():add_time_trigger("fs_poll" .. FS.poll_n, 1)
end
local function cancel_switch()   -- the helper exits by itself once request.txt is gone (fs_ingame.py stale())
  os.remove(DIR .. "request.txt"); FS.state = "idle"; close_panel(); log("cancelled by the player")
end

-- The Load window. Find("load-save_game") gives the first one in the tree, which can be a hidden Save window the
-- player opened earlier (same layout): its list never shows a row, so the switch hung in the Load window (user's
-- playtest 2026-11-23, after saving by hand). Take the one that is shown.
local function load_panel()
  local hit
  local function walk(c, d)
    if hit or d > 6 then return end
    for i = 0, c:ChildCount() - 1 do
      local ok, ch = pcall(function() return U(c:Find(i)) end)
      if ok and ch then
        local okid, id = pcall(function() return ch:Id() end)
        if okid and id == "load-save_game" then
          if shown(ch) then hit = ch; return end
        else walk(ch, d + 1) end
        if hit then return end
      end
    end
  end
  if FS.root then pcall(walk, FS.root, 0) end
  return hit
end
local function in_load(id)
  local p = load_panel(); if not p then return nil end
  local x = p:Find(id); if x then return U(x) end
end

-- the top row of the load list (the list_box children are not in screen order)
local function top_row()
  local lb = in_load("list_box"); if not lb then return nil end
  local by, bn
  for i = 0, lb:ChildCount() - 1 do
    pcall(function()
      local r = U(lb:Find(i)); local t = tostring(U(r:Find("name")):GetStateText()); local _, y = r:Position()
      if t ~= "" and r:Visible() and (not by or y < by) then by, bn = y, t end
    end)
  end
  return bn
end

-- the list cuts long names: "FS rom_ptolemaics t13 073..." (long run 2, 2026-11-23); accept a cut name that starts
-- the target
local function is_target(name)
  if not name or not FS.target then return false end
  if name == FS.target then return true end
  local cut = name:match("^(.-)%.%.%.$") or name:match("^(.-)\226\128\166$")   -- "..." or the ellipsis character
  return cut ~= nil and #cut >= 8 and FS.target:sub(1, #cut) == cut
end

local function on_ui_frame()
  if FS.state == "opening" then
    FS.tries = (FS.tries or 0) + 1
    local name = top_row()
    if FS.tries == 1 or FS.tries % 10 == 0 then log("top row (try " .. FS.tries .. "): " .. tostring(name)) end
    if is_target(name) then
      local ok = in_load("button_ok")
      wfile("click.txt", "OK " .. pos(ok)); FS.state = "confirm"; log("top row is the target (try " .. FS.tries .. "); OK at " .. pos(ok))
    elseif FS.tries >= 200 then
      wfile("click.txt", "ERROR top row is '" .. tostring(name) .. "', not the target"); FS.state = "idle"
      log("gave up: top row " .. tostring(name) .. "; the new save is in Menu > Load: " .. tostring(FS.target))
    end
  elseif FS.state == "tick" then
    local t = find("button_tick", "dialogue_box")
    if t and shown(t) then wfile("tick.txt", "TICK " .. pos(t)); log("tick at " .. pos(t)); FS.state = "loading" end
  end
end

local function on_click(ctx)
  local s = ""; pcall(function() s = ctx.string end)
  if s == "fs_switch_button" then
    local p = find("fs_switch_panel")
    if p and p:Visible() then close_panel() else open_panel() end
  elseif s:sub(1, 7) == "fs_row_" and s ~= "fs_row_msg" then
    FS.choice = s:sub(8)
    for _, kv in ipairs(FACTIONS) do
      local r = find("fs_row_" .. kv[1]); if r then pcall(function() r:SetState(kv[1] == FS.choice and "selected" or "unselected") end) end
    end
  elseif s == "fs_button_cancel" then
    if FS.state == "waiting" then cancel_switch() else close_panel() end
  elseif s == "fs_button_ok" then
    if FS.state ~= "idle" then set_title("Switching... please wait"); return end
    if not my_turn() then set_title("Switch faction: only during your own turn"); return end
    if not FS.choice then set_title("Choose a faction first"); return end
    if not helper_there() then
      message_panel("Switch failed", "Helper not found: put the faction_switch folder into the game folder"); return
    end
    start_switch(FS.choice)
  elseif FS.state ~= "idle" then
    log("click " .. s .. " in state " .. FS.state)
    if FS.state == "confirm" and s == "button_ok" then FS.state = "tick" end
    if FS.state == "opening" or FS.state == "tick" then on_ui_frame() end
  end
end

-- ---------------- camera to the new faction after the load (camera.txt = its key, written before the load)
-- Rome II's scroll_camera stops all timers and scroll_camera_with_direction does nothing (SHARED_KNOWLEDGE.md), so:
-- SimulateClick the faction leader's (else any general's) row character_row_<cqi> in the lists panel's Forces tab,
-- which selects that army and moves the camera to it (population-supply, tested 2026-11-10); open the tab first if the
-- row isn't there, close it again after.
local function general_cqi(key)
  local f = g():model():world():faction_by_key(key); local first
  pcall(function()
    if f:has_faction_leader() and f:faction_leader():has_military_force() then first = f:faction_leader():cqi() end
  end)
  if first then return first end
  local cl = f:character_list()
  for i = 0, cl:num_items() - 1 do
    local ok, c = pcall(function() local ch = cl:item_at(i); if ch:has_military_force() then return ch:cqi() end end)
    if ok and c then return c end
  end
end
local CAM = nil
local function camera_step(name)
  if not CAM then return end
  CAM.tries = CAM.tries + 1
  local row = find("character_row_" .. CAM.cqi)
  if row then
    pcall(function() row:SimulateClick() end); log("camera: clicked character_row_" .. CAM.cqi .. " (try " .. CAM.tries .. ")")
    if CAM.opened then pcall(function() find("tab_units"):SimulateClick() end) end
    CAM = nil; return
  end
  if CAM.tries >= 6 then log("camera: no character_row_" .. CAM.cqi); if CAM.opened then pcall(function() find("tab_units"):SimulateClick() end) end; CAM = nil; return end
  if not CAM.opened then local t = find("tab_units"); if t then pcall(function() t:SimulateClick() end); CAM.opened = true end end
  g():add_time_trigger("fs_cam" .. CAM.tries, 0.3)
end
-- A faction played for the first time gets its turn-1 shroud (from the start/missions file). By a late turn its AI
-- armies stand in land that was unexplored then: hidden under the clouds and not selectable (user's playtest,
-- Seleucid at turn 18, 2026-11-23). So after a switch: every region it owns and every region one of its characters
-- stands in is made seen + visible for it. True for any played faction too (its own land and armies), so done always.
local function reveal_own(key)
  local gi = g(); local f = gi:model():world():faction_by_key(key); local done, n = {}, 0
  local function add(r)
    if not r or r == "" or done[r] then return end
    done[r] = true; n = n + 1
    pcall(function() gi:make_region_seen_in_shroud(key, r) end)
    pcall(function() gi:make_region_visible_in_shroud(key, r) end)
  end
  pcall(function()
    local rl = f:region_list()
    for i = 0, rl:num_items() - 1 do add(rl:item_at(i):name()) end
  end)
  local cl = f:character_list()
  for i = 0, cl:num_items() - 1 do
    pcall(function() local ch = cl:item_at(i); if ch:has_region() then add(ch:region():name()) end end)
  end
  log("shroud: " .. n .. " own/army regions made seen and visible for " .. key)
end

local function camera_after_load()
  local want = rfile("camera.txt"); if not want then return end
  want = want:gsub("%s+$", ""); os.remove(DIR .. "camera.txt")
  local me = local_faction()
  if me ~= want then log("camera: local faction is " .. tostring(me) .. ", not " .. want .. "; not moved"); return end
  pcall(reveal_own, me)
  local cqi = general_cqi(me)
  if not cqi then log("camera: " .. me .. " has no army"); return end
  CAM = { cqi = cqi, tries = 0 }
  g():add_time_trigger("fs_cam0", 1)
end

local function on_timer(ctx)
  local s = tostring(ctx.string)
  if s:sub(1, 6) == "fs_cam" then camera_step(s); return end
  if s ~= "fs_poll" .. tostring(FS.poll_n) or FS.state ~= "waiting" then return end
  FS.polls = FS.polls + 1
  local r = rfile("ready.txt")
  if r and r:sub(1, 5) == "READY" then
    FS.target = r:sub(7):gsub("%s+$", ""); FS.state = "opening"; FS.tries = 0
    wfile("camera.txt", FS.new)
    log("ready: " .. FS.target .. "; opening Menu > Load")
    close_panel()   -- modal: with it open the Load panel ignores clicks
    local ok, e = pcall(function() find("button_menu", "menu_bar"):SimulateClick(); find("button_load"):SimulateClick() end)
    log("menu/load clicked: " .. tostring(ok) .. " " .. tostring(e))
    -- the menu pauses the game: no timers from here on, and ComponentMouseOn does not always come (long run round
    -- 3, 2026-11-23). Look once now, and give the helper a harmless spot to click (the Local tab, already selected):
    -- every click is a ComponentLClickUp, i.e. a frame in which on_ui_frame looks again
    pcall(on_ui_frame)
    if FS.state == "opening" then
      local lt = in_load("button_local")
      if lt then wfile("poke.txt", "POKE " .. pos(lt)) end
    end
  elseif r then
    fail((r:gsub("^ERROR%s*", ""):gsub("%s+$", "")))
  elseif FS.polls > 240 then   -- the helper gives up after ~90 s itself; this covers a helper that never started
    os.remove(DIR .. "request.txt"); fail("no answer from the helper (see faction_switch\\helper.log)")
  else
    g():add_time_trigger("fs_poll" .. FS.poll_n, 1)
  end
end

-- our button right after the last visible one of the row (the layout's x=172 left a gap in game: the game moves its
-- buttons at runtime, e.g. the hidden chat button)
local function place_button()
  local b = find("fs_switch_button"); if not b then return end
  -- every shown button-sized child of menu_bar in the row of button_menu counts, so buttons other mods add there
  -- (Consul Scriptum's consul_scriptum_button_toggle) are not covered
  local mbar, first = find("menu_bar"), find("button_menu", "menu_bar")
  if not (mbar and first) then return end
  local _, by = first:Position(); local _, bh = first:Dimensions()
  local best
  for i = 0, mbar:ChildCount() - 1 do
    pcall(function()
      local c = U(mbar:Find(i)); local id = c:Id()
      if id ~= "fs_switch_button" and c:Visible() then
        local x, y = c:Position(); local w, h = c:Dimensions()
        if math.abs(y - by) < 4 and h <= bh + 8 and w <= bh + 8 and (not best or x + w > best[1] + best[3]) then
          best = { x, y, w, id }
        end
      end
    end)
  end
  if best then local x, y = b:Position(); b:MoveTo(best[1] + best[3], best[2]); log("button from " .. x .. "," .. y .. " to " .. (best[1] + best[3]) .. "," .. best[2] .. " (after " .. best[4] .. ")") end
end

-- a Lua error inside an event callback is swallowed silently by the game: log it
local function guard(name, fn)
  return function(ctx) local ok, e = pcall(fn, ctx); if not ok then log("ERROR in " .. name .. ": " .. tostring(e)) end end
end
scripting.AddEventCallBack("UICreated", guard("UICreated", function(ctx)
  FS.root = U(ctx.component)
  -- our button and window are built into campaign_tactical_map (a layout Consul Scriptum and DeI leave alone);
  -- move them under menu_bar, which is always shown and never closes
  local mbar = find("menu_bar")
  for _, id in ipairs({ "fs_switch_button", "fs_switch_panel" }) do
    local c = find(id)
    if c and mbar then
      local okp, par = pcall(function() return U(c:Parent()):Id() end)
      if not (okp and par == "menu_bar") then
        local ok, e = pcall(function() mbar:Adopt(c:Address()) end)
        log("adopt " .. id .. " from " .. tostring(par) .. ": " .. tostring(ok) .. " " .. tostring(e or ""))
      end
    end
  end
  pcall(function() find("fs_switch_panel"):MoveTo(360, 40) end)
  close_panel()
  -- row labels: text baked into the layout shows "dy", so set it here (each label has its own name, fs_label_<key>)
  for _, kv in ipairs(FACTIONS) do local c = find("fs_label_" .. kv[1]); if c then c:SetStateText(kv[2]) end end
  log("UI created; panel " .. tostring(find("fs_switch_panel") ~= nil) .. ", button " .. tostring(find("fs_switch_button") ~= nil))
end))
scripting.AddEventCallBack("ComponentLClickUp", guard("click", on_click))
scripting.AddEventCallBack("ComponentMouseOn", guard("mouse", function() if FS.state ~= "idle" then on_ui_frame() end end))
scripting.AddEventCallBack("TimeTrigger", guard("timer", on_timer))
scripting.AddEventCallBack("FactionTurnStart", guard("turn start", on_turn(true)))
scripting.AddEventCallBack("FactionTurnEnd", guard("turn end", on_turn(false)))
-- timers armed at UICreated during a load only fire after turn start; FirstTickAfterWorldCreated is the place
scripting.AddEventCallBack("FirstTickAfterWorldCreated", guard("first tick", function()
  pcall(place_button); camera_after_load()
end))
log("fs_switch loaded")
return FS   -- package.loaded["data.lua_scripts.paw_fs_switch"], for checks from outside (bridge)
