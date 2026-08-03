"""Server-rendered HTML pages: the scan form and its results.

Unversioned, like `routes/health.py` — these are the UI, not a JSON API
contract. A future JSON API for the same capability would live under
`/api/v1` instead, without touching these routes.
"""

from __future__ import annotations

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse

from port_scanner.web.core.templating import templates
from port_scanner.web.schemas.scan import (
    DEFAULT_PORT_SPEC,
    DEFAULT_TIMEOUT,
    DEFAULT_WORKERS,
    ScanFormData,
)
from port_scanner.web.services.scan_service import ScanFormError, run_scan

router = APIRouter(tags=["pages"])


@router.get("/", name="index", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request, name="index.html", context={"form": ScanFormData()}
    )


@router.post("/scan", name="submit_scan", response_class=HTMLResponse)
def submit_scan(
    request: Request,
    # Every field has a default, deliberately: this handler is the single
    # place that decides how bad input is reported, so FastAPI/Pydantic
    # must never short-circuit with their own JSON 422 for a missing
    # field — that would bypass the friendly HTML error path below.
    target: str = Form(""),
    ports: str = Form(DEFAULT_PORT_SPEC),
    timeout: str = Form(DEFAULT_TIMEOUT),
    workers: str = Form(DEFAULT_WORKERS),
) -> HTMLResponse:
    form = ScanFormData(target=target, ports=ports, timeout=timeout, workers=workers)

    try:
        result = run_scan(form)
    except ScanFormError as exc:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"form": form, "error": str(exc)},
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    return templates.TemplateResponse(
        request=request,
        name="results.html",
        context={"form": form, "result": result},
    )
