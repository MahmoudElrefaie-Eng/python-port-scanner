"""Orchestrates the scanning core's output through the provider chain into
a structured `Host` result.

The single shared entrypoint for vulnerability assessment — mirrors
`discovery.discover()`'s role for scanning (see DECISIONS.md 29). Not yet
called by `cli.py` or `web/` (Milestone 4 scope is this engine only, see
ROADMAP.md); a future milestone wires it in, calling this exact function.
"""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor

from port_scanner.discovery import PortResult
from port_scanner.security import matching, risk
from port_scanner.security.matching import ProductVersion
from port_scanner.security.models import Finding, Host, Service, Vulnerability
from port_scanner.security.providers.base import VulnerabilityProvider
from port_scanner.security.providers.local_cve import LocalCVEProvider
from port_scanner.security.providers.nvd import NVDProvider


def assess(
    target: str,
    port_results: Sequence[PortResult],
    *,
    cache: VulnerabilityProvider | None = None,
    providers: Sequence[VulnerabilityProvider] | None = None,
    max_workers: int = 10,
) -> Host:
    """Assess `port_results` (as returned by `discovery.discover()`) for
    `target`, returning a `Host` with findings attached per `Service`.

    For each service: `cache` is tried first; only if it has nothing are
    `providers` queried, with their results merged and deduplicated by
    CVE ID (not simple first-wins — see DECISIONS.md 29). Any successful
    live-provider lookup is written back into `cache` if it supports
    that, so a repeat assessment of the same product/version is served
    from the cache without hitting the network again.

    Defaults to `LocalCVEProvider()` + `NVDProvider()` sharing that same
    local database — i.e. `assess(target, results)` with no further
    arguments works out of the box, using the network only when the local
    cache doesn't already have an answer. Pass `providers=()` for a
    strictly offline, cache-only assessment.
    """
    if cache is None:
        cache = LocalCVEProvider()
    if providers is None:
        cache_path = cache.db_path if isinstance(cache, LocalCVEProvider) else None
        providers = (NVDProvider(cache_db_path=cache_path),)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        services = list(
            executor.map(lambda pr: _assess_service(pr, cache, providers), port_results)
        )

    return Host(
        target=target,
        services=tuple(services),
        risk_level=risk.aggregate(service.risk_level for service in services),
    )


def _assess_service(
    port_result: PortResult,
    cache: VulnerabilityProvider,
    providers: Sequence[VulnerabilityProvider],
) -> Service:
    product_version = matching.normalize(port_result.service, port_result.banner)

    findings: tuple[Finding, ...] = ()
    if product_version is not None:
        vulnerabilities = _lookup(product_version.product, product_version.version, cache, providers)
        findings = tuple(_to_finding(vuln, product_version) for vuln in vulnerabilities)

    return Service(
        port=port_result.port,
        state=port_result.state,
        service_name=port_result.service,
        banner=port_result.banner,
        findings=findings,
        risk_level=risk.aggregate(f.risk_level for f in findings),
    )


def _lookup(
    product: str,
    version: str | None,
    cache: VulnerabilityProvider,
    providers: Sequence[VulnerabilityProvider],
) -> list[Vulnerability]:
    try:
        cached = cache.lookup(product, version)
    except Exception:
        cached = []
    if cached:
        return cached

    merged: dict[str, Vulnerability] = {}
    for provider in providers:
        try:
            for vulnerability in provider.lookup(product, version):
                merged.setdefault(vulnerability.cve_id, vulnerability)
        except Exception:
            continue  # one provider failing must not affect the others
    return list(merged.values())


def _to_finding(vulnerability: Vulnerability, product_version: ProductVersion) -> Finding:
    # A version range was only ever checked (by the provider) when a
    # version was actually parsed out of the banner — see matching.py and
    # DECISIONS.md 31. No version to check against means this is a
    # product-only match, not a confirmed one.
    confidence = "confirmed" if product_version.version is not None else "product"
    return Finding(
        vulnerability=vulnerability,
        matched_product=product_version.product,
        matched_version=product_version.version,
        confidence=confidence,
        risk_level=risk.level_from_score(vulnerability.cvss_score),
        recommendation=risk.recommend(vulnerability, product_version.product),
    )
