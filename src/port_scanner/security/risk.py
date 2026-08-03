"""CVSS-based risk scoring and deterministic, template-based recommendations.

Recommendations are template text, not LLM-generated, on purpose: they
need to be deterministic (reproducible, testable) and work identically in
offline mode. Richer, AI-generated recommendations are a natural future
addition — as a separate provider-like component consuming a `Finding`,
not a change to this module (see DECISIONS.md 33).
"""

from __future__ import annotations

from collections.abc import Iterable

from port_scanner.security.models import RiskLevel, Vulnerability, risk_rank

# Thresholds as published by NVD for mapping a CVSS base score to a
# qualitative severity rating. Applied to both v3.x and v2 scores — v2
# has no official "critical" band, so a 10.0-scoring v2 finding lands in
# CRITICAL here rather than being capped at HIGH; this is a deliberate
# simplification (see DECISIONS.md 31 for the broader "approximate
# matching, not a full-fidelity CVSS implementation" framing).
_SCORE_THRESHOLDS: tuple[tuple[float, RiskLevel], ...] = (
    (9.0, RiskLevel.CRITICAL),
    (7.0, RiskLevel.HIGH),
    (4.0, RiskLevel.MEDIUM),
    (0.1, RiskLevel.LOW),
)


def level_from_score(score: float | None) -> RiskLevel:
    """Map a CVSS base score to a `RiskLevel`. `None` (unscored) -> INFO."""
    if score is None:
        return RiskLevel.INFO
    for threshold, level in _SCORE_THRESHOLDS:
        if score >= threshold:
            return level
    return RiskLevel.INFO


def aggregate(levels: Iterable[RiskLevel]) -> RiskLevel:
    """Worst-case aggregation: the highest `RiskLevel` among `levels`, or
    INFO if empty. This is the same convention Nessus/OpenVAS/Qualys use
    for host-level severity — the single worst finding, not an average,
    is what a reader needs to see first."""
    levels = list(levels)
    if not levels:
        return RiskLevel.INFO
    return max(levels, key=risk_rank)


def recommend(vulnerability: Vulnerability, matched_product: str) -> str:
    """A short, deterministic remediation suggestion for `vulnerability`."""
    cve = vulnerability.cve_id
    score_note = (
        f" (CVSS {vulnerability.cvss_score})" if vulnerability.cvss_score is not None else ""
    )
    if vulnerability.fixed_version:
        return (
            f"Upgrade {matched_product} to {vulnerability.fixed_version} or later "
            f"to address {cve}{score_note}."
        )
    return f"Review {cve}{score_note} and apply the vendor's patch for {matched_product}."
