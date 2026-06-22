from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from copy_air_bridge.tuya_model import DATA_POINTS


class NotSupportedActionError(ValueError):
    pass


class DeviceStateMachine:
    def __init__(self, state: Mapping[str, Any]) -> None:
        self._state = self._normalize_state(state)

    def validate_action(self, code: str, value: Any) -> None:
        if not self.is_action_supported(code, value):
            raise NotSupportedActionError(f"{code} is not supported in the current device state")

    def available_buttons(self) -> list[str]:
        return [code for code, data_point in DATA_POINTS.items() if data_point.writable and self.is_action_supported(code, True)]

    def get_current_th(self) -> dict[str, Any]:
        return {"temp_current": self._state.get("temp_current"), "humidity": self._state.get("humidity")}

    def is_action_supported(self, code: str, value: Any | None = None) -> bool:
        if code not in DATA_POINTS or not DATA_POINTS[code].writable:
            return False

        if self._state.get("switch") is False:
            return code == "switch" and value is True

        mode = self._state.get("mode")
        if code == "temp_set":
            return mode == "Colding"
        if code in {"fan_speed_enum", "turbo"}:
            return mode != "Auto"
        if code == "humidityset":
            return mode == "Dehmidify"

        return True

    @staticmethod
    def _normalize_state(state: Mapping[str, Any]) -> Mapping[str, Any]:
        dps = state.get("dps")
        if not isinstance(dps, Mapping):
            return state

        normalized = dict(state)
        for code, data_point in DATA_POINTS.items():
            value = dps.get(str(data_point.id), dps.get(data_point.id))
            if value is not None:
                normalized[code] = value
        return normalized