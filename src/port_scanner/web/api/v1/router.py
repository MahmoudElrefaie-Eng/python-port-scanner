"""Aggregator for all ``/api/v1`` routes.

Empty as of Milestone 1, which only establishes the versioning scaffold.
Future endpoint modules (e.g. ``api/v1/endpoints/scan.py``) register
themselves here via ``api_router.include_router(...)`` — mounting this
router under a version prefix now means adding v1 endpoints later never
requires touching ``app.py`` again.
"""

from fastapi import APIRouter

api_router = APIRouter()
