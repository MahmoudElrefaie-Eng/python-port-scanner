"""FastAPI application factory for the port-scanner web interface.

Run with: ``uvicorn port_scanner.web.app:app``
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles

from port_scanner.web.api.v1.router import api_router
from port_scanner.web.core.config import Settings, get_settings
from port_scanner.web.core.exceptions import register_exception_handlers
from port_scanner.web.core.logging import configure_logging
from port_scanner.web.core.templating import STATIC_DIR
from port_scanner.web.routes.health import router as health_router
from port_scanner.web.routes.pages import router as pages_router

DESCRIPTION = (
    "HTTP interface for the port-scanner engine. Wraps the same scan and "
    "port-spec-parsing core used by the `port-scanner` CLI behind a "
    "versioned REST API — see this project's ARCHITECTURE.md."
)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application.

    Accepts an optional ``settings`` override so tests (and, later,
    alternate deployments) can construct an app against a specific
    configuration without mutating process environment variables.
    """
    settings = settings or get_settings()
    configure_logging(settings)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=DESCRIPTION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.state.settings = settings

    register_exception_handlers(app)

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    app.include_router(health_router)
    app.include_router(pages_router)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        schema["info"]["contact"] = {"name": "Mahmoud Elrefaie"}
        schema["info"]["x-environment"] = settings.environment
        schema.setdefault(
            "tags",
            [
                {"name": "health", "description": "Liveness/readiness probes"},
                {"name": "pages", "description": "Server-rendered HTML pages (scan form and results)"},
            ],
        )
        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]

    return app


app = create_app()
