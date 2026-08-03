"""Banner -> (product, version) normalization, and version comparison.

This is deliberately a "Stage 1" implementation, not full CPE (Common
Platform Enumeration) binding — see DECISIONS.md 31 for why. It covers
the banner shapes `detection.py`'s grabbers actually produce (an
OpenSSH-style greeting, an HTTP `Server` header, `"MySQL <version>"`,
`"Redis <version>"`) and a simple dotted-numeric version comparison. Both
are documented, known-approximate, and safe to extend without touching
anything outside this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_SSH_VERSION_RE = re.compile(r"OpenSSH[_-]?(\d+(?:\.\d+)*(?:p\d+)?)", re.IGNORECASE)
_HTTP_SERVER_VERSION_RE = re.compile(r"^([A-Za-z][\w.-]*)/(\d+(?:\.\d+)*)")
_HTTP_SERVER_NAME_RE = re.compile(r"^([A-Za-z][\w.-]*)")
_MYSQL_VERSION_RE = re.compile(r"MySQL\s+(\d\S*)", re.IGNORECASE)
_REDIS_VERSION_RE = re.compile(r"Redis\s+(\d\S*)", re.IGNORECASE)

# A handful of known product-name mismatches between what a banner says
# and what NVD's CPE dictionary calls the same product (e.g. Apache HTTP
# Server's official CPE product is "http_server", not "apache"). Kept as
# a small, explicit table rather than a general solution — see
# DECISIONS.md 31.
_CPE_PRODUCT_ALIASES: dict[str, tuple[str, ...]] = {
    "apache": ("apache", "http_server"),
}


@dataclass(frozen=True)
class ProductVersion:
    """A normalized (product, version) pair extracted from a banner.
    `version` is `None` when a product was identified but no version
    could be parsed out of the banner (e.g. a bare `"Caddy"`)."""

    product: str
    version: str | None


def normalize(service_name: str, banner: str) -> ProductVersion | None:
    """Extract a `ProductVersion` from a service name + banner, or `None`
    if the banner doesn't look like one this module knows how to parse."""
    if not banner or banner == "Unknown":
        return None

    if service_name == "SSH":
        match = _SSH_VERSION_RE.search(banner)
        return ProductVersion("openssh", match.group(1)) if match else None

    if service_name in ("HTTP", "HTTPS"):
        match = _HTTP_SERVER_VERSION_RE.match(banner)
        if match:
            return ProductVersion(match.group(1).lower(), match.group(2))
        match = _HTTP_SERVER_NAME_RE.match(banner)
        return ProductVersion(match.group(1).lower(), None) if match else None

    if service_name == "MySQL":
        match = _MYSQL_VERSION_RE.search(banner)
        return ProductVersion("mysql", match.group(1)) if match else None

    if service_name == "Redis":
        match = _REDIS_VERSION_RE.search(banner)
        if match:
            return ProductVersion("redis", match.group(1))
        if banner.lower().startswith("redis"):
            return ProductVersion("redis", None)
        return None

    return None


def cpe_product_candidates(product: str) -> tuple[str, ...]:
    """Product names to try against a CPE dictionary for `product`,
    covering known banner-name / CPE-name mismatches (see
    `_CPE_PRODUCT_ALIASES`). Always includes `product` itself."""
    return _CPE_PRODUCT_ALIASES.get(product, (product,))


def parse_version(text: str | None) -> tuple[int, ...] | None:
    """Parse a leading run of dot/hyphen-separated numeric segments out of
    `text`. `"9.6p1"` -> `(9, 6)`, `"5.7.30-log"` -> `(5, 7, 30)`,
    `"2.4.7"` -> `(2, 4, 7)`. Returns `None` if no numeric segment is found
    at all (this is an approximation, not a full version-spec parser —
    pre-release/build-metadata ordering per SemVer/PEP 440 is not
    modeled)."""
    if not text:
        return None
    segments: list[int] = []
    for part in re.split(r"[.\-]", text):
        match = re.match(r"^(\d+)", part)
        if not match:
            break
        segments.append(int(match.group(1)))
        if not part.isdigit():
            break  # numeric prefix followed by a non-numeric suffix ends the run
    return tuple(segments) if segments else None


def compare_versions(a: tuple[int, ...], b: tuple[int, ...]) -> int:
    """-1 if a < b, 0 if equal, 1 if a > b — comparing as dotted integers,
    zero-padding the shorter tuple (so `(9,)` == `(9, 0)`)."""
    length = max(len(a), len(b))
    pa = a + (0,) * (length - len(a))
    pb = b + (0,) * (length - len(b))
    return (pa > pb) - (pa < pb)


def in_range(
    version: tuple[int, ...],
    start: tuple[int, ...] | None,
    start_inclusive: bool,
    end: tuple[int, ...] | None,
    end_inclusive: bool,
) -> bool:
    """Whether `version` falls within `[start, end]` (bounds optional,
    inclusivity per bound) — the shape NVD expresses affected-version
    ranges in (`versionStart{In,Ex}cluding`/`versionEnd{In,Ex}cluding`)."""
    if start is not None:
        cmp = compare_versions(version, start)
        if cmp < 0 or (cmp == 0 and not start_inclusive):
            return False
    if end is not None:
        cmp = compare_versions(version, end)
        if cmp > 0 or (cmp == 0 and not end_inclusive):
            return False
    return True
