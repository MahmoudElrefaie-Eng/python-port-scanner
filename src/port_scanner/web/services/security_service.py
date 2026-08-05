"""Bridges ``web/`` to the Security Engine.

Named generically — not ``vulnerability_service.py`` or
``assessment_service.py`` — because this is the module every future
Security Engine capability (SSL/TLS analysis, HTTP header checks, DNS
enumeration, WHOIS, technology detection, ...) will be wired in through,
alongside vulnerability assessment. Milestone 5 wires up vulnerability
assessment only (``security.engine.assess()``); see DECISIONS.md 34 and
ARCHITECTURE.md's "``security/`` as a pluggable pipeline" section for the
intended shape of what comes next.

Deliberately does not re-scan the target. ``routes/pages.py`` already has
a completed ``ScanResultView`` from ``scan_service.run_scan()`` by the
time an assessment is requested; this module adapts that result's
``PortResultView`` list back into ``discovery.PortResult`` (a plain
4-field value copy — the two types carry identical fields, just on
opposite sides of the web/schema boundary) and hands it to
``security.engine.assess()``. That keeps the assessment based on the
exact ports the user was just shown, instead of a second, independent
scan that could disagree with the first (a port closing between the two,
for instance) and doubles the network cost against the target for no
benefit.
"""

from __future__ import annotations

from collections.abc import Sequence

from port_scanner.discovery import PortResult
from port_scanner.security.engine import assess
from port_scanner.security.models import Finding, Host, Service, Vulnerability
from port_scanner.web.schemas.scan import PortResultView
from port_scanner.web.schemas.security import (
    FindingView,
    HostView,
    ServiceAssessmentView,
    VulnerabilityView,
)


def run_assessment(target: str, results: Sequence[PortResultView]) -> HostView:
    """Run vulnerability assessment over `results` (as already produced by
    `scan_service.run_scan()`) and return a template/JSON-ready view.

    Unlike `scan_service.run_scan`, this never raises a user-facing
    validation error: `security.engine.assess()` already degrades a
    failed lookup (a network error, a locked cache) to "no findings" per
    service rather than raising (see DECISIONS.md 32) — there is no
    equivalent of `ScanFormError` needed here.
    """
    port_results = [
        PortResult(port=r.port, state=r.state, service=r.service, banner=r.banner)
        for r in results
    ]
    host = assess(target, port_results)
    return _to_view(host)


def _to_view(host: Host) -> HostView:
    return HostView(
        target=host.target,
        risk_level=host.risk_level,
        services=[_service_view(service) for service in host.services],
    )


def _service_view(service: Service) -> ServiceAssessmentView:
    return ServiceAssessmentView(
        port=service.port,
        state=service.state,
        service_name=service.service_name,
        banner=service.banner,
        risk_level=service.risk_level,
        findings=[_finding_view(finding) for finding in service.findings],
    )


def _finding_view(finding: Finding) -> FindingView:
    return FindingView(
        vulnerability=_vulnerability_view(finding.vulnerability),
        matched_product=finding.matched_product,
        matched_version=finding.matched_version,
        confidence=finding.confidence,
        risk_level=finding.risk_level,
        recommendation=finding.recommendation,
    )


def _vulnerability_view(vulnerability: Vulnerability) -> VulnerabilityView:
    return VulnerabilityView(
        cve_id=vulnerability.cve_id,
        description=vulnerability.description,
        cvss_score=vulnerability.cvss_score,
        cvss_version=vulnerability.cvss_version,
        fixed_version=vulnerability.fixed_version,
        references=list(vulnerability.references),
        source=vulnerability.source,
    )
