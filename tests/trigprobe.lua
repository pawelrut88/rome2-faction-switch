local function log(s) local g = io.open("fs_evlog.txt", "a"); g:write(s .. "\n"); g:flush(); g:close() end
for _, ev in ipairs({'ComponentLClickUp', 'ComponentMouseOn'}) do
  scripting.AddEventCallBack(ev, function(ctx)
    local s = ''; pcall(function() s = ctx.string end)
    if ev == 'ComponentLClickUp' or s:find('end_turn') or s:find('chat') then log(ev .. ' ' .. s) end
  end)
end
scripting.game_interface:disable_end_turn(true)
local b = B.find_shown('button_end_turn'); local st = ''; pcall(function() st = tostring(b:CurrentState()) end)
log('armed; end turn state ' .. st)
return st
