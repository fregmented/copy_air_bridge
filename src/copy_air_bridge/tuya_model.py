from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


Access = Literal["ro", "rw"]
DataType = Literal["bool", "enum", "value"]
ValueType = Literal["int", "float"]


@dataclass(frozen=True)
class DataPoint:
    id: int
    code: str
    access: Access
    type: DataType
    minimum: int | float | None = None
    maximum: int | float | None = None
    step: int | float | None = None
    values: tuple[str, ...] = ()
    value_type: ValueType = "int"

    @property
    def writable(self) -> bool:
        return self.access == "rw"


DATA_POINTS: dict[str, DataPoint] = {
    "switch": DataPoint(1, "switch", "rw", "bool"),
    "temp_current": DataPoint(2, "temp_current", "ro", "value", 10, 45, 1),
    "temp_set": DataPoint(5, "temp_set", "rw", "value", 16, 32, 1),
    "mode": DataPoint(7, "mode", "rw", "enum", values=("Auto", "Colding", "Dehmidify", "Wind", "Save")),
    "fan_speed_enum": DataPoint(9, "fan_speed_enum", "rw", "enum", values=("auto", "low", "middle", "high")),
    "child_lock": DataPoint(11, "child_lock", "rw", "bool"),
    "on_time": DataPoint(101, "on_time", "rw", "value", 0, 24, 1),
    "stop_time": DataPoint(102, "stop_time", "rw", "value", 0, 24, 1),
    "turbo": DataPoint(103, "turbo", "rw", "bool"),
    "sleepfunc": DataPoint(104, "sleepfunc", "rw", "bool"),
    "swing1": DataPoint(105, "swing1", "rw", "enum", values=("stop", "leftright", "updown", "all")),
    "light": DataPoint(106, "light", "rw", "bool"),
    "currenterror": DataPoint(107, "currenterror", "ro", "value", 0, 99, 1),
    "motiondetector": DataPoint(108, "motiondetector", "ro", "value", 0, 1, 1),
    "humidity": DataPoint(109, "humidity", "ro", "value", 0, 100, 1),
    "humidityset": DataPoint(110, "humidityset", "rw", "value", 35, 70, 5),
}


def status_to_codes(status: dict[str, Any]) -> dict[str, Any]:
    dps = status.get("dps")
    if not isinstance(dps, dict):
        return status

    coded_status = {code: status[code] for code in DATA_POINTS if code in status}
    for code, data_point in DATA_POINTS.items():
        value = dps.get(str(data_point.id), dps.get(data_point.id))
        if value is not None:
            coded_status[code] = value
    return coded_status


def normalize_command_value(code: str, value: Any) -> Any:
    data_point = DATA_POINTS[code]

    if data_point.type != "value":
        return value

    if data_point.value_type == "int":
        if isinstance(value, bool):
            return value
        try:
            converted_float = float(value)
        except (TypeError, ValueError):
            return value
        if converted_float.is_integer():
            return int(converted_float)
        return value

    if data_point.value_type == "float":
        if isinstance(value, bool):
            return value
        try:
            return float(value)
        except (TypeError, ValueError):
            return value

    return value


def validate_command(code: str, value: Any) -> DataPoint:
    data_point = DATA_POINTS[code]
    value = normalize_command_value(code, value)

    if not data_point.writable:
        raise ValueError(f"{code} is read-only")
    if data_point.type == "bool" and not isinstance(value, bool):
        raise ValueError(f"{code} must be a boolean")
    if data_point.type == "enum" and value not in data_point.values:
        raise ValueError(f"{code} must be one of {', '.join(data_point.values)}")
    if data_point.type == "value":
        if data_point.value_type == "int" and (isinstance(value, bool) or not isinstance(value, int)):
            raise ValueError(f"{code} must be an integer")
        if data_point.value_type == "float" and (isinstance(value, bool) or not isinstance(value, float)):
            raise ValueError(f"{code} must be a float")
        if data_point.minimum is not None and value < data_point.minimum:
            raise ValueError(f"{code} must be greater than or equal to {data_point.minimum}")
        if data_point.maximum is not None and value > data_point.maximum:
            raise ValueError(f"{code} must be less than or equal to {data_point.maximum}")
        if data_point.step is not None and data_point.minimum is not None and (value - data_point.minimum) % data_point.step != 0:
            raise ValueError(f"{code} must use step {data_point.step}")

    return data_point
