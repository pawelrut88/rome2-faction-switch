local m=scripting.game_interface:model(); local f=m:world():faction_by_key('rom_carthage'); local cl=f:character_list(); local t={}
for i=0,cl:num_items()-1 do local c=cl:item_at(i); t[#t+1]=c:cqi()..'@'..c:logical_position_x()..','..c:logical_position_y() end
return 'turn='..m:turn_number()..' treasury='..f:treasury()..' '..table.concat(t,' ')
