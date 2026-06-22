from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from copy_air_bridge.tuya_model import DATA_POINTS


LOGGER = logging.getLogger("copy_air_bridge")


class NotSupportedActionError(ValueError):
    pass


class DeviceStateMachine:
    def __init__(self, state: Mapping[str, Any], previous_state: Mapping[str, Any] | None = None) -> None:
        self._previous_state = self._normalize_state(previous_state or {})
        self._state = self._normalize_state(state)
        LOGGER.info("Device state updated:\n%s", self.format_state_table())

    @property
    def state(self) -> Mapping[str, Any]:
        return self._state

    def validate_action(self, code: str, value: Any) -> None:
        if not self.is_action_supported(code, value):
            raise NotSupportedActionError(f"{code} is not supported in the current device state")

    def available_buttons(self) -> list[str]:
        return [code for code, data_point in DATA_POINTS.items() if data_point.writable and self.is_action_supported(code, True)]

    def get_current_th(self) -> dict[str, Any]:
        return {"temp_current": self._state.get("temp_current"), "humidity": self._state.get("humidity")}

    def format_state_table(self) -> str:
        table_rows = [("dp", "name", "state(old)", "state(new)")]
        for code, data_point in DATA_POINTS.items():
            table_rows.append(
                (
                    str(data_point.id),
                    data_point.code,
                    self._format_state_value(self._previous_state.get(code)),
                    self._format_state_value(self._state.get(code)),
                )
            )

        column_widths = [max(len(row[index]) for row in table_rows) for index in range(len(table_rows[0]))]
        rows = [self._format_table_row(table_rows[0], column_widths), self._format_table_row(tuple("-" * width for width in column_widths), column_widths)]
        rows.extend(self._format_table_row(row, column_widths) for row in table_rows[1:])
        return "\n".join(rows)

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

    @staticmethod
    def _format_state_value(value: Any) -> str:
        if value is True:
            return "true"
        if value is False:
            return "false"
        if value is None:
            return ""
        return str(value)

    @staticmethod
    def _format_table_row(values: tuple[str, ...], column_widths: list[int]) -> str:
        cells = [value.ljust(width) for value, width in zip(values, column_widths, strict=True)]
        return f"| {' | '.join(cells)} |"