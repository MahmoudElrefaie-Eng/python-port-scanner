"""Local CVE cache: a SQLite-backed store, stdlib `sqlite3` only.

This is reference data (public, read-mostly, identical for every user),
architecturally distinct from the per-user/scan-history data a future
auth/history feature will eventually need in a real RDBMS — see
DECISIONS.md 29. It's a *cache*: written to by providers as a side effect
of a live lookup (see `providers/nvd.py`), read by `LocalCVEProvider`
before any network call is attempted.

The database path is always an explicit parameter, never read from an
environment variable or global config here — see DECISIONS.md 32 and the
architecture proposal's "explicit parameters, not global config"
principle. `default_db_path()` exists so *callers* (an interface's config
layer) have a sensible default to fall back to; this module never calls
it implicitly.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from port_scanner.security.matching import parse_version
from port_scanner.security.models import Vulnerability

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cached_vulnerabilities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cve_id TEXT NOT NULL,
    product TEXT NOT NULL,
    version_start TEXT,
    version_start_inclusive INTEGER NOT NULL DEFAULT 1,
    version_end TEXT,
    version_end_inclusive INTEGER NOT NULL DEFAULT 1,
    description TEXT NOT NULL,
    cvss_score REAL,
    cvss_version TEXT,
    fixed_version TEXT,
    references_json TEXT NOT NULL,
    source TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    UNIQUE (cve_id, product, version_start, version_end)
);
CREATE INDEX IF NOT EXISTS idx_cached_vulnerabilities_product
    ON cached_vulnerabilities (product);
"""


@dataclass(frozen=True)
class CachedRecord:
    """One cached row: a `Vulnerability` plus the affected-version range
    it was recorded against for `product` (bounds are dotted-int tuples
    already parsed via `matching.parse_version`, or `None` if unbounded)."""

    vulnerability: Vulnerability
    product: str
    version_start: tuple[int, ...] | None
    version_start_inclusive: bool
    version_end: tuple[int, ...] | None
    version_end_inclusive: bool


def default_db_path() -> Path:
    """Where the local CVE cache lives if a caller doesn't specify one."""
    return Path.home() / ".port_scanner" / "cve.db"


@contextmanager
def connect(path: Path | str) -> Iterator[sqlite3.Connection]:
    """Open (creating and initializing if needed) the CVE cache at `path`."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
        yield conn
    finally:
        conn.close()


def upsert(
    conn: sqlite3.Connection,
    vulnerability: Vulnerability,
    product: str,
    version_start: str | None,
    version_start_inclusive: bool,
    version_end: str | None,
    version_end_inclusive: bool,
) -> None:
    """Cache `vulnerability` as affecting `product` within the given
    version range. Idempotent: a repeat write for the same
    (cve_id, product, version_start, version_end) replaces the row."""
    conn.execute(
        """
        INSERT INTO cached_vulnerabilities (
            cve_id, product, version_start, version_start_inclusive,
            version_end, version_end_inclusive, description, cvss_score,
            cvss_version, fixed_version, references_json, source, fetched_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (cve_id, product, version_start, version_end) DO UPDATE SET
            version_start_inclusive = excluded.version_start_inclusive,
            version_end_inclusive = excluded.version_end_inclusive,
            description = excluded.description,
            cvss_score = excluded.cvss_score,
            cvss_version = excluded.cvss_version,
            fixed_version = excluded.fixed_version,
            references_json = excluded.references_json,
            source = excluded.source,
            fetched_at = excluded.fetched_at
        """,
        (
            vulnerability.cve_id,
            product,
            version_start,
            int(version_start_inclusive),
            version_end,
            int(version_end_inclusive),
            vulnerability.description,
            vulnerability.cvss_score,
            vulnerability.cvss_version,
            vulnerability.fixed_version,
            json.dumps(list(vulnerability.references)),
            vulnerability.source,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()


def query_by_product(conn: sqlite3.Connection, product: str) -> list[CachedRecord]:
    """All cached records for `product` (case-insensitive exact match)."""
    rows = conn.execute(
        """
        SELECT cve_id, product, version_start, version_start_inclusive,
               version_end, version_end_inclusive, description, cvss_score,
               cvss_version, fixed_version, references_json, source
        FROM cached_vulnerabilities
        WHERE lower(product) = lower(?)
        """,
        (product,),
    ).fetchall()

    records = []
    for row in rows:
        (
            cve_id, row_product, version_start, start_inclusive,
            version_end, end_inclusive, description, cvss_score,
            cvss_version, fixed_version, references_json, source,
        ) = row
        vulnerability = Vulnerability(
            cve_id=cve_id,
            description=description,
            cvss_score=cvss_score,
            cvss_version=cvss_version,
            fixed_version=fixed_version,
            references=tuple(json.loads(references_json)),
            source=source,
        )
        records.append(
            CachedRecord(
                vulnerability=vulnerability,
                product=row_product,
                version_start=parse_version(version_start),
                version_start_inclusive=bool(start_inclusive),
                version_end=parse_version(version_end),
                version_end_inclusive=bool(end_inclusive),
            )
        )
    return records
