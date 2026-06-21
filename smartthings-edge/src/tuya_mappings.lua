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
  Auto = "auto",
  Colding = "cool",
  Dehmidify = "dry",
  Wind = "fanOnly",
  Save = "eco",
}

mappings.air_conditioner_mode_values = {
  auto = "Auto",
  cool = "Colding",
  dry = "Dehmidify",
  fanOnly = "Wind",
  eco = "Save",
}

mappings.fan_mode_values = {
  auto = "auto",
  low = "low",
  middle = "medium",
  high = "high",
}

mappings.smartthings_fan_mode_values = {
  auto = "auto",
  low = "low",
  medium = "middle",
  high = "high",
}

return mappings
