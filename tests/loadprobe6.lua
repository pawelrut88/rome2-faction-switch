-- load a save from the in-game menu by script only; tries several ways to press the load panel's OK, one per frame
local TARGET = "FS L4 carthage t4"
local function log(s) local g = io.open("fs_evlog.txt", "a"); g:write(s .. "\n"); g:flush(); g:close() end
local function shown(id, ctx)
  local c = B.find_shown(id, ctx) or B.find(id, ctx); if not c then return nil end
  local v = false; pcall(function() v = c:Visible() end); if v then return c end
end
local row
local function find_row()
  local lb = B.find_shown('list_box', 'load-save_game'); if not lb then return nil end
  for i = 0, lb:ChildCount() - 1 do
    local r = B.U(lb:Find(i)); local t = ''
    pcall(function() t = tostring(B.U(r:Find('name')):GetStateText()) end)
    if t == TARGET then return r end
  end
end
local attempts = {
  function(ok) ok:SimulateClick() end,
  function(ok) row:SimulateClick(); ok:SimulateClick() end,
  function(ok) ok:SimulateKey('RETURN') end,
  function(ok) B.U(shown('load-save_game')):SimulateKey('RETURN') end,
  function(ok) row:SimulateKey('RETURN') end,
}
local step, a = 0, 0
local function next_frame() if row then row:SimulateClick() else local b = B.find('button_local', 'load-save_game'); if b then b:SimulateClick() end end end
FS_STEP6 = function(ev)
  step = step + 1; if step > 40 then log('gave up'); FS_STEP6 = nil; return end
  local db = shown('button_tick', 'dialogue_box')
  if db then local t = ''; pcall(function() t = tostring(B.find_shown('DY_text', 'dialogue_box'):GetStateText()) end)
    log('dialogue: ' .. t); local x, y = db:Position(); log('tick at ' .. x .. ',' .. y); db:SimulateClick(); log('tick clicked'); FS_STEP6 = nil; return end
  if a == 0 and not shown('load-save_game') then next_frame(); return end
  if not shown('load-save_game') then log('load panel gone (after attempt ' .. a .. ')'); FS_STEP6 = nil; return end
  if not row then row = find_row(); if row then log('row found'); row:SimulateClick(); return end; next_frame(); return end
  a = a + 1; local f = attempts[a]; if not f then log('all attempts done'); FS_STEP6 = nil; return end
  local ok = shown('button_ok', 'load-save_game')
  local r, e = pcall(f, ok); log('attempt ' .. a .. (r and ' ok' or (' err ' .. tostring(e))))
  next_frame()
end
scripting.AddEventCallBack('ComponentLClickUp', function(ctx)
  local s = ''; pcall(function() s = ctx.string end); log('ev6 ' .. s)
  if FS_STEP6 and s ~= 'button_menu' then FS_STEP6(s) end
end)
FS_STEP5 = nil; log('armed6 ' .. TARGET)
B.click('button_menu'); B.click('button_load')
return 'sent'
