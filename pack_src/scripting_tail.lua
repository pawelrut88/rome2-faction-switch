-- ===== faction-switch (everything above is CA's vanilla campaigns/main_rome/scripting.lua, unchanged) =====
do
	local ok, err = pcall(require, "data.lua_scripts.fs_switch")
	if not ok then
		local f = io.open("faction_switch\\fs_switch_error.txt", "a") or io.open("fs_switch_error.txt", "a")
		if f then f:write(os.date("%H:%M:%S ") .. tostring(err) .. "\n"); f:close() end
	end
end
