local TARGET = "FS L5 rome t4 from carthage"
local function log(s) local g = io.open("fs_evlog.txt", "a"); g:write(s .. "\n"); g:flush(); g:close() end
local function try_load()
  local lb = B.find_shown('list_box', 'load-save_game') or B.find('list_box', 'load-save_game')
  if not lb then log('no list'); return false end
  for i = 0, lb:ChildCount() - 1 do
    local r = B.U(lb:Find(i)); local nm = B.U(r:Find('name')); local t = ''
    pcall(function() t = tostring(nm:GetStateText()) end)
    if t == TARGET then
      log('row ' .. i .. ' ' .. t); r:SimulateClick()
      local ok = B.find_shown('button_ok', 'load-save_game') or B.find('button_ok', 'load-save_game')
      log('ok state ' .. tostring(ok:CurrentState())); ok:SimulateClick(); log('clicked ok'); return true
    end
  end
  log('target not in list (' .. lb:ChildCount() .. ' rows)'); return false
end
FS_LOADING = true
scripting.AddEventCallBack('ComponentLClickUp', function(ctx)
  if not FS_LOADING then return end
  local s = ''; pcall(function() s = ctx.string end)
  if s == 'button_load' then FS_LOADING = false; log('event button_load'); pcall(try_load) end
end)
log('armed load ' .. TARGET)
B.click('button_menu'); B.click('button_load')
return 'sent'
