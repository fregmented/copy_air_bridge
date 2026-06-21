from __future__ import annotations

import unittest

from copy_air_bridge.cli import format_data_point, parse_value
from copy_air_bridge.tuya_model import DATA_POINTS, validate_command


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


if __name__ == "__main__":
    unittest.main()