"""Data models for the security assessment layer.

Shaped as Host -> Service -> Finding -> Vulnerability rather than a flat
per-scan result list, on purpose: a `Host` is what a future Asset
Inventory feature persists and tracks across scans over time; `Service`
composes a `discovery.PortResult` rather than replacing it (see
DECISIONS.md 28). `Vulnerability` (the CVE record itself) is kept
separate from `Finding` (the fact that this vulnerability was matched
against this service) so the same CVE found on many hosts isn't
duplicated data — see DECISIONS.md 28.

Every type here is a frozen, plain dataclass using only tuples for
collections (never lists — a "frozen" dataclass with a `list` field is
still mutable through that field). This is deliberate: these are the
types a future `ai/` package, `reporting/` package, or persistence layer
consumes as a stable, read-only contract (see DECISIONS.md 33) — nothing
about them assumes a particular consumer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RiskLevel(str, Enum):
    """Ordered from least to most severe; ordering matters for aggregation."""

    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# Ordinal ranking for RiskLevel, since Enum members aren't orderable by
# default and IntEnum would make "CRITICAL > HIGH" true but also make
# nonsensical things like "CRITICAL + 1" type-check.
_RISK_ORDER: dict[RiskLevel, int] = {
    RiskLevel.INFO: 0,
    RiskLevel.LOW: 1,
    RiskLevel.MEDIUM: 2,
    RiskLevel.HIGH: 3,
    RiskLevel.CRITICAL: 4,
}


def risk_rank(level: RiskLevel) -> int:
    """Ordinal rank of `level`, for sorting/max() over RiskLevel values."""
    return _RISK_ORDER[level]


@dataclass(frozen=True)
class Vulnerability:
    """A CVE record as reported by a provider — data about the flaw
    itself, independent of any specific host it might affect."""

    cve_id: str
    description: str
    cvss_score: float | None
    cvss_version: str | None
    fixed_version: str | None
    references: tuple[str, ...]
    source: str  # provider name that supplied this record, e.g. "nvd"


@dataclass(frozen=True)
class Finding:
    """One `Vulnerability` matched against one `Service`."""

    vulnerability: Vulnerability
    matched_product: str
    matched_version: str | None
    confidence: str  # "confirmed" (version range matched) or "product" (
    #                   product identified, no confirmed version range)
    risk_level: RiskLevel
    recommendation: str


@dataclass(frozen=True)
class Service:
    """One open port, plus what's known about vulnerabilities in
    whatever's running on it. Composes a `discovery.PortResult` (by
    value, not by reference) rather than modifying or subclassing it —
    `discovery.py` has no knowledge this type exists."""

    port: int
    state: str
    service_name: str
    banner: str
    findings: tuple[Finding, ...]
    risk_level: RiskLevel


@dataclass(frozen=True)
class Host:
    """A scanned target and everything found on it. This is the top-level
    result `security.engine.assess()` returns, and the shape a future
    Asset Inventory feature would persist and re-assess over time."""

    target: str
    services: tuple[Service, ...]
    risk_level: RiskLevel
