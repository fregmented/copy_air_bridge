from __future__ import annotations

from typing import Any

import tinytuya

from copy_air_bridge.config import TuyaDeviceSettings
from copy_air_bridge.state_machine import DeviceStateMachine
from copy_air_bridge.tuya_model import status_to_codes, validate_command


class TuyaAirConditioner:
    def __init__(self, settings: TuyaDeviceSettings) -> None:
        self._device = tinytuya.Device(settings.device_id, settings.host, settings.local_key)
        self._device.set_version(settings.version)
        self._state_machine = DeviceStateMachine({})

    def status(self) -> dict[str, Any]:
        status = self._device.status()
        self.update_state(status)
        return status_to_codes(status)

    def update_state(self, state: dict[str, Any]) -> None:
        self._state_machine = DeviceStateMachine(state, self._state_machine.state)

    def check_availability(self) -> dict[str, Any]:
        return self.status()

    def available_buttons(self) -> list[str]:
        return self._state_machine.available_buttons()

    def get_current_th(self) -> dict[str, Any]:
        return self._state_machine.get_current_th()

    def set_value(self, code: str, value: Any) -> dict[str, Any]:
        data_point = validate_command(code, value)
        self._state_machine.validate_action(code, value)
        response = self._device.set_value(data_point.id, value)
        self.update_state(response)
        return status_to_codes(response)
