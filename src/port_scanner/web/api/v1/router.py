"""Aggregator for all ``/api/v1`` routes.

Empty from Milestone 1 through Milestone 4 — a pure versioning scaffold.
Milestone 5 adds the first endpoint module, ``endpoints/security.py``.
Future endpoint modules register themselves here via
``api_router.include_router(...)`` — mounting this router under a version
prefix from the start means adding v1 endpoints never requires touching
``app.py`` again.
"""

from fastapi import APIRouter

from port_scanner.web.api.v1.endpoints.security import router as security_router

api_router = APIRouter()
api_router.include_router(security_router)
