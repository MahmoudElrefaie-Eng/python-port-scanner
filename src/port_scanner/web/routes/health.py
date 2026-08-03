"""Liveness/readiness probe.

Deliberately outside ``/api/v1``: load balancers and orchestrators (e.g. a
Kubernetes liveness probe) hit this on a fixed, version-independent path,
and its contract should stay stable across API version bumps.
"""

from fastapi import APIRouter, Request

from port_scanner.web.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Liveness check")
async def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )
