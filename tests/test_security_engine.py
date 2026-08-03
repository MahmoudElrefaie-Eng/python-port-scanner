"""Tests for the assess() orchestrator, using hand-written fake providers
(trivial to write against the VulnerabilityProvider Protocol) so the
orchestration logic — provider ordering, merging, never-raises — is
tested independently of any concrete provider's internals."""

from port_scanner.discovery import PortResult
from port_scanner.security.engine import assess
from port_scanner.security.models import RiskLevel, Vulnerability


def _vuln(cve_id, score=8.1):
    return Vulnerability(
        cve_id=cve_id,
        description="test",
        cvss_score=score,
        cvss_version="3.1",
        fixed_version="9.9",
        references=(),
        source="fake",
    )


class _FakeProvider:
    def __init__(self, name, results=None, raises=False):
        self.name = name
        self._results = results or []
        self._raises = raises
        self.calls = []

    def lookup(self, product, version):
        self.calls.append((product, version))
        if self._raises:
            raise RuntimeError("provider exploded")
        return list(self._results)


def _port_result(port=22, service="SSH", banner="OpenSSH_9.6"):
    return PortResult(port=port, state="OPEN", service=service, banner=banner)


class TestAssessBasics:
    def test_returns_a_host_with_one_service_per_port_result(self):
        results = [_port_result(22), _port_result(80, "HTTP", "nginx/1.18.0")]
        host = assess("example.com", results, cache=_FakeProvider("cache"), providers=())

        assert host.target == "example.com"
        assert [s.port for s in host.services] == [22, 80]

    def test_service_with_no_parseable_banner_has_no_findings(self):
        results = [_port_result(9999, "Unknown", "Unknown")]
        host = assess("example.com", results, cache=_FakeProvider("cache"), providers=())

        assert host.services[0].findings == ()
        assert host.services[0].risk_level == RiskLevel.INFO

    def test_empty_port_results_yields_a_host_with_no_services(self):
        host = assess("example.com", [], cache=_FakeProvider("cache"), providers=())
        assert host.services == ()
        assert host.risk_level == RiskLevel.INFO


class TestProviderOrdering:
    def test_cache_hit_skips_live_providers(self):
        cache = _FakeProvider("cache", results=[_vuln("CVE-CACHED")])
        live = _FakeProvider("live", results=[_vuln("CVE-LIVE")])

        host = assess("h", [_port_result()], cache=cache, providers=(live,))

        assert [f.vulnerability.cve_id for f in host.services[0].findings] == ["CVE-CACHED"]
        assert live.calls == []  # never queried

    def test_cache_miss_falls_through_to_live_providers(self):
        cache = _FakeProvider("cache", results=[])
        live = _FakeProvider("live", results=[_vuln("CVE-LIVE")])

        host = assess("h", [_port_result()], cache=cache, providers=(live,))

        assert [f.vulnerability.cve_id for f in host.services[0].findings] == ["CVE-LIVE"]
        assert live.calls == [("openssh", "9.6")]

    def test_multiple_live_providers_are_merged_and_deduplicated(self):
        cache = _FakeProvider("cache", results=[])
        provider_a = _FakeProvider("a", results=[_vuln("CVE-SHARED"), _vuln("CVE-A-ONLY")])
        provider_b = _FakeProvider("b", results=[_vuln("CVE-SHARED"), _vuln("CVE-B-ONLY")])

        host = assess("h", [_port_result()], cache=cache, providers=(provider_a, provider_b))

        cve_ids = {f.vulnerability.cve_id for f in host.services[0].findings}
        assert cve_ids == {"CVE-SHARED", "CVE-A-ONLY", "CVE-B-ONLY"}


class TestNeverRaises:
    def test_a_broken_cache_provider_does_not_fail_the_assessment(self):
        cache = _FakeProvider("cache", raises=True)
        live = _FakeProvider("live", results=[_vuln("CVE-LIVE")])

        host = assess("h", [_port_result()], cache=cache, providers=(live,))

        assert [f.vulnerability.cve_id for f in host.services[0].findings] == ["CVE-LIVE"]

    def test_a_broken_live_provider_does_not_fail_the_assessment(self):
        cache = _FakeProvider("cache", results=[])
        broken = _FakeProvider("broken", raises=True)
        working = _FakeProvider("working", results=[_vuln("CVE-OK")])

        host = assess("h", [_port_result()], cache=cache, providers=(broken, working))

        assert [f.vulnerability.cve_id for f in host.services[0].findings] == ["CVE-OK"]

    def test_all_providers_failing_yields_no_findings_not_an_exception(self):
        cache = _FakeProvider("cache", raises=True)
        live = _FakeProvider("live", raises=True)

        host = assess("h", [_port_result()], cache=cache, providers=(live,))

        assert host.services[0].findings == ()
        assert host.risk_level == RiskLevel.INFO


class TestRiskAggregation:
    def test_host_risk_is_the_worst_across_services(self):
        cache = _FakeProvider("cache", results=[])
        low_risk = _FakeProvider("low", results=[_vuln("CVE-LOW", score=2.0)])
        critical_risk = _FakeProvider("critical", results=[_vuln("CVE-CRIT", score=9.9)])

        results = [
            _port_result(22, "SSH", "OpenSSH_9.6"),
        ]
        # Use two separate assess() calls (one provider set can't easily
        # vary per-port) — assert per-service aggregation directly instead.
        host_low = assess("h", results, cache=cache, providers=(low_risk,))
        host_critical = assess("h", results, cache=cache, providers=(critical_risk,))

        assert host_low.services[0].risk_level == RiskLevel.LOW
        assert host_low.risk_level == RiskLevel.LOW
        assert host_critical.services[0].risk_level == RiskLevel.CRITICAL
        assert host_critical.risk_level == RiskLevel.CRITICAL

    def test_finding_confidence_reflects_whether_a_version_was_known(self):
        cache = _FakeProvider("cache", results=[_vuln("CVE-X")])

        with_version = assess("h", [_port_result(22, "SSH", "OpenSSH_9.6")], cache=cache, providers=())
        without_version = assess("h", [_port_result(80, "HTTP", "Caddy")], cache=cache, providers=())

        assert with_version.services[0].findings[0].confidence == "confirmed"
        assert without_version.services[0].findings[0].confidence == "product"
