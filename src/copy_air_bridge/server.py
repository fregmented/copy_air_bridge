from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from copy_air_bridge.config import DEFAULT_SETTINGS_PATH, load_settings
from copy_air_bridge.ssdp import SsdpAdvertisement, SsdpAdvertiser, build_location
from copy_air_bridge.state_machine import NotSupportedActionError
from copy_air_bridge.tuya_client import TuyaAirConditioner
from copy_air_bridge.tuya_model import DATA_POINTS


LOGGER = logging.getLogger("copy_air_bridge")


def build_root_description(settings_host: str, settings_port: int, service_type: str, unique_service_name: str) -> str:
    base_url = build_location(settings_host, settings_port).removesuffix("/rootDesc.xml")
    udn = unique_service_name.split("::", 1)[0]
    return f"""<?xml version="1.0"?>
<root xmlns="urn:schemas-upnp-org:device-1-0">
  <specVersion>
    <major>1</major>
    <minor>0</minor>
  </specVersion>
  <URLBase>{base_url}</URLBase>
  <device>
    <deviceType>{service_type}</deviceType>
    <friendlyName>Copy Air Bridge</friendlyName>
    <manufacturer>copy-air-bridge</manufacturer>
    <modelName>Copy Air Bridge</modelName>
    <modelNumber>0.1</modelNumber>
    <UDN>{udn}</UDN>
  </device>
</root>
"""


class CommandRequest(BaseModel):
    value: Any


def create_app() -> FastAPI:
    settings = load_settings(DEFAULT_SETTINGS_PATH)
    air_conditioner = TuyaAirConditioner(settings.tuya)
    ssdp_advertiser = None
    if settings.ssdp.enabled:
        ssdp_advertiser = SsdpAdvertiser(
            SsdpAdvertisement(
                service_type=settings.ssdp.service_type,
                location=build_location(settings.bridge.host, settings.bridge.port),
                server=settings.ssdp.server,
                unique_service_name=settings.ssdp.unique_service_name,
                notify_interval_seconds=settings.ssdp.notify_interval_seconds,
            ),
            interface=settings.ssdp.interface,
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if ssdp_advertiser is not None:
            ssdp_advertiser.start()
        try:
            yield
        finally:
            if ssdp_advertiser is not None:
                ssdp_advertiser.stop()

    app = FastAPI(title="Copy Air Bridge", docs_url="/docs", redoc_url="/redoc", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/rootDesc.xml", response_class=Response)
    def root_description() -> Response:
        return Response(
            content=build_root_description(
                settings.bridge.host,
                settings.bridge.port,
                settings.ssdp.service_type,
                settings.ssdp.unique_service_name,
            ),
            media_type="application/xml",
        )

    @app.get("/model")
    def model() -> dict[str, dict[str, Any]]:
        return {code: data_point.__dict__ for code, data_point in DATA_POINTS.items()}

    @app.get("/status")
    def status() -> dict[str, Any]:
        return air_conditioner.status()

    @app.get("/buttons")
    def buttons() -> dict[str, list[str]]:
        return {"buttons": air_conditioner.available_buttons()}

    @app.post("/commands/{code}")
    def command(code: str, request: CommandRequest) -> dict[str, Any]:
        if code not in DATA_POINTS:
            raise HTTPException(status_code=404, detail=f"Unknown data point: {code}")
        try:
            return air_conditioner.set_value(code, request.value)
        except NotSupportedActionError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    return app


def configure_logging() -> None:
    LOGGER.setLevel(logging.INFO)
    if LOGGER.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s:     %(message)s"))
    LOGGER.addHandler(handler)


def main() -> None:
    configure_logging()
    settings = load_settings(DEFAULT_SETTINGS_PATH)
    uvicorn.run("copy_air_bridge.server:create_app", factory=True, host=settings.bridge.host, port=settings.bridge.port)
