local mappings = {}

mappings.writable_capabilities = {
  switch = true,
  thermostatCoolingSetpoint = true,
  airConditionerMode = true,
  airConditionerFanMode = true,
}

mappings.capability_to_tuya = {
  switch = "switch",
  thermostatCoolingSetpoint = "temp_set",
  temperatureMeasurement = "temp_current",
  relativeHumidityMeasurement = "humidity",
  airConditionerMode = "mode",
  airConditionerFanMode = "fan_speed_enum",
}

mappings.tuya_to_capability = {
  switch = "switch",
  temp_set = "thermostatCoolingSetpoint",
  temp_current = "temperatureMeasurement",
  humidity = "relativeHumidityMeasurement",
  mode = "airConditionerMode",
  fan_speed_enum = "airConditionerFanMode",
}

mappings.mode_values = {
  Auto = "Auto",
  Colding = "Cooling",
  Dehmidify = "Dehumid",
  Wind = "Fan",
  Save = "Eco",
}

mappings.air_conditioner_mode_values = {
  Auto = { mode = "Auto", sleepfunc = false, turbo = false },
  Cooling = { mode = "Colding", sleepfunc = false, turbo = false },
  Dehumid = { mode = "Dehmidify", sleepfunc = false, turbo = false },
  Fan = { mode = "Wind", sleepfunc = false, turbo = false },
  Eco = { mode = "Save", sleepfunc = false, turbo = false },
  Silent = { mode = "Colding", sleepfunc = true, turbo = false },
  Power = { mode = "Colding", sleepfunc = false, turbo = true },
}

mappings.air_conditioner_modes = { "Auto", "Cooling", "Dehumid", "Fan", "Eco", "Silent", "Power" }

mappings.fan_modes = { "Auto", "Low", "Mid", "High" }

mappings.auto_only_fan_modes = { "Auto" }

mappings.fan_mode_values = {
  auto = "Auto",
  low = "Low",
  middle = "Mid",
  high = "High",
}

mappings.smartthings_fan_mode_values = {
  Auto = "auto",
  Low = "low",
  Mid = "middle",
  High = "high",
}

return mappings
