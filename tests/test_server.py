from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from copy_air_bridge.config import Settings, TuyaDeviceSettings
from copy_air_bridge.server import create_app


class ServerTest(unittest.TestCase):
    def create_test_app(self):
        settings = Settings(tuya=TuyaDeviceSettings(device_id="device", local_key="key", host="192.0.2.10"))
        with patch("copy_air_bridge.server.load_settings", return_value=settings):
            with patch("copy_air_bridge.server.TuyaAirConditioner", return_value=Mock()):
                return create_app()

    def test_redoc_endpoint_is_configured(self) -> None:
        app = self.create_test_app()

        routes = {route.path for route in app.routes}

        self.assertEqual(app.redoc_url, "/redoc")
        self.assertIn("/redoc", routes)

    def test_swagger_endpoint_is_configured(self) -> None:
        app = self.create_test_app()

        routes = {route.path for route in app.routes}

        self.assertEqual(app.docs_url, "/docs")
        self.assertIn("/docs", routes)

    def test_openapi_schema_is_available_for_redoc(self) -> None:
        app = self.create_test_app()

        schema = app.openapi()

        self.assertEqual(app.openapi_url, "/openapi.json")
        self.assertEqual(schema["info"]["title"], "Copy Air Bridge")


if __name__ == "__main__":
    unittest.main()