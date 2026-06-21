from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


DEFAULT_SETTINGS_PATH = Path("data/settings.yaml")


class TuyaDeviceSettings(BaseModel):
    device_id: str = Field(..., min_length=1)
    local_key: str = Field(..., min_length=1)
    host: str = Field(..., min_length=1)
    version: float = 3.4


class BridgeSettings(BaseModel):
    host: str = "0.0.0.0"
    port: int = Field(default=8080, ge=1, le=65535)


class SsdpSettings(BaseModel):
    enabled: bool = True
    interface: str | None = None
    service_type: str = "urn:schemas-upnp-org:device:CopyAirBridge:1"
    unique_service_name: str = "uuid:copy-air-bridge::urn:schemas-upnp-org:device:CopyAirBridge:1"
    server: str = "CopyAirBridge/0.1 UPnP/1.1"
    notify_interval_seconds: int = Field(default=30, ge=1)


class Settings(BaseModel):
    bridge: BridgeSettings = Field(default_factory=BridgeSettings)
    ssdp: SsdpSettings = Field(default_factory=SsdpSettings)
    tuya: TuyaDeviceSettings


def load_settings(path: Path = DEFAULT_SETTINGS_PATH) -> Settings:
    with path.open("r", encoding="utf-8") as settings_file:
        raw_settings: dict[str, Any] = yaml.safe_load(settings_file) or {}
    return Settings.model_validate(raw_settings)
