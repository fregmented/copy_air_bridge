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
local STATUS_POLL_INTERVAL_SECONDS = 60
local STATUS_POLL_TIMER_FIELD = "status_poll_timer"
local request_sequence = 0

local function device_name(device)
  if device == nil then
    return "<nil device>"
  end
  return string.format("%s (%s)", tostring(device.label or "<no label>"), tostring(device.id or "<no id>"))
end

local function log_table(prefix, value)
  local encoded = json.encode(value)
  log.info(string.format("%s: %s", prefix, tostring(encoded)))
end

local function next_request_id()
  request_sequence = request_sequence + 1
  return request_sequence
end

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

local function bridge_api_base_url(location)
  if location == nil then
    return nil
  end
  return (location:gsub("/rootDesc%.xml%s*$", ""))
end

local function discover_bridge_location(should_continue)
  log.info(string.format("SSDP discovery started: service=%s address=%s port=%s", SSDP_SERVICE_TYPE, SSDP_ADDRESS, tostring(SSDP_PORT)))
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
      log.info("SSDP discovery stopped by SmartThings runtime")
      break
    end

    local response, ip, port = udp:receivefrom()
    if response ~= nil then
      local service_type = header_value(response, "ST") or header_value(response, "NT")
      local location = header_value(response, "LOCATION")
      log.info(string.format(
        "SSDP response received: ip=%s port=%s service=%s location=%s",
        tostring(ip),
        tostring(port),
        tostring(service_type),
        tostring(location)
      ))
      if service_type == SSDP_SERVICE_TYPE and location ~= nil then
        udp:close()
        log.info(string.format("SSDP bridge matched: location=%s base_url=%s", location, bridge_api_base_url(location)))
        return bridge_api_base_url(location)
      end
    end
  end

  udp:close()
  log.warn("SSDP discovery timed out without matching Copy Air Bridge response")
  return nil
end

local function bridge_base_url(device, force_discovery)
  local location = device:get_field(BRIDGE_LOCATION_FIELD)
  log.info(string.format(
    "bridge location lookup: device=%s cached=%s force_discovery=%s",
    device_name(device),
    tostring(location),
    tostring(force_discovery)
  ))
  if force_discovery or location == nil then
    location = discover_bridge_location()
    if location ~= nil then
      device:set_field(BRIDGE_LOCATION_FIELD, location, { persist = true })
      log.info(string.format("bridge location persisted: device=%s location=%s", device_name(device), location))
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

local function request_json_from_url(base_url, method, path, body, reason)
  local response_body = {}
  local body_text = body and json.encode(body) or nil
  local request_id = next_request_id()
  local url = base_url .. path
  log.info(string.format(
    "bridge server request #%s started: reason=%s method=%s url=%s body=%s",
    tostring(request_id),
    tostring(reason or "unspecified"),
    method,
    url,
    tostring(body_text)
  ))
  local _, status = http.request({
    url = url,
    method = method,
    headers = {
      ["Content-Type"] = "application/json",
      ["Content-Length"] = body_text and tostring(#body_text) or "0",
    },
    source = body_text and ltn12.source.string(body_text) or nil,
    sink = ltn12.sink.table(response_body),
  })

  local response_text = table.concat(response_body)
  log.info(string.format(
    "bridge server request #%s completed: method=%s url=%s status=%s body=%s",
    tostring(request_id),
    method,
    url,
    tostring(status),
    response_text
  ))
  if status ~= 200 then
    log.warn(string.format(
      "bridge server request #%s failed: method=%s url=%s status=%s body=%s",
      tostring(request_id),
      method,
      url,
      tostring(status),
      response_text
    ))
    return nil
  end

  if response_text == "" then
    return {}
  end
  local decoded, position, decode_error = json.decode(response_text)
  if decoded == nil then
    log.warn(string.format("bridge response JSON decode failed: %s %s position=%s error=%s body=%s", method, path, tostring(position), tostring(decode_error), response_text))
  end
  return decoded
end

local function request_json(device, method, path, body, reason)
  local base_url = bridge_base_url(device)
  if base_url == nil then
    log.warn("Copy Air Bridge server was not found via SSDP")
    return nil
  end

  local result = request_json_from_url(base_url, method, path, body, reason)
  if result ~= nil then
    return result
  end

  log.warn("cached Copy Air Bridge location failed; rediscovering via SSDP")
  local rediscovered_base_url = bridge_base_url(device, true)
  if rediscovered_base_url == nil or rediscovered_base_url == base_url then
    return nil
  end
  return request_json_from_url(rediscovered_base_url, method, path, body, (reason or "unspecified") .. " retry")
end

local function emit_supported_air_conditioner_modes(device)
  device:emit_event(capabilities.airConditionerMode.supportedAcModes(mappings.air_conditioner_modes))
  device:emit_event(capabilities.airConditionerMode.availableAcModes(mappings.air_conditioner_modes))
end

local function emit_fan_modes(device, air_conditioner_mode)
  device:emit_event(capabilities.airConditionerFanMode.supportedAcFanModes(mappings.fan_modes))
  if air_conditioner_mode == "Auto" or air_conditioner_mode == "Silent" or air_conditioner_mode == "Power" then
    device:emit_event(capabilities.airConditionerFanMode.availableAcFanModes(mappings.auto_only_fan_modes))
  else
    device:emit_event(capabilities.airConditionerFanMode.availableAcFanModes(mappings.fan_modes))
  end
end

local function air_conditioner_mode_from_status(status)
  if status.mode == "Colding" then
    if status.sleepfunc == true then
      return "Silent"
    end
    if status.turbo == true then
      return "Power"
    end
  end
  return mappings.mode_values[status.mode]
end

local function emit_status(device, status)
  log_table(string.format("emitting status for %s", device_name(device)), status)
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
    local mode = air_conditioner_mode_from_status(status)
    if mode ~= nil then
      device:emit_event(capabilities.airConditionerMode.airConditionerMode(mode))
      emit_fan_modes(device, mode)
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
  local status = request_json(device, "GET", "/status", nil, "refresh status")
  if status ~= nil then
    emit_status(device, status)
  end
end

local function start_status_polling(driver, device)
  if device:get_field(STATUS_POLL_TIMER_FIELD) ~= nil then
    log.info(string.format("status polling already scheduled: device=%s interval=%ss", device_name(device), tostring(STATUS_POLL_INTERVAL_SECONDS)))
    return
  end

  log.info(string.format("status polling scheduled: device=%s interval=%ss", device_name(device), tostring(STATUS_POLL_INTERVAL_SECONDS)))
  local timer = device.thread:call_on_schedule(
    STATUS_POLL_INTERVAL_SECONDS,
    function()
      log.info(string.format("status polling requested for %s", device_name(device)))
      refresh_handler(driver, device)
    end,
    "copy-air-bridge-status-poll"
  )
  device:set_field(STATUS_POLL_TIMER_FIELD, timer)
end

local function switch_handler(driver, device, command)
  local tuya_code = mappings.capability_to_tuya.switch
  local value = command.command == capabilities.switch.commands.on.NAME
  log.info(string.format("set %s to %s", tuya_code, tostring(value)))
  local status = request_json(device, "POST", "/commands/" .. tuya_code, { value = value }, "set " .. tuya_code)
  if status ~= nil then
    emit_status(device, status)
  end
end

local function cooling_setpoint_handler(driver, device, command)
  local tuya_code = mappings.capability_to_tuya.thermostatCoolingSetpoint
  local value = command_arg(command, "setpoint", "value")
  log.info(string.format("set %s to %s", tuya_code, tostring(value)))
  local status = request_json(device, "POST", "/commands/" .. tuya_code, { value = value }, "set " .. tuya_code)
  if status ~= nil then
    emit_status(device, status)
  end
end

local function air_conditioner_mode_handler(driver, device, command)
  local requested_mode = command_arg(command, "mode", "airConditionerMode", "value")
  local tuya_values = mappings.air_conditioner_mode_values[requested_mode]
  if tuya_values == nil then
    log.warn(string.format("unsupported air conditioner mode: %s", tostring(requested_mode)))
    return
  end

  local status = request_json(device, "GET", "/status", nil, "read status before setting air conditioner mode")
  if status == nil then
    return
  end

  local command_order = { "mode", "sleepfunc", "turbo" }
  if requested_mode == "Auto" then
    command_order = { "sleepfunc", "turbo", "mode" }
  end
  for _, tuya_code in ipairs(command_order) do
    local value = tuya_values[tuya_code]
    if status[tuya_code] == value then
      log.info(string.format("skip %s; already %s", tuya_code, tostring(value)))
      goto continue
    end
    log.info(string.format("set %s to %s", tuya_code, tostring(value)))
    status = request_json(device, "POST", "/commands/" .. tuya_code, { value = value }, "set " .. tuya_code)
    if status == nil then
      return
    end
    ::continue::
  end
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
  local status = request_json(device, "POST", "/commands/" .. tuya_code, { value = tuya_fan_mode }, "set " .. tuya_code)
  if status ~= nil then
    emit_status(device, status)
  end
end

local function discovery_handler(driver, _, should_continue)
  log.info("SmartThings discovery handler started")
  if should_continue ~= nil and not should_continue() then
    log.info("SmartThings discovery handler stopped before SSDP search")
    return
  end
  local location = discover_bridge_location(should_continue)
  if location == nil then
    log.warn("Copy Air Bridge server was not discovered via SSDP")
    return
  end

  local create_device_message = {
    type = "LAN",
    device_network_id = "copy-air-bridge",
    label = "Tuya Air Conditioner",
    profile = "air-conditioner",
    manufacturer = "Copy Air Bridge",
    model = "Tuya eh1sso Air Conditioner",
    vendor_provided_label = "Tuya Air Conditioner",
    data = location,
  }
  log_table("trying to create SmartThings device", create_device_message)
  local success, result = pcall(driver.try_create_device, driver, create_device_message)
  if success then
    log.info(string.format("SmartThings try_create_device completed: result=%s", tostring(result)))
  else
    log.error(string.format("SmartThings try_create_device failed: error=%s", tostring(result)))
  end
end

local function device_added(driver, device)
  log.info(string.format("device lifecycle invoked: device=%s dni=%s", device_name(device), tostring(device.device_network_id)))
  emit_supported_air_conditioner_modes(device)
  emit_fan_modes(device, nil)
  start_status_polling(driver, device)
  local should_refresh = false
  if device.data ~= nil then
    local bridge_location = device.data
    if type(device.data) == "table" then
      bridge_location = device.data.bridge_location
    end
    local base_url = bridge_api_base_url(bridge_location)
    if base_url ~= nil then
      log.info(string.format("device lifecycle bridge data found: raw=%s base_url=%s", tostring(bridge_location), tostring(base_url)))
      device:set_field(BRIDGE_LOCATION_FIELD, base_url, { persist = true })
      log.info(string.format("device lifecycle bridge location persisted: device=%s location=%s", device_name(device), tostring(base_url)))
      should_refresh = true
    end
  end

  local cached_location = device:get_field(BRIDGE_LOCATION_FIELD)
  if cached_location ~= nil then
    log.info(string.format("device lifecycle bridge location already cached: device=%s location=%s", device_name(device), tostring(cached_location)))
    should_refresh = true
  else
    log.warn(string.format("device lifecycle has no bridge location data: device=%s", device_name(device)))
  end
  if should_refresh then
    refresh_handler(driver, device)
  end
end

local copy_air_bridge = Driver("copy-air-bridge", {
  discovery = discovery_handler,
  lifecycle_handlers = {
    added = device_added,
    init = device_added,
    infoChanged = device_added,
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
