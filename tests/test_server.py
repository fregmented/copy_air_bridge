from __future__ import annotations

import asyncio
import logging
import unittest
from unittest.mock import Mock, patch

from starlette.requests import Request

from copy_air_bridge.config import Settings, SsdpSettings, TuyaDeviceSettings
from copy_air_bridge.server import build_root_description, configure_logging, create_app, format_request_log


class ServerTest(unittest.TestCase):
    def create_test_app(self):
        settings = Settings(tuya=TuyaDeviceSettings(device_id="device", local_key="key", host="192.0.2.10"))
        air_conditioner = Mock()
        with patch("copy_air_bridge.server.load_settings", return_value=settings):
            with patch("copy_air_bridge.server.TuyaAirConditioner", return_value=air_conditioner):
                return create_app(), air_conditioner

    def test_redoc_endpoint_is_configured(self) -> None:
        app, _ = self.create_test_app()

        routes = {route.path for route in app.routes}

        self.assertEqual(app.redoc_url, "/redoc")
        self.assertIn("/redoc", routes)

    def test_swagger_endpoint_is_configured(self) -> None:
        app, _ = self.create_test_app()

        routes = {route.path for route in app.routes}

        self.assertEqual(app.docs_url, "/docs")
        self.assertIn("/docs", routes)

    def test_openapi_schema_is_available_for_redoc(self) -> None:
        app, _ = self.create_test_app()

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

    def test_air_conditioner_state_is_refreshed_during_app_lifespan(self) -> None:
        settings = Settings(tuya=TuyaDeviceSettings(device_id="device", local_key="key", host="192.0.2.10"))
        air_conditioner = Mock()
        with patch("copy_air_bridge.server.load_settings", return_value=settings):
            with patch("copy_air_bridge.server.TuyaAirConditioner", return_value=air_conditioner):
                with patch("copy_air_bridge.server.STATE_REFRESH_INTERVAL_SECONDS", 0.01):
                    app = create_app()

                    async def run_lifespan() -> None:
                        async with app.router.lifespan_context(app):
                            await asyncio.sleep(0.02)

                    asyncio.run(run_lifespan())

        self.assertGreaterEqual(air_conditioner.status.call_count, 1)

    def test_current_th_endpoint_returns_temperature_and_humidity(self) -> None:
        app, air_conditioner = self.create_test_app()
        route = next(route for route in app.routes if route.path == "/current-th")
        air_conditioner.get_current_th.return_value = {"temp_current": 23, "humidity": 48}

        self.assertEqual(route.endpoint(), {"temp_current": 23, "humidity": 48})
        air_conditioner.get_current_th.assert_called_once_with()

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

    def test_request_log_format_contains_request_and_response_information(self) -> None:
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/health",
                "query_string": b"verbose=true",
                "headers": [(b"host", b"testserver")],
                "client": ("192.0.2.30", 12345),
                "scheme": "http",
                "server": ("testserver", 80),
            }
        )

        log_output = format_request_log(request, 200, 12.345)

        self.assertEqual(log_output, "HTTP GET /health?verbose=true from=192.0.2.30 status=200 duration=12.35ms")

    def test_request_log_format_contains_error_status_information(self) -> None:
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/commands/unknown",
                "query_string": b"",
                "headers": [(b"host", b"testserver")],
                "client": ("192.0.2.30", 12345),
                "scheme": "http",
                "server": ("testserver", 80),
            }
        )

        log_output = format_request_log(request, 404, 1.2)

        self.assertEqual(log_output, "HTTP POST /commands/unknown from=192.0.2.30 status=404 duration=1.20ms")


if __name__ == "__main__":
    unittest.main()