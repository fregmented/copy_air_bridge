from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from copy_air_bridge.config import TuyaDeviceSettings
from copy_air_bridge.state_machine import DeviceStateMachine, NotSupportedActionError
from copy_air_bridge.tuya_client import TuyaAirConditioner


class DeviceStateMachineTest(unittest.TestCase):
    def test_powered_off_device_only_allows_switch_on(self) -> None:
        state_machine = DeviceStateMachine({"switch": False, "mode": "Colding"})

        state_machine.validate_action("switch", True)
        self.assertEqual(state_machine.available_buttons(), ["switch"])

        blocked_examples = [
            ("switch", False),
            ("mode", "Auto"),
            ("temp_set", 24),
            ("fan_speed_enum", "middle"),
            ("turbo", True),
            ("humidityset", 55),
        ]
        for code, value in blocked_examples:
            with self.subTest(code=code, value=value):
                with self.assertRaises(NotSupportedActionError):
                    state_machine.validate_action(code, value)

    def test_temperature_can_only_be_set_in_colding_mode(self) -> None:
        DeviceStateMachine({"switch": True, "mode": "Colding"}).validate_action("temp_set", 24)

        for mode in ("Auto", "Dehmidify", "Wind", "Save"):
            with self.subTest(mode=mode):
                with self.assertRaises(NotSupportedActionError):
                    DeviceStateMachine({"switch": True, "mode": mode}).validate_action("temp_set", 24)

    def test_fan_speed_and_turbo_are_blocked_in_auto_mode(self) -> None:
        auto_state = DeviceStateMachine({"switch": True, "mode": "Auto"})

        for code, value in (("fan_speed_enum", "low"), ("turbo", True)):
            with self.subTest(code=code):
                with self.assertRaises(NotSupportedActionError):
                    auto_state.validate_action(code, value)

        wind_state = DeviceStateMachine({"switch": True, "mode": "Wind"})
        wind_state.validate_action("fan_speed_enum", "low")
        wind_state.validate_action("turbo", True)

    def test_humidity_set_can_only_be_set_in_dehmidify_mode(self) -> None:
        DeviceStateMachine({"switch": True, "mode": "Dehmidify"}).validate_action("humidityset", 55)

        for mode in ("Auto", "Colding", "Wind", "Save"):
            with self.subTest(mode=mode):
                with self.assertRaises(NotSupportedActionError):
                    DeviceStateMachine({"switch": True, "mode": mode}).validate_action("humidityset", 55)

    def test_available_buttons_reflect_current_state(self) -> None:
        self.assertEqual(DeviceStateMachine({"switch": False, "mode": "Colding"}).available_buttons(), ["switch"])

        self.assertEqual(
            DeviceStateMachine({"switch": True, "mode": "Auto"}).available_buttons(),
            ["switch", "mode", "child_lock", "on_time", "stop_time", "sleepfunc", "swing1", "light"],
        )
        self.assertEqual(
            DeviceStateMachine({"switch": True, "mode": "Colding"}).available_buttons(),
            [
                "switch",
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
            ],
        )
        self.assertIn("humidityset", DeviceStateMachine({"switch": True, "mode": "Dehmidify"}).available_buttons())

    def test_tinytuya_dps_status_is_normalized(self) -> None:
        state_machine = DeviceStateMachine({"dps": {"1": True, "7": "Colding"}})

        state_machine.validate_action("temp_set", 24)
        self.assertIn("temp_set", state_machine.available_buttons())

    def test_current_temperature_and_humidity_are_read_from_normalized_state(self) -> None:
        state_machine = DeviceStateMachine({"dps": {"2": 23, "109": 48}})

        self.assertEqual(state_machine.get_current_th(), {"temp_current": 23, "humidity": 48})

    def test_state_machine_formats_normalized_state_as_table(self) -> None:
        state_machine = DeviceStateMachine({"dps": {"1": False, "2": 23, "7": "Colding"}})

        self.assertEqual(
            state_machine.format_state_table().splitlines()[:5],
            [
                "| dp  | name           | state(old) | state(new) |",
                "| --- | -------------- | ---------- | ---------- |",
                "| 1   | switch         |            | false      |",
                "| 2   | temp_current   |            | 23         |",
                "| 5   | temp_set       |            |            |",
            ],
        )
        self.assertIn("| 7   | mode           |            | Colding    |", state_machine.format_state_table())

    def test_state_machine_formats_previous_state_as_table(self) -> None:
        state_machine = DeviceStateMachine(
            {"dps": {"1": True, "2": 24, "7": "Colding"}},
            {"dps": {"1": False, "2": 23, "7": "Auto"}},
        )

        table = state_machine.format_state_table()

        self.assertIn("| 1   | switch         | false      | true       |", table)
        self.assertIn("| 2   | temp_current   | 23         | 24         |", table)
        self.assertIn("| 7   | mode           | Auto       | Colding    |", table)

    def test_state_machine_logs_state_table_when_updated(self) -> None:
        with self.assertLogs("copy_air_bridge", level="INFO") as logs:
            DeviceStateMachine({"dps": {"1": False, "7": "Auto"}})

        self.assertIn("Device state updated:\n| dp  | name           | state(old) | state(new) |", logs.output[0])
        self.assertIn("| 1   | switch         |            | false      |", logs.output[0])
        self.assertIn("| 7   | mode           |            | Auto       |", logs.output[0])

    def test_tuya_client_updates_state_machine_from_status(self) -> None:
        device = Mock()
        device.status.return_value = {"dps": {"1": True, "7": "Colding"}}

        with patch("copy_air_bridge.tuya_client.tinytuya.Device", return_value=device):
            air_conditioner = TuyaAirConditioner(TuyaDeviceSettings(device_id="device", local_key="key", host="192.0.2.10"))

        self.assertEqual(air_conditioner.check_availability(), {"switch": True, "mode": "Colding"})
        self.assertIn("temp_set", air_conditioner.available_buttons())

    def test_tuya_client_returns_status_with_data_point_names(self) -> None:
        device = Mock()
        device.status.return_value = {"dps": {"1": True, "2": 23, "5": 24, "7": "Colding"}}

        with patch("copy_air_bridge.tuya_client.tinytuya.Device", return_value=device):
            air_conditioner = TuyaAirConditioner(TuyaDeviceSettings(device_id="device", local_key="key", host="192.0.2.10"))

        self.assertEqual(
            air_conditioner.status(),
            {"switch": True, "temp_current": 23, "temp_set": 24, "mode": "Colding"},
        )

    def test_tuya_client_updates_state_machine_from_set_response(self) -> None:
        device = Mock()
        device.status.side_effect = [
            {"dps": {"1": True, "7": "Auto"}},
            {"dps": {"1": True, "7": "Auto"}},
            {"dps": {"1": True, "7": "Colding"}},
        ]
        device.set_value.side_effect = [
            {"dps": {"7": "Colding"}},
            {"dps": {"5": 18}},
        ]

        with patch("copy_air_bridge.tuya_client.tinytuya.Device", return_value=device):
            air_conditioner = TuyaAirConditioner(TuyaDeviceSettings(device_id="device", local_key="key", host="192.0.2.10"))

        air_conditioner.check_availability()
        air_conditioner.set_value("mode", "Colding")
        air_conditioner.set_value("temp_set", 18)

        self.assertEqual(device.set_value.call_args_list[0].args, (7, "Colding"))
        self.assertEqual(device.set_value.call_args_list[1].args, (5, 18))

    def test_tuya_client_returns_set_response_with_data_point_names(self) -> None:
        device = Mock()
        device.status.return_value = {"dps": {"1": True, "7": "Colding"}}
        device.set_value.return_value = {"dps": {"5": 18}}

        with patch("copy_air_bridge.tuya_client.tinytuya.Device", return_value=device):
            air_conditioner = TuyaAirConditioner(TuyaDeviceSettings(device_id="device", local_key="key", host="192.0.2.10"))

        air_conditioner.check_availability()

        self.assertEqual(air_conditioner.set_value("temp_set", 18), {"temp_set": 18})

    def test_tuya_client_skips_unchanged_turbo_sleepfunc_and_mode_commands(self) -> None:
        device = Mock()
        device.status.return_value = {"dps": {"1": True, "7": "Colding", "103": True, "104": False}}

        with patch("copy_air_bridge.tuya_client.tinytuya.Device", return_value=device):
            air_conditioner = TuyaAirConditioner(TuyaDeviceSettings(device_id="device", local_key="key", host="192.0.2.10"))

        for code, value in (("turbo", True), ("sleepfunc", False), ("mode", "Colding")):
            with self.subTest(code=code):
                self.assertEqual(air_conditioner.set_value(code, value)[code], value)

        device.set_value.assert_not_called()

    def test_tuya_client_sends_changed_tracked_commands_after_status_refresh(self) -> None:
        device = Mock()
        device.status.return_value = {"dps": {"1": True, "7": "Colding", "103": False}}
        device.set_value.return_value = {"dps": {"103": True}}

        with patch("copy_air_bridge.tuya_client.tinytuya.Device", return_value=device):
            air_conditioner = TuyaAirConditioner(TuyaDeviceSettings(device_id="device", local_key="key", host="192.0.2.10"))

        self.assertEqual(air_conditioner.set_value("turbo", True), {"turbo": True})

        self.assertEqual(device.set_value.call_args.args, (103, True))

    def test_tuya_client_still_sends_unchanged_untracked_commands(self) -> None:
        device = Mock()
        device.status.return_value = {"dps": {"1": True, "7": "Colding", "106": True}}
        device.set_value.return_value = {"dps": {"106": True}}

        with patch("copy_air_bridge.tuya_client.tinytuya.Device", return_value=device):
            air_conditioner = TuyaAirConditioner(TuyaDeviceSettings(device_id="device", local_key="key", host="192.0.2.10"))

        self.assertEqual(air_conditioner.set_value("light", True), {"light": True})

        self.assertEqual(device.set_value.call_args.args, (106, True))


if __name__ == "__main__":
    unittest.main()