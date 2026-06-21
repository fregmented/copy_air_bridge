from __future__ import annotations

import asyncio
import logging
import unittest
from unittest.mock import Mock, patch

from copy_air_bridge.config import Settings, SsdpSettings, TuyaDeviceSettings
from copy_air_bridge.server import build_root_description, configure_logging, create_app


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

    def test_root_description_contains_upnp_device_metadata(self) -> None:
        xml = build_root_description(
            "192.0.2.20",
            8080,
            "urn:schemas-upnp-org:device:CopyAirBridge:1",
            "uuid:copy-air-bridge::urn:schemas-upnp-org:device:CopyAirBridge:1",
        )

        self.assertIn("<deviceType>urn:schemas-upnp-org:device:CopyAirBridge:1</deviceType>", xml)
        self.assertIn("<friendlyName>Copy Air Bridge</friendlyName>", xml)
        self.assertIn("<UDN>uuid:copy-air-bridge</UDN>", xml)
        self.assertIn("<URLBase>http://192.0.2.20:8080</URLBase>", xml)

    def test_ssdp_advertiser_runs_during_app_lifespan(self) -> None:
        settings = Settings(
            ssdp=SsdpSettings(interface="192.0.2.20"),
            tuya=TuyaDeviceSettings(device_id="device", local_key="key", host="192.0.2.10"),
        )
        advertiser = Mock()
        with patch("copy_air_bridge.server.load_settings", return_value=settings):
            with patch("copy_air_bridge.server.TuyaAirConditioner", return_value=Mock()):
                with patch("copy_air_bridge.server.SsdpAdvertiser", return_value=advertiser):
                    app = create_app()

                    async def run_lifespan() -> None:
                        async with app.router.lifespan_context(app):
                            pass

                    asyncio.run(run_lifespan())

        advertiser.start.assert_called_once_with()
        advertiser.stop.assert_called_once_with()

    def test_ssdp_advertiser_receives_configured_interface(self) -> None:
        settings = Settings(
            ssdp=SsdpSettings(interface="192.0.2.20"),
            tuya=TuyaDeviceSettings(device_id="device", local_key="key", host="192.0.2.10"),
        )
        with patch("copy_air_bridge.server.load_settings", return_value=settings):
            with patch("copy_air_bridge.server.TuyaAirConditioner", return_value=Mock()):
                with patch("copy_air_bridge.server.SsdpAdvertiser") as advertiser_class:
                    create_app()

        self.assertEqual(advertiser_class.call_args.kwargs["interface"], "192.0.2.20")

    def test_configure_logging_enables_application_info_logs(self) -> None:
        logger = logging.getLogger("copy_air_bridge")
        original_level = logger.level
        original_handlers = logger.handlers[:]
        try:
            logger.handlers.clear()

            configure_logging()

            self.assertEqual(logger.level, logging.INFO)
            self.assertEqual(len(logger.handlers), 1)
        finally:
            logger.handlers[:] = original_handlers
            logger.setLevel(original_level)


if __name__ == "__main__":
    unittest.main()