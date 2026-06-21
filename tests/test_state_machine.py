from __future__ import annotations

import unittest

from copy_air_bridge.state_machine import DeviceStateMachine, NotSupportedActionError


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


if __name__ == "__main__":
    unittest.main()