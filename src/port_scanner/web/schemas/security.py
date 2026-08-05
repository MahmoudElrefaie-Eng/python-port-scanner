"""Response/view models for the Security Engine's output, rendered by both
the server-rendered HTML pages (``results.html``) and the JSON API
(``web/api/v1/endpoints/security.py``).

Milestone 5 wires up the vulnerability assessment module only
(``security.engine.assess()``); these view models are named generically —
``HostView``, not ``AssessmentView`` — for the same reason
``web/services/security_service.py`` is, per DECISIONS.md 34: future
Security Engine modules (SSL/TLS, HTTP headers, DNS enumeration, WHOIS,
technology detection, ...) are expected to attach their own findings to
this same shape without a rename.
"""

from __future__ import annotations

from pydantic import BaseModel

from port_scanner.security.models import RiskLevel
from port_scanner.web.schemas.scan import (
    DEFAULT_PORT_SPEC,
    DEFAULT_TIMEOUT,
    DEFAULT_WORKERS,
)


class AssessmentRequest(BaseModel):
    """JSON request body for ``POST /api/v1/assessments`` — scan `target`
    over `ports`, then assess whatever's found for known vulnerabilities.

    Mirrors the same fields (and, via `scan_service.run_scan`, the same
    validation bounds — see DECISIONS.md 17) as the HTML scan form; this
    is a second caller of that shared logic, not a separate copy of it.
    """

    target: str
    ports: str = DEFAULT_PORT_SPEC
    timeout: float = float(DEFAULT_TIMEOUT)
    workers: int = int(DEFAULT_WORKERS)


class VulnerabilityView(BaseModel):
    """A CVE record, as reported by a provider — mirrors
    ``security.models.Vulnerability``."""

    cve_id: str
    description: str
    cvss_score: float | None
    cvss_version: str | None
    fixed_version: str | None
    references: list[str]
    source: str


class FindingView(BaseModel):
    """One ``VulnerabilityView`` matched against one service — mirrors
    ``security.models.Finding``."""

    vulnerability: VulnerabilityView
    matched_product: str
    matched_version: str | None
    confidence: str
    risk_level: RiskLevel
    recommendation: str


class ServiceAssessmentView(BaseModel):
    """One open port's security assessment: what's running on it, its
    risk level, and any matched vulnerabilities — mirrors
    ``security.models.Service``."""

    port: int
    state: str
    service_name: str
    banner: str
    risk_level: RiskLevel
    findings: list[FindingView]


class HostView(BaseModel):
    """A scanned target's full security assessment — mirrors
    ``security.models.Host``, kept as a separate (Pydantic, not dataclass)
    type so the web layer's response shape can evolve independently of the
    Security Engine's internal representation (same reasoning as
    ``PortResultView`` vs. ``discovery.PortResult`` — see
    ``schemas/scan.py``)."""

    target: str
    risk_level: RiskLevel
    services: list[ServiceAssessmentView]
