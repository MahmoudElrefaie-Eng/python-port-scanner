"""Tests for the vulnerability providers.

`LocalCVEProvider` is tested against a real (throwaway, tmp_path) SQLite
database — real I/O, no mocking, matching this project's testing
philosophy. `NVDProvider` is tested against a small local fake HTTP
server serving canned NVD-shaped responses (the same "real socket, fake
remote" technique tests/test_detection.py already uses for fake SSH/HTTP
servers) rather than mocking `urllib` or hitting the real NVD API — see
DECISIONS.md and this module's own docstring reasoning in
ARCHITECTURE.md's testing-strategy section.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from port_scanner.security import cve_db
from port_scanner.security.providers.local_cve import LocalCVEProvider
from port_scanner.security.providers.nvd import NVDProvider


def _openssh_nvd_response(
    cve_id="CVE-2024-9999",
    version_start="9.0",
    version_end="9.8",
    score=8.1,
):
    return {
        "resultsPerPage": 1,
        "startIndex": 0,
        "totalResults": 1,
        "vulnerabilities": [
            {
                "cve": {
                    "id": cve_id,
                    "descriptions": [
                        {"lang": "en", "value": "A test OpenSSH vulnerability."}
                    ],
                    "metrics": {
                        "cvssMetricV31": [{"cvssData": {"version": "3.1", "baseScore": score}}]
                    },
                    "configurations": [
                        {
                            "nodes": [
                                {
                                    "cpeMatch": [
                                        {
                                            "vulnerable": True,
                                            "criteria": "cpe:2.3:a:openbsd:openssh:*:*:*:*:*:*:*:*",
                                            "versionStartIncluding": version_start,
                                            "versionEndExcluding": version_end,
                                        }
                                    ]
                                }
                            ]
                        }
                    ],
                    "references": [{"url": "https://example.com/advisory"}],
                }
            }
        ],
    }


class _FakeNVDServer:
    """A tiny local HTTP server standing in for the real NVD API."""

    def __init__(self, response_body: bytes, status: int = 200):
        response_body_ = response_body
        status_ = status

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 (stdlib method name)
                self.send_response(status_)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(response_body_)

            def log_message(self, format, *args):  # noqa: A002
                pass  # keep test output quiet

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        self.base_url = f"http://127.0.0.1:{self._server.server_address[1]}/cves/2.0"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        self._server.shutdown()


@pytest.fixture
def fake_nvd():
    servers = []

    def _make(payload: dict, status: int = 200):
        server = _FakeNVDServer(json.dumps(payload).encode("utf-8"), status=status)
        servers.append(server)
        return server

    yield _make

    for server in servers:
        server.stop()


class TestLocalCVEProvider:
    def test_finds_a_cached_vulnerability_in_range(self, tmp_path):
        db_path = tmp_path / "cve.db"
        with cve_db.connect(db_path) as conn:
            from port_scanner.security.models import Vulnerability

            cve_db.upsert(
                conn,
                Vulnerability(
                    cve_id="CVE-2024-0001",
                    description="test",
                    cvss_score=8.1,
                    cvss_version="3.1",
                    fixed_version="9.8",
                    references=(),
                    source="test",
                ),
                "openssh",
                "9.0",
                True,
                "9.8",
                False,
            )

        provider = LocalCVEProvider(db_path=db_path)
        results = provider.lookup("openssh", "9.6")

        assert [v.cve_id for v in results] == ["CVE-2024-0001"]

    def test_excludes_a_cached_vulnerability_outside_the_range(self, tmp_path):
        db_path = tmp_path / "cve.db"
        with cve_db.connect(db_path) as conn:
            from port_scanner.security.models import Vulnerability

            cve_db.upsert(
                conn,
                Vulnerability(
                    cve_id="CVE-2024-0001",
                    description="test",
                    cvss_score=8.1,
                    cvss_version="3.1",
                    fixed_version=None,
                    references=(),
                    source="test",
                ),
                "openssh",
                "9.0",
                True,
                "9.8",
                False,
            )

        provider = LocalCVEProvider(db_path=db_path)
        assert provider.lookup("openssh", "9.9") == []

    def test_unknown_product_returns_empty(self, tmp_path):
        provider = LocalCVEProvider(db_path=tmp_path / "cve.db")
        assert provider.lookup("some-unknown-product", "1.0") == []


class TestNVDProvider:
    def test_finds_cve_within_version_range(self, fake_nvd):
        server = fake_nvd(_openssh_nvd_response())
        provider = NVDProvider(base_url=server.base_url, timeout=5.0)

        results = provider.lookup("openssh", "9.6")

        assert len(results) == 1
        assert results[0].cve_id == "CVE-2024-9999"
        assert results[0].cvss_score == 8.1
        assert results[0].cvss_version == "3.1"

    def test_excludes_cve_outside_version_range(self, fake_nvd):
        server = fake_nvd(_openssh_nvd_response())
        provider = NVDProvider(base_url=server.base_url, timeout=5.0)

        assert provider.lookup("openssh", "9.9") == []

    def test_no_version_returns_product_match_without_range_check(self, fake_nvd):
        server = fake_nvd(_openssh_nvd_response())
        provider = NVDProvider(base_url=server.base_url, timeout=5.0)

        results = provider.lookup("openssh", None)

        assert len(results) == 1

    def test_caches_result_when_a_cache_db_path_is_given(self, fake_nvd, tmp_path):
        server = fake_nvd(_openssh_nvd_response())
        db_path = tmp_path / "cve.db"
        provider = NVDProvider(base_url=server.base_url, timeout=5.0, cache_db_path=db_path)

        provider.lookup("openssh", "9.6")

        with cve_db.connect(db_path) as conn:
            cached = cve_db.query_by_product(conn, "openssh")
        assert len(cached) == 1
        assert cached[0].vulnerability.cve_id == "CVE-2024-9999"

    def test_never_raises_on_connection_failure(self):
        # Nothing listening on this port.
        provider = NVDProvider(base_url="http://127.0.0.1:1/cves/2.0", timeout=1.0)

        assert provider.lookup("openssh", "9.6") == []

    def test_never_raises_on_malformed_response(self, fake_nvd):
        server = _FakeNVDServer(b"not valid json")
        provider = NVDProvider(base_url=server.base_url, timeout=5.0)

        try:
            assert provider.lookup("openssh", "9.6") == []
        finally:
            server.stop()

    def test_never_raises_on_http_error_status(self, fake_nvd):
        server = fake_nvd({"vulnerabilities": []}, status=503)
        provider = NVDProvider(base_url=server.base_url, timeout=5.0)

        assert provider.lookup("openssh", "9.6") == []
