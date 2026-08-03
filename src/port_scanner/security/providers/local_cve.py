"""Local, offline-safe provider backed by the SQLite CVE cache."""

from __future__ import annotations

from pathlib import Path

from port_scanner.security import cve_db, matching
from port_scanner.security.models import Vulnerability


class LocalCVEProvider:
    """Reads `cve_db.py`. Zero network, zero latency beyond a disk read —
    always tried first by `engine.assess()` (see DECISIONS.md 29)."""

    name = "local-cve"

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db_path = Path(db_path) if db_path is not None else cve_db.default_db_path()

    @property
    def db_path(self) -> Path:
        """Exposed so `engine.py` can point a live provider's write-through
        cache at the same database, without reaching into a private attribute."""
        return self._db_path

    def lookup(self, product: str, version: str | None) -> list[Vulnerability]:
        parsed_version = matching.parse_version(version) if version else None
        found: dict[str, Vulnerability] = {}
        try:
            with cve_db.connect(self._db_path) as conn:
                for candidate in matching.cpe_product_candidates(product):
                    for record in cve_db.query_by_product(conn, candidate):
                        if parsed_version is None or matching.in_range(
                            parsed_version,
                            record.version_start,
                            record.version_start_inclusive,
                            record.version_end,
                            record.version_end_inclusive,
                        ):
                            found[record.vulnerability.cve_id] = record.vulnerability
        except Exception:
            # A corrupt/locked/unreadable cache degrades to "no results",
            # same as any other provider failure — see DECISIONS.md 32.
            return []
        return list(found.values())
