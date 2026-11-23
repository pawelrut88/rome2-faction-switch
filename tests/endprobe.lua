local function log(s) local g = io.open("fs_evlog.txt", "a"); g:write(s .. "\n"); g:flush(); g:close() end
scripting.game_interface:disable_end_turn(true)
scripting.AddEventCallBack('ComponentLClickUp', function(ctx)
  local s = ''; pcall(function() s = ctx.string end)
  if s == 'button_end_turn' then log('END TURN CLICKED while disabled') end
end)
local b = B.find_shown('button_end_turn'); local st = ''; pcall(function() st = tostring(b:CurrentState()) end)
log('end turn state after disable: ' .. st)
return 'state=' .. st
