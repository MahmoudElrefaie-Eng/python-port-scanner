"""JSON API for the Security Engine.

``POST /assessments`` (mounted under `settings.api_v1_prefix`, so
`/api/v1/assessments`) is a programmatic counterpart to the HTML scan
form's "Assess for known vulnerabilities" checkbox
(`routes/pages.py`) — it scans `target` and runs vulnerability
assessment over the result, returning a `HostView` as JSON instead of a
rendered page.

Named `security.py`, not `assessment.py` or `vulnerability.py`, for the
same reason `web/services/security_service.py` is (DECISIONS.md 34):
future Security Engine modules are expected to add their own routes here
rather than to a module named after just one of them.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from port_scanner.web.schemas.scan import ScanFormData
from port_scanner.web.schemas.security import AssessmentRequest, HostView
from port_scanner.web.services import security_service
from port_scanner.web.services.scan_service import ScanFormError, run_scan

router = APIRouter(tags=["security"])


@router.post(
    "/assessments",
    response_model=HostView,
    summary="Scan a target and assess it for known vulnerabilities",
)
def create_assessment(payload: AssessmentRequest) -> HostView:
    """Scan `payload.target` over `payload.ports`, then run vulnerability
    assessment over whatever's found. Reuses `scan_service.run_scan` (and
    therefore its input bounds — see DECISIONS.md 17) rather than calling
    `discovery.discover` directly, so this endpoint enforces the same
    per-request limits the HTML form does.
    """
    form = ScanFormData(
        target=payload.target,
        ports=payload.ports,
        timeout=str(payload.timeout),
        workers=str(payload.workers),
    )

    try:
        result = run_scan(form)
    except ScanFormError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    return security_service.run_assessment(result.target, result.results)
