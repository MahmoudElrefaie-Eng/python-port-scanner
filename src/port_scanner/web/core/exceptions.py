"""Application-wide exception types and their global FastAPI handlers.

Two handlers are registered, deliberately leaving FastAPI's own defaults
for ``HTTPException`` and ``RequestValidationError`` untouched:

- ``AppError`` — base class for domain errors future endpoints will raise
  (e.g. a future auth or scan-job error) that should map to a specific
  HTTP status without every route implementing its own try/except.
- ``Exception`` — a last-resort safety net for genuinely unhandled bugs:
  logs the full traceback server-side and returns an opaque 500 to the
  client instead of leaking internals.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for application errors that map to an HTTP response."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = "Internal server error"

    def __init__(self, detail: str | None = None) -> None:
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the given FastAPI app."""

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(Exception)
    async def handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled exception on %s %s", request.method, request.url.path
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )
