from __future__ import annotations

from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from copy_air_bridge.config import DEFAULT_SETTINGS_PATH, load_settings
from copy_air_bridge.state_machine import NotSupportedActionError
from copy_air_bridge.tuya_client import TuyaAirConditioner
from copy_air_bridge.tuya_model import DATA_POINTS


class CommandRequest(BaseModel):
    value: Any


def create_app() -> FastAPI:
    settings = load_settings(DEFAULT_SETTINGS_PATH)
    air_conditioner = TuyaAirConditioner(settings.tuya)
    app = FastAPI(title="Copy Air Bridge", docs_url="/docs", redoc_url="/redoc")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

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


def main() -> None:
    settings = load_settings(DEFAULT_SETTINGS_PATH)
    uvicorn.run("copy_air_bridge.server:create_app", factory=True, host=settings.bridge.host, port=settings.bridge.port)
