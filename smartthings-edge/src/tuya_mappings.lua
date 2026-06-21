local mappings = {}

mappings.capability_to_tuya = {
  switch = "switch",
  thermostatCoolingSetpoint = "temp_set",
  temperatureMeasurement = "temp_current",
  relativeHumidityMeasurement = "humidity",
  airConditionerMode = "mode",
  fanSpeed = "fan_speed_enum",
}

mappings.tuya_to_capability = {
  switch = "switch",
  temp_set = "thermostatCoolingSetpoint",
  temp_current = "temperatureMeasurement",
  humidity = "relativeHumidityMeasurement",
  mode = "airConditionerMode",
  fan_speed_enum = "fanSpeed",
}

mappings.mode_values = {
  Auto = "auto",
  Colding = "cool",
  Dehmidify = "dry",
  Wind = "fanOnly",
  Save = "eco",
}

mappings.fan_speed_values = {
  auto = "auto",
  low = "low",
  middle = "medium",
  high = "high",
}

return mappings
