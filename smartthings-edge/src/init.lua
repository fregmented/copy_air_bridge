local capabilities = require "st.capabilities"
local Driver = require "st.driver"
local log = require "log"

local mappings = require "tuya_mappings"

local function refresh_handler(driver, device)
  log.info(string.format("refresh requested for %s", device.label or device.id))
  -- TODO: Query the Python bridge /status endpoint and emit mapped events.
end

local function switch_handler(driver, device, command)
  local tuya_code = mappings.capability_to_tuya.switch
  log.info(string.format("set %s to %s", tuya_code, command.command))
  -- TODO: POST the translated command to /commands/switch.
end

local copy_air_bridge = Driver("copy-air-bridge", {
  capability_handlers = {
    [capabilities.refresh.ID] = {
      [capabilities.refresh.commands.refresh.NAME] = refresh_handler,
    },
    [capabilities.switch.ID] = {
      [capabilities.switch.commands.on.NAME] = switch_handler,
      [capabilities.switch.commands.off.NAME] = switch_handler,
    },
  },
})

copy_air_bridge:run()
