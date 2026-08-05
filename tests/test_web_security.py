"""Tests for the Security Engine's web wiring (Milestone 5): the JSON view
models, the `security_service.py` adapter, the "Assess for known
vulnerabilities" checkbox on the scan form, and the `POST
/api/v1/assessments` JSON endpoint.

Deliberately never exercises a real NVD lookup. `security_service.py`
calls `security.engine.assess()` with its own defaults (LocalCVEProvider +
NVDProvider); `assess()`'s own provider-chain behavior is already covered
by `tests/test_security_engine.py` and `tests/test_security_providers.py`
(the latter against a local fake HTTP server, not the real NVD API — see
docs/CLAUDE.md's testing philosophy). Tests here either use an
unrecognized banner (no product to look up, so no provider is ever
queried) or monkeypatch `security_service.assess` with a fake `Host` to
verify the view-model mapping end-to-end, independent of live network
access.
"""

from __future__ import annotations

import socket

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import status
from fastapi.testclient import TestClient

from port_scanner.security.models import Finding, Host, RiskLevel, Service, Vulnerability
from port_scanner.web.app import create_app
from port_scanner.web.schemas.scan import PortResultView
from port_scanner.web.services import security_service


def _listening_port() -> tuple[socket.socket, int]:
    """Bind and listen on an OS-assigned port, returning the socket and its
    port number. The caller must close the socket once done scanning it."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    return server, server.getsockname()[1]


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


class TestSecurityServiceAdapter:
    """Unit tests for `security_service.run_assessment`, independent of HTTP wiring."""

    def test_unrecognized_banner_has_no_findings(self):
        results = [PortResultView(port=9999, state="OPEN", service="Unknown", banner="Unknown")]

        host_view = security_service.run_assessment("example.com", results)

        assert host_view.target == "example.com"
        assert host_view.risk_level == RiskLevel.INFO
        assert host_view.services[0].port == 9999
        assert host_view.services[0].findings == []

    def test_empty_results_yields_a_host_view_with_no_services(self):
        host_view = security_service.run_assessment("example.com", [])

        assert host_view.target == "example.com"
        assert host_view.services == []
        assert host_view.risk_level == RiskLevel.INFO

    def test_maps_findings_and_recommendations_from_assess(self, monkeypatch):
        vulnerability = Vulnerability(
            cve_id="CVE-2003-0693",
            description="a buffer overflow",
            cvss_score=10.0,
            cvss_version="2.0",
            fixed_version="3.6.2",
            references=("https://example.com/advisory",),
            source="nvd",
        )
        finding = Finding(
            vulnerability=vulnerability,
            matched_product="openssh",
            matched_version="3.4p1",
            confidence="confirmed",
            risk_level=RiskLevel.CRITICAL,
            recommendation="Upgrade openssh to 3.6.2 or later to address CVE-2003-0693 (CVSS 10.0).",
        )
        service = Service(
            port=22,
            state="OPEN",
            service_name="SSH",
            banner="OpenSSH_3.4p1",
            findings=(finding,),
            risk_level=RiskLevel.CRITICAL,
        )
        fake_host = Host(target="example.com", services=(service,), risk_level=RiskLevel.CRITICAL)
        monkeypatch.setattr(security_service, "assess", lambda target, port_results: fake_host)

        results = [PortResultView(port=22, state="OPEN", service="SSH", banner="OpenSSH_3.4p1")]
        host_view = security_service.run_assessment("example.com", results)

        assert host_view.risk_level == RiskLevel.CRITICAL
        finding_view = host_view.services[0].findings[0]
        assert finding_view.vulnerability.cve_id == "CVE-2003-0693"
        assert finding_view.vulnerability.references == ["https://example.com/advisory"]
        assert finding_view.confidence == "confirmed"
        assert finding_view.recommendation.startswith("Upgrade openssh")


class TestScanFormAssessCheckbox:
    def test_checkbox_present_and_unchecked_by_default(self, client: TestClient):
        response = client.get("/")

        assert response.status_code == status.HTTP_200_OK
        assert 'name="assess"' in response.text
        assert "checked" not in response.text

    def test_assess_true_shows_security_section(self, client: TestClient):
        server, port = _listening_port()
        try:
            response = client.post(
                "/scan",
                data={
                    "target": "127.0.0.1",
                    "ports": str(port),
                    "timeout": "0.5",
                    "workers": "10",
                    "assess": "true",
                },
            )
        finally:
            server.close()

        assert response.status_code == status.HTTP_200_OK
        assert "Security assessment" in response.text
        assert "risk--info" in response.text
        assert "No known vulnerabilities matched" in response.text
        assert "checked" in response.text  # sticky checkbox

    def test_assess_omitted_hides_security_section(self, client: TestClient):
        server, port = _listening_port()
        try:
            response = client.post(
                "/scan",
                data={"target": "127.0.0.1", "ports": str(port), "timeout": "0.5", "workers": "10"},
            )
        finally:
            server.close()

        assert response.status_code == status.HTTP_200_OK
        assert "Security assessment" not in response.text

    def test_invalid_input_preserves_assess_checkbox_state(self, client: TestClient):
        response = client.post(
            "/scan",
            data={"target": "", "ports": "80", "timeout": "1.0", "workers": "10", "assess": "true"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "checked" in response.text


class TestAssessmentsEndpoint:
    def test_returns_host_view_json(self, client: TestClient):
        server, port = _listening_port()
        try:
            response = client.post(
                "/api/v1/assessments",
                json={"target": "127.0.0.1", "ports": str(port), "timeout": 0.5, "workers": 10},
            )
        finally:
            server.close()

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["target"] == "127.0.0.1"
        assert body["risk_level"] == "INFO"
        assert body["services"][0]["port"] == port
        assert body["services"][0]["findings"] == []

    def test_invalid_target_returns_422_with_detail(self, client: TestClient):
        response = client.post("/api/v1/assessments", json={"target": "", "ports": "80"})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "target is required" in response.json()["detail"].lower()

    def test_too_many_ports_is_rejected(self, client: TestClient):
        response = client.post(
            "/api/v1/assessments",
            json={"target": "127.0.0.1", "ports": "1-65535", "timeout": 0.1, "workers": 50},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "too many ports" in response.json()["detail"].lower()

    def test_endpoint_documented_under_security_tag(self, client: TestClient):
        schema = client.get("/openapi.json").json()

        assert "/api/v1/assessments" in schema["paths"]
        assert "security" in schema["paths"]["/api/v1/assessments"]["post"]["tags"]
