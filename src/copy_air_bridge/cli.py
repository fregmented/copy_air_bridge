from __future__ import annotations

import argparse
import cmd
import json
import shlex
from pathlib import Path
from typing import Any

from copy_air_bridge.config import DEFAULT_SETTINGS_PATH, load_settings
from copy_air_bridge.state_machine import NotSupportedActionError
from copy_air_bridge.tuya_client import TuyaAirConditioner
from copy_air_bridge.tuya_model import DATA_POINTS, DataPoint, normalize_command_value, validate_command


class DeviceUnavailableError(RuntimeError):
    pass


def parse_value(data_point: DataPoint, raw_value: str) -> Any:
    if data_point.type == "bool":
        normalized = raw_value.strip().lower()
        if normalized in {"1", "true", "on", "yes", "y"}:
            return True
        if normalized in {"0", "false", "off", "no", "n"}:
            return False
        raise ValueError(f"{data_point.code} must be a boolean")

    if data_point.type == "value":
        try:
            return int(raw_value, 10)
        except ValueError as error:
            raise ValueError(f"{data_point.code} must be an integer") from error

    return raw_value


def format_data_point(data_point: DataPoint) -> str:
    details = [
        f"id={data_point.id}",
        f"code={data_point.code}",
        f"access={data_point.access}",
        f"type={data_point.type}",
    ]
    if data_point.type == "value":
        details.append(f"range={data_point.minimum}-{data_point.maximum}")
        details.append(f"step={data_point.step}")
    if data_point.type == "enum":
        details.append(f"values={', '.join(data_point.values)}")
    return " | ".join(details)


def get_status_value(status: dict[str, Any], data_point: DataPoint) -> Any:
    dps = status.get("dps", status)
    return dps.get(str(data_point.id), dps.get(data_point.id))


def format_status(status: dict[str, Any]) -> str:
    dps = status.get("dps", status)
    id_to_data_point = {data_point.id: data_point for data_point in DATA_POINTS.values()}
    rows: list[tuple[str, int, Any]] = []

    for raw_dp, state in dps.items():
        dp = int(raw_dp)
        data_point = id_to_data_point[dp]
        rows.append((data_point.code, dp, state))

    rows.sort(key=lambda row: row[1])
    table_rows = [("name", "dp", "state"), *((name, str(dp), str(state)) for name, dp, state in rows)]
    widths = [max(len(row[column]) for row in table_rows) for column in range(3)]

    def format_row(row: tuple[str, str, str]) -> str:
        return "| " + " | ".join(value.ljust(widths[index]) for index, value in enumerate(row)) + " |"

    separator = "| " + " | ".join("-" * width for width in widths) + " |"
    return "\n".join([format_row(table_rows[0]), separator, *(format_row(row) for row in table_rows[1:])])


class AirBridgeShell(cmd.Cmd):
    intro = "Copy Air Bridge interactive CLI. Type help or ? to list commands."
    prompt = "copy-air> "

    def __init__(self, air_conditioner: TuyaAirConditioner) -> None:
        super().__init__()
        self.air_conditioner = air_conditioner

    def do_model(self, arg: str) -> None:
        """List all Tuya data points: model"""
        if arg.strip():
            print("Usage: model")
            return
        for data_point in DATA_POINTS.values():
            print(format_data_point(data_point))

    def do_status(self, arg: str) -> None:
        """Read device status from TinyTuya: status"""
        if arg.strip():
            print("Usage: status")
            return
        print(format_status(self.air_conditioner.status()))

    def do_get(self, arg: str) -> None:
        """Show model metadata for one data point: get <code>"""
        parts = shlex.split(arg)
        if len(parts) != 1:
            print("Usage: get <code>")
            return
        data_point = DATA_POINTS.get(parts[0])
        if data_point is None:
            print(f"Unknown data point: {parts[0]}")
            return
        print(format_data_point(data_point))
        print(f"state={get_status_value(self.air_conditioner.status(), data_point)}")

    def do_set(self, arg: str) -> None:
        """Set a writable data point value: set <code> <value>"""
        parts = shlex.split(arg)
        if len(parts) != 2:
            print("Usage: set <code> <value>")
            return

        code, raw_value = parts
        data_point = DATA_POINTS.get(code)
        if data_point is None:
            print(f"Unknown data point: {code}")
            return

        try:
            value = parse_value(data_point, raw_value)
            value = normalize_command_value(code, value)
            validate_command(code, value)
        except ValueError as error:
            print(f"Invalid value: {error}")
            return

        try:
            response = self.air_conditioner.set_value(code, value)
        except NotSupportedActionError as error:
            print(f"Not supported: {error}")
            return
        print(json.dumps(response, ensure_ascii=False, indent=2, sort_keys=True))

    def do_quit(self, arg: str) -> bool:
        """Exit the CLI: quit"""
        if arg.strip():
            print("Usage: quit")
            return False
        return True

    def do_exit(self, arg: str) -> bool:
        """Exit the CLI: exit"""
        return self.do_quit(arg)

    def do_EOF(self, arg: str) -> bool:
        print()
        return True

    def emptyline(self) -> None:
        return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interactive CLI for testing the Copy Air Bridge Python server logic.")
    parser.add_argument(
        "--settings",
        type=Path,
        default=DEFAULT_SETTINGS_PATH,
        help=f"Settings YAML path. Defaults to {DEFAULT_SETTINGS_PATH}",
    )
    return parser


def create_air_conditioner(settings_path: Path) -> TuyaAirConditioner:
    settings = load_settings(settings_path)
    air_conditioner = TuyaAirConditioner(settings.tuya)
    try:
        air_conditioner.check_availability()
    except Exception as error:
        raise DeviceUnavailableError(f"Failed to connect to Tuya device: {error}") from error
    return air_conditioner


def main() -> None:
    args = build_parser().parse_args()
    try:
        air_conditioner = create_air_conditioner(args.settings)
    except DeviceUnavailableError as error:
        raise SystemExit(str(error)) from error
    AirBridgeShell(air_conditioner).cmdloop()
