from __future__ import annotations

import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

from copy_air_bridge.cli import AirBridgeShell, DeviceUnavailableError, create_air_conditioner, format_data_point, format_status, main, parse_value
from copy_air_bridge.config import Settings, TuyaDeviceSettings
from copy_air_bridge.state_machine import NotSupportedActionError
from copy_air_bridge.tuya_model import DATA_POINTS, normalize_command_value, validate_command


class CliTest(unittest.TestCase):
    def test_cli_model_supports_all_agent_data_points(self) -> None:
        self.assertEqual(
            set(DATA_POINTS),
            {
                "switch",
                "temp_current",
                "temp_set",
                "mode",
                "fan_speed_enum",
                "child_lock",
                "on_time",
                "stop_time",
                "turbo",
                "sleepfunc",
                "swing1",
                "light",
                "currenterror",
                "motiondetector",
                "humidity",
                "humidityset",
            },
        )

        for code, data_point in DATA_POINTS.items():
            formatted = format_data_point(data_point)
            self.assertIn(f"code={code}", formatted)
            self.assertIn(f"id={data_point.id}", formatted)

    def test_parse_value_for_writable_data_points(self) -> None:
        examples = [
            ("switch", "on", True),
            ("switch", "false", False),
            ("temp_set", "24", 24),
            ("mode", "Colding", "Colding"),
            ("fan_speed_enum", "middle", "middle"),
            ("swing1", "all", "all"),
            ("humidityset", "55", 55),
        ]
        for code, raw_value, expected in examples:
            with self.subTest(code=code, raw_value=raw_value):
                value = parse_value(DATA_POINTS[code], raw_value)
                self.assertEqual(value, expected)
                validate_command(code, value)

    def test_read_only_data_points_are_not_writable(self) -> None:
        examples = [
            ("temp_current", "25"),
            ("currenterror", "0"),
            ("motiondetector", "1"),
            ("humidity", "40"),
        ]
        for code, raw_value in examples:
            with self.subTest(code=code, raw_value=raw_value):
                value = parse_value(DATA_POINTS[code], raw_value)
                with self.assertRaisesRegex(ValueError, "read-only"):
                    validate_command(code, value)

    def test_convertible_integer_data_point_values_are_normalized(self) -> None:
        examples = [
            ("temp_set", "24", 24),
            ("temp_set", "24.0", 24),
            ("temp_set", 24.0, 24),
            ("humidityset", "55", 55),
        ]
        for code, value, expected in examples:
            with self.subTest(code=code, value=value):
                normalized = normalize_command_value(code, value)
                self.assertEqual(normalized, expected)
                validate_command(code, normalized)

    def test_non_integral_values_are_rejected_for_integer_data_points(self) -> None:
        examples = [
            ("temp_set", "24.5"),
            ("temp_set", 24.5),
        ]
        for code, value in examples:
            with self.subTest(code=code, value=value):
                normalized = normalize_command_value(code, value)
                with self.assertRaisesRegex(ValueError, "integer"):
                    validate_command(code, normalized)

    def test_invalid_cli_values_are_rejected(self) -> None:
        examples = [
            ("switch", "maybe", "boolean"),
            ("temp_set", "cold", "integer"),
            ("mode", "Cooling", "one of"),
            ("humidityset", "52", "step"),
        ]
        for code, raw_value, message in examples:
            with self.subTest(code=code, raw_value=raw_value):
                with self.assertRaisesRegex(ValueError, message):
                    value = parse_value(DATA_POINTS[code], raw_value)
                    validate_command(code, value)

    def test_format_status_uses_data_point_names(self) -> None:
        self.assertEqual(
            format_status({"dps": {"1": True, "2": 26, "7": "Colding"}}),
            "| name         | dp | state   |\n"
            "| ------------ | -- | ------- |\n"
            "| switch       | 1  | True    |\n"
            "| temp_current | 2  | 26      |\n"
            "| mode         | 7  | Colding |",
        )

    def test_status_command_prints_formatted_status(self) -> None:
        air_conditioner = Mock()
        air_conditioner.status.return_value = {"dps": {"1": True, "5": 24}}

        with patch("sys.stdout", new_callable=StringIO) as stdout:
            AirBridgeShell(air_conditioner).do_status("")

        self.assertEqual(
            stdout.getvalue(),
            "| name     | dp | state |\n"
            "| -------- | -- | ----- |\n"
            "| switch   | 1  | True  |\n"
            "| temp_set | 5  | 24    |\n",
        )

    def test_get_command_polls_and_prints_current_state(self) -> None:
        air_conditioner = Mock()
        air_conditioner.status.return_value = {"dps": {"5": 24}}

        with patch("sys.stdout", new_callable=StringIO) as stdout:
            AirBridgeShell(air_conditioner).do_get("temp_set")

        air_conditioner.status.assert_called_once_with()
        self.assertEqual(
            stdout.getvalue(),
            "id=5 | code=temp_set | access=rw | type=value | range=16-32 | step=1\n"
            "state=24\n",
        )

    def test_set_command_prints_not_supported_error_without_crashing(self) -> None:
        air_conditioner = Mock()
        air_conditioner.set_value.side_effect = NotSupportedActionError("temp_set is not supported in the current device state")

        with patch("sys.stdout", new_callable=StringIO) as stdout:
            AirBridgeShell(air_conditioner).do_set("temp_set 24")

        air_conditioner.set_value.assert_called_once_with("temp_set", 24)
        self.assertEqual(stdout.getvalue(), "Not supported: temp_set is not supported in the current device state\n")

    def test_create_air_conditioner_checks_availability_on_startup(self) -> None:
        settings_path = Path("data/settings.yaml")
        settings = Settings(tuya=TuyaDeviceSettings(device_id="device", local_key="key", host="192.0.2.10"))
        air_conditioner = Mock()

        with patch("copy_air_bridge.cli.load_settings", return_value=settings) as load_settings:
            with patch("copy_air_bridge.cli.TuyaAirConditioner", return_value=air_conditioner) as air_conditioner_class:
                self.assertIs(create_air_conditioner(settings_path), air_conditioner)

        load_settings.assert_called_once_with(settings_path)
        air_conditioner_class.assert_called_once_with(settings.tuya)
        air_conditioner.check_availability.assert_called_once_with()

    def test_create_air_conditioner_reports_availability_failure(self) -> None:
        settings = Settings(tuya=TuyaDeviceSettings(device_id="device", local_key="key", host="192.0.2.10"))
        air_conditioner = Mock()
        air_conditioner.check_availability.side_effect = OSError("network unreachable")

        with patch("copy_air_bridge.cli.load_settings", return_value=settings):
            with patch("copy_air_bridge.cli.TuyaAirConditioner", return_value=air_conditioner):
                with self.assertRaisesRegex(DeviceUnavailableError, "Failed to connect to Tuya device"):
                    create_air_conditioner(Path("data/settings.yaml"))

    def test_main_exits_without_traceback_when_device_is_unavailable(self) -> None:
        with patch("copy_air_bridge.cli.create_air_conditioner", side_effect=DeviceUnavailableError("unavailable")):
            with patch("sys.argv", ["copy-air-cli"]):
                with self.assertRaisesRegex(SystemExit, "unavailable"):
                    main()


if __name__ == "__main__":
    unittest.main()