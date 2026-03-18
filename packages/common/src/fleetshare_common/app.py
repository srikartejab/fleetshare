from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fleetshare_common.settings import get_settings


def create_app(title: str, description: str) -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=title, description=description, version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health():
        return {"service": settings.service_name, "status": "ok"}

    return app

