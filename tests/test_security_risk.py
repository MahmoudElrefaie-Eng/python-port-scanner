from port_scanner.security.models import RiskLevel, Vulnerability, risk_rank
from port_scanner.security.risk import aggregate, level_from_score, recommend


def _vuln(cve_id="CVE-2024-0001", cvss_score=9.8, fixed_version=None):
    return Vulnerability(
        cve_id=cve_id,
        description="A test vulnerability.",
        cvss_score=cvss_score,
        cvss_version="3.1",
        fixed_version=fixed_version,
        references=(),
        source="test",
    )


class TestRiskRank:
    def test_ordering_is_monotonic(self):
        levels = [RiskLevel.INFO, RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        ranks = [risk_rank(level) for level in levels]
        assert ranks == sorted(ranks)


class TestLevelFromScore:
    def test_critical_at_or_above_nine(self):
        assert level_from_score(9.8) == RiskLevel.CRITICAL
        assert level_from_score(9.0) == RiskLevel.CRITICAL

    def test_high_band(self):
        assert level_from_score(7.5) == RiskLevel.HIGH
        assert level_from_score(8.9) == RiskLevel.HIGH

    def test_medium_band(self):
        assert level_from_score(4.0) == RiskLevel.MEDIUM
        assert level_from_score(6.9) == RiskLevel.MEDIUM

    def test_low_band(self):
        assert level_from_score(0.1) == RiskLevel.LOW
        assert level_from_score(3.9) == RiskLevel.LOW

    def test_zero_is_info(self):
        assert level_from_score(0.0) == RiskLevel.INFO

    def test_none_is_info(self):
        assert level_from_score(None) == RiskLevel.INFO


class TestAggregate:
    def test_empty_is_info(self):
        assert aggregate([]) == RiskLevel.INFO

    def test_picks_the_worst_level(self):
        levels = [RiskLevel.LOW, RiskLevel.CRITICAL, RiskLevel.MEDIUM]
        assert aggregate(levels) == RiskLevel.CRITICAL

    def test_single_level(self):
        assert aggregate([RiskLevel.HIGH]) == RiskLevel.HIGH


class TestRecommend:
    def test_includes_fixed_version_when_known(self):
        vuln = _vuln(fixed_version="9.8")
        text = recommend(vuln, "openssh")
        assert "9.8" in text
        assert vuln.cve_id in text
        assert "openssh" in text

    def test_falls_back_to_generic_advice_without_a_fixed_version(self):
        vuln = _vuln(fixed_version=None)
        text = recommend(vuln, "openssh")
        assert vuln.cve_id in text
        assert "vendor's patch" in text

    def test_includes_cvss_score_when_present(self):
        vuln = _vuln(cvss_score=9.8)
        assert "9.8" in recommend(vuln, "openssh")
