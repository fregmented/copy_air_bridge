local capabilities = require "st.capabilities"
local Driver = require "st.driver"
local log = require "log"
local socket = require "cosock.socket"
local http = require "cosock.socket.http"
local ltn12 = require "ltn12"
local json = require "dkjson"

local mappings = require "tuya_mappings"

local SSDP_ADDRESS = "239.255.255.250"
local SSDP_PORT = 1900
local SSDP_SERVICE_TYPE = "urn:schemas-upnp-org:device:CopyAirBridge:1"
local BRIDGE_LOCATION_FIELD = "bridge_location"

local function trim(value)
  return (value:gsub("^%s+", ""):gsub("%s+$", ""))
end

local function header_value(response, name)
  local lower_name = name:lower()
  for line in response:gmatch("([^\r\n]+)") do
    local header_name, value = line:match("^([^:]+):%s*(.*)$")
    if header_name ~= nil and header_name:lower() == lower_name then
      return trim(value)
    end
  end
  return nil
end

local function discover_bridge_location(should_continue)
  local udp = assert(socket.udp())
  udp:settimeout(1)
  udp:setsockname("*", 0)
  local search = table.concat({
    "M-SEARCH * HTTP/1.1",
    "HOST: " .. SSDP_ADDRESS .. ":" .. SSDP_PORT,
    "MAN: \"ssdp:discover\"",
    "MX: 1",
    "ST: " .. SSDP_SERVICE_TYPE,
    "",
    "",
  }, "\r\n")

  local ok, error_message = udp:sendto(search, SSDP_ADDRESS, SSDP_PORT)
  if not ok then
    udp:close()
    log.warn(string.format("SSDP search failed: %s", tostring(error_message)))
    return nil
  end

  local deadline = socket.gettime() + 3
  while socket.gettime() < deadline do
    if should_continue ~= nil and not should_continue() then
      break
    end

    local response = udp:receivefrom()
    if response ~= nil then
      local service_type = header_value(response, "ST") or header_value(response, "NT")
      local location = header_value(response, "LOCATION")
      if service_type == SSDP_SERVICE_TYPE and location ~= nil then
        udp:close()
        return location
      end
    end
  end

  udp:close()
  return nil
end

local function bridge_base_url(device, force_discovery)
  local location = device:get_field(BRIDGE_LOCATION_FIELD)
  if force_discovery or location == nil then
    location = discover_bridge_location()
    if location ~= nil then
      device:set_field(BRIDGE_LOCATION_FIELD, location, { persist = true })
    end
  end
  return location
end

local function command_arg(command, ...)
  local args = command.args or {}
  for _, name in ipairs({ ... }) do
    if args[name] ~= nil then
      return args[name]
    end
  end
  return args[1]
end

local function request_json_from_url(base_url, method, path, body)
  local response_body = {}
  local body_text = body and json.encode(body) or nil
  local _, status = http.request({
    url = base_url .. path,
    method = method,
    headers = {
      ["Content-Type"] = "application/json",
      ["Content-Length"] = body_text and tostring(#body_text) or "0",
    },
    source = body_text and ltn12.source.string(body_text) or nil,
    sink = ltn12.sink.table(response_body),
  })

  local response_text = table.concat(response_body)
  if status ~= 200 then
    log.warn(string.format("bridge request failed: %s %s -> %s %s", method, path, tostring(status), response_text))
    return nil
  end

  if response_text == "" then
    return {}
  end
  return json.decode(response_text)
end

local function request_json(device, method, path, body)
  local base_url = bridge_base_url(device)
  if base_url == nil then
    log.warn("Copy Air Bridge server was not found via SSDP")
    return nil
  end

  local result = request_json_from_url(base_url, method, path, body)
  if result ~= nil then
    return result
  end

  log.warn("cached Copy Air Bridge location failed; rediscovering via SSDP")
  local rediscovered_base_url = bridge_base_url(device, true)
  if rediscovered_base_url == nil or rediscovered_base_url == base_url then
    return nil
  end
  return request_json_from_url(rediscovered_base_url, method, path, body)
end

local function emit_status(device, status)
  if status.switch ~= nil then
    device:emit_event(status.switch and capabilities.switch.switch.on() or capabilities.switch.switch.off())
  end
  if status.temp_current ~= nil then
    device:emit_event(capabilities.temperatureMeasurement.temperature({ value = status.temp_current, unit = "C" }))
  end
  if status.temp_set ~= nil then
    device:emit_event(capabilities.thermostatCoolingSetpoint.coolingSetpoint({ value = status.temp_set, unit = "C" }))
  end
  if status.humidity ~= nil then
    device:emit_event(capabilities.relativeHumidityMeasurement.humidity(status.humidity))
  end
  if status.mode ~= nil then
    local mode = mappings.mode_values[status.mode]
    if mode ~= nil then
      device:emit_event(capabilities.airConditionerMode.airConditionerMode(mode))
    end
  end
  if status.fan_speed_enum ~= nil then
    local fan_mode = mappings.fan_mode_values[status.fan_speed_enum]
    if fan_mode ~= nil then
      device:emit_event(capabilities.airConditionerFanMode.fanMode(fan_mode))
    end
  end
end

local function refresh_handler(driver, device)
  log.info(string.format("refresh requested for %s", device.label or device.id))
  local status = request_json(device, "GET", "/status")
  if status ~= nil then
    emit_status(device, status)
  end
end

local function switch_handler(driver, device, command)
  local tuya_code = mappings.capability_to_tuya.switch
  local value = command.command == capabilities.switch.commands.on.NAME
  log.info(string.format("set %s to %s", tuya_code, tostring(value)))
  local status = request_json(device, "POST", "/commands/" .. tuya_code, { value = value })
  if status ~= nil then
    emit_status(device, status)
  end
end

local function cooling_setpoint_handler(driver, device, command)
  local tuya_code = mappings.capability_to_tuya.thermostatCoolingSetpoint
  local value = command_arg(command, "setpoint", "value")
  log.info(string.format("set %s to %s", tuya_code, tostring(value)))
  local status = request_json(device, "POST", "/commands/" .. tuya_code, { value = value })
  if status ~= nil then
    emit_status(device, status)
  end
end

local function air_conditioner_mode_handler(driver, device, command)
  local tuya_code = mappings.capability_to_tuya.airConditionerMode
  local requested_mode = command_arg(command, "mode", "airConditionerMode", "value")
  local tuya_mode = mappings.air_conditioner_mode_values[requested_mode]
  if tuya_mode == nil then
    log.warn(string.format("unsupported air conditioner mode: %s", tostring(requested_mode)))
    return
  end
  log.info(string.format("set %s to %s", tuya_code, tuya_mode))
  local status = request_json(device, "POST", "/commands/" .. tuya_code, { value = tuya_mode })
  if status ~= nil then
    emit_status(device, status)
  end
end

local function fan_mode_handler(driver, device, command)
  local tuya_code = mappings.capability_to_tuya.airConditionerFanMode
  local requested_fan_mode = command_arg(command, "fanMode", "mode", "value")
  local tuya_fan_mode = mappings.smartthings_fan_mode_values[requested_fan_mode]
  if tuya_fan_mode == nil then
    log.warn(string.format("unsupported fan mode: %s", tostring(requested_fan_mode)))
    return
  end
  log.info(string.format("set %s to %s", tuya_code, tuya_fan_mode))
  local status = request_json(device, "POST", "/commands/" .. tuya_code, { value = tuya_fan_mode })
  if status ~= nil then
    emit_status(device, status)
  end
end

local function discovery_handler(driver, _, should_continue)
  if should_continue ~= nil and not should_continue() then
    return
  end
  local location = discover_bridge_location(should_continue)
  if location == nil then
    log.warn("Copy Air Bridge server was not discovered via SSDP")
    return
  end

  driver:try_create_device({
    type = "LAN",
    device_network_id = "copy-air-bridge",
    label = "Tuya Air Conditioner",
    profile = "air-conditioner",
    manufacturer = "Copy Air Bridge",
    model = "Tuya eh1sso Air Conditioner",
    vendor_provided_label = "Tuya Air Conditioner",
    data = {
      bridge_location = location,
    },
  })
end

local function device_added(driver, device)
  if device.data ~= nil and device.data.bridge_location ~= nil then
    device:set_field(BRIDGE_LOCATION_FIELD, device.data.bridge_location, { persist = true })
  end
end

local copy_air_bridge = Driver("copy-air-bridge", {
  discovery = discovery_handler,
  lifecycle_handlers = {
    added = device_added,
    init = device_added,
  },
  capability_handlers = {
    [capabilities.refresh.ID] = {
      [capabilities.refresh.commands.refresh.NAME] = refresh_handler,
    },
    [capabilities.switch.ID] = {
      [capabilities.switch.commands.on.NAME] = switch_handler,
      [capabilities.switch.commands.off.NAME] = switch_handler,
    },
    [capabilities.thermostatCoolingSetpoint.ID] = {
      [capabilities.thermostatCoolingSetpoint.commands.setCoolingSetpoint.NAME] = cooling_setpoint_handler,
    },
    [capabilities.airConditionerMode.ID] = {
      [capabilities.airConditionerMode.commands.setAirConditionerMode.NAME] = air_conditioner_mode_handler,
    },
    [capabilities.airConditionerFanMode.ID] = {
      [capabilities.airConditionerFanMode.commands.setFanMode.NAME] = fan_mode_handler,
    },
  },
})

copy_air_bridge:run()
