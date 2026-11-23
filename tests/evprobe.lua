local f = io.open("fs_evlog.txt", "w"); f:write("start\n"); f:close()
local function log(s) local g = io.open("fs_evlog.txt", "a"); g:write(s .. "\n"); g:flush(); g:close() end
local function rows()
  local lb = B.find_shown('list_box', 'load-save_game') or B.find('list_box', 'load-save_game')
  if not lb then return 'nolist' end
  local n = lb:ChildCount(); local t = {'n=' .. n}
  for i = 0, math.min(n, 3) - 1 do
    local r = B.U(lb:Find(i)); local s = {}
    local function w(c, d) if d > 3 then return end; local x = ''; pcall(function() x = tostring(c:GetStateText() or '') end)
      s[#s+1] = tostring(c:Id()) .. '=' .. x; for j = 0, c:ChildCount() - 1 do w(B.U(c:Find(j)), d + 1) end end
    w(r, 0); t[#t+1] = table.concat(s, ' | ')
  end
  return table.concat(t, '\n')
end
FS_ROWS = rows
for _, ev in ipairs({'PanelOpenedCampaign', 'ComponentLClickUp', 'ComponentMouseOn'}) do
  scripting.AddEventCallBack(ev, function(ctx)
    local s = ''; pcall(function() s = ctx.string end)
    log(ev .. ' ' .. tostring(s) .. ' ' .. rows())
  end)
end
return 'armed'
