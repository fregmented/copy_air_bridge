from __future__ import annotations

from typing import Any

import tinytuya

from copy_air_bridge.config import TuyaDeviceSettings
from copy_air_bridge.tuya_model import validate_command


class TuyaAirConditioner:
    def __init__(self, settings: TuyaDeviceSettings) -> None:
        self._device = tinytuya.Device(settings.device_id, settings.host, settings.local_key)
        self._device.set_version(settings.version)

    def status(self) -> dict[str, Any]:
        return self._device.status()

    def set_value(self, code: str, value: Any) -> dict[str, Any]:
        data_point = validate_command(code, value)
        return self._device.set_value(data_point.id, value)
