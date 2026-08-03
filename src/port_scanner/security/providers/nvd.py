"""Live provider against the NVD (National Vulnerability Database) REST
API v2.0 — https://nvd.nist.gov/developers/vulnerabilities.

Parses the real response shape (verified against the live API while
building this): `vulnerabilities[].cve.{id,descriptions,metrics,
configurations,references}`, with `configurations[].nodes[].cpeMatch[]`
carrying the CPE match criteria and optional
`versionStart{In,Ex}cluding`/`versionEnd{In,Ex}cluding` bounds. Only the
first CVSS metric found, in v3.1 -> v3.0 -> v2 preference order, is used
— see DECISIONS.md 31 for why this (and the rest of this module) is a
deliberately approximate, not full-fidelity, CPE implementation.

No API key is required for light use (rate-limited to 5 requests per
30 seconds without one); `api_key` is accepted and sent if the caller has
one, for the higher limit.

`results_per_page` defaults to 200, not NVD's own default of 20: verified
live while building this that `keywordSearch` doesn't return results
ordered by relevance to any particular version, so a small page can miss
the specific CVE that actually covers the version being looked up (e.g.
searching "openssh" for version 3.4p1 found 0 matches at 20 results, 58
real matches — including the well-known CVE-2003-0693 — at 200). This
is one HTTP request either way; only the response size grows.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import NamedTuple

from port_scanner.security import cve_db, matching
from port_scanner.security.models import Vulnerability

DEFAULT_BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
DEFAULT_TIMEOUT = 15.0
DEFAULT_RESULTS_PER_PAGE = 200
USER_AGENT = (
    "port-scanner-security/1.0 "
    "(+https://github.com/MahmoudElrefaie-Eng/python-port-scanner)"
)

_CVSS_METRIC_KEYS = (("cvssMetricV31", "3.1"), ("cvssMetricV30", "3.0"), ("cvssMetricV2", "2.0"))


class VersionRange(NamedTuple):
    start: tuple[int, ...] | None
    start_inclusive: bool
    end: tuple[int, ...] | None
    end_inclusive: bool


class NVDProvider:
    """Queries NVD's `keywordSearch`, then refines matches against the
    response's own CPE configuration data for the specific product."""

    name = "nvd"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        results_per_page: int = DEFAULT_RESULTS_PER_PAGE,
        cache_db_path: Path | str | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout
        self._results_per_page = results_per_page
        self._cache_db_path = Path(cache_db_path) if cache_db_path is not None else None

    def lookup(self, product: str, version: str | None) -> list[Vulnerability]:
        parsed_version = matching.parse_version(version) if version else None
        try:
            payload = self._fetch(product)
        except Exception:
            return []

        found: dict[str, Vulnerability] = {}
        for item in payload.get("vulnerabilities", []):
            cve = item.get("cve", {})
            cve_id = cve.get("id")
            if not cve_id:
                continue

            for candidate in matching.cpe_product_candidates(product):
                version_range = self._match_cpe(cve, candidate)
                if version_range is None:
                    continue
                if parsed_version is not None and not matching.in_range(
                    parsed_version, *version_range
                ):
                    continue

                vulnerability = self._to_vulnerability(cve, cve_id)
                found[cve_id] = vulnerability
                self._cache(vulnerability, candidate, version_range)
                break  # this CVE is accounted for; move to the next one

        return list(found.values())

    def _fetch(self, product: str) -> dict:
        params = {"keywordSearch": product, "resultsPerPage": str(self._results_per_page)}
        url = f"{self._base_url}?{urllib.parse.urlencode(params)}"
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        if self._api_key:
            headers["apiKey"] = self._api_key
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=self._timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _cache(self, vulnerability: Vulnerability, product: str, version_range: VersionRange) -> None:
        if self._cache_db_path is None:
            return
        try:
            with cve_db.connect(self._cache_db_path) as conn:
                cve_db.upsert(
                    conn,
                    vulnerability,
                    product,
                    _format_version(version_range.start),
                    version_range.start_inclusive,
                    _format_version(version_range.end),
                    version_range.end_inclusive,
                )
        except Exception:
            pass  # caching is a bonus; never let it affect the lookup result

    @staticmethod
    def _match_cpe(cve: dict, product: str) -> VersionRange | None:
        """Find a `cpeMatch` entry for `product` in `cve`'s configuration
        data and extract its affected-version range, if any."""
        for configuration in cve.get("configurations", []):
            for node in configuration.get("nodes", []):
                for cpe_match in node.get("cpeMatch", []):
                    if not cpe_match.get("vulnerable", False):
                        continue
                    criteria_parts = cpe_match.get("criteria", "").split(":")
                    # cpe:2.3:{part}:{vendor}:{product}:{version}:...
                    if len(criteria_parts) < 6 or criteria_parts[4].lower() != product.lower():
                        continue

                    start = matching.parse_version(
                        cpe_match.get("versionStartIncluding") or cpe_match.get("versionStartExcluding")
                    )
                    start_inclusive = "versionStartExcluding" not in cpe_match
                    end = matching.parse_version(
                        cpe_match.get("versionEndIncluding") or cpe_match.get("versionEndExcluding")
                    )
                    end_inclusive = "versionEndExcluding" not in cpe_match

                    if start is None and end is None:
                        # No explicit range on this entry — if the CPE
                        # criteria itself pins one exact version (not a
                        # wildcard), that's an exact-match range.
                        pinned = criteria_parts[5] if len(criteria_parts) > 5 else "*"
                        if pinned in ("*", "-"):
                            continue
                        exact = matching.parse_version(pinned)
                        if exact is None:
                            continue
                        return VersionRange(exact, True, exact, True)

                    return VersionRange(start, start_inclusive, end, end_inclusive)
        return None

    @staticmethod
    def _to_vulnerability(cve: dict, cve_id: str) -> Vulnerability:
        description = ""
        for entry in cve.get("descriptions", []):
            if entry.get("lang") == "en":
                description = entry.get("value", "")
                break

        score: float | None = None
        cvss_version: str | None = None
        metrics = cve.get("metrics", {})
        for key, version_label in _CVSS_METRIC_KEYS:
            entries = metrics.get(key)
            if entries:
                score = entries[0].get("cvssData", {}).get("baseScore")
                cvss_version = version_label
                break

        references = tuple(
            ref["url"] for ref in cve.get("references", []) if ref.get("url")
        )

        return Vulnerability(
            cve_id=cve_id,
            description=description,
            cvss_score=score,
            cvss_version=cvss_version,
            # NVD's v2.0 API doesn't reliably surface a "fixed in" version
            # as structured data; left unset rather than guessed.
            fixed_version=None,
            references=references,
            source="nvd",
        )


def _format_version(version: tuple[int, ...] | None) -> str | None:
    return ".".join(str(part) for part in version) if version is not None else None
