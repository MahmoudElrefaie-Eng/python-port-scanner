import socket

import pytest

from port_scanner.cli import _format_security_report, _format_table, main, parse_ports
from port_scanner.discovery import PortResult
from port_scanner.security.models import Finding, Host, RiskLevel, Service, Vulnerability


def _free_port() -> int:
    """Ask the OS for an unused local port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class TestParsePorts:
    def test_single_port(self):
        assert parse_ports("80") == [80]

    def test_comma_separated_ports(self):
        assert parse_ports("22,80,443") == [22, 80, 443]

    def test_range(self):
        assert parse_ports("20-25") == [20, 21, 22, 23, 24, 25]

    def test_mixed_list_and_range(self):
        assert parse_ports("22,80,8000-8002") == [22, 80, 8000, 8001, 8002]

    def test_deduplicates_and_sorts(self):
        assert parse_ports("443,80,80,443") == [80, 443]

    def test_rejects_non_numeric_port(self):
        with pytest.raises(ValueError):
            parse_ports("abc")

    def test_rejects_backwards_range(self):
        with pytest.raises(ValueError):
            parse_ports("90-20")

    def test_rejects_out_of_range_port(self):
        with pytest.raises(ValueError):
            parse_ports("70000")

    def test_rejects_empty_entry(self):
        with pytest.raises(ValueError):
            parse_ports("22,,80")


def test_main_reports_open_port(capsys):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]

        exit_code = main(["127.0.0.1", "--ports", str(port), "--timeout", "0.5"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert str(port) in captured.out


def test_main_reports_no_open_ports(capsys):
    closed_port = _free_port()

    exit_code = main(["127.0.0.1", "--ports", str(closed_port), "--timeout", "0.5"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "No open ports" in captured.out


def test_main_rejects_invalid_port_spec(capsys):
    exit_code = main(["127.0.0.1", "--ports", "not-a-port"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "error" in captured.err.lower()


def test_main_prints_a_table_with_service_and_banner_columns(capsys):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]

        exit_code = main(["127.0.0.1", "--ports", str(port), "--timeout", "0.3"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "PORT" in captured.out
    assert "STATE" in captured.out
    assert "SERVICE" in captured.out
    assert "BANNER" in captured.out
    # A raw listening socket with nothing behind it isn't a known service.
    assert "Unknown" in captured.out


def test_main_without_assess_flag_omits_security_report(capsys):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]

        exit_code = main(["127.0.0.1", "--ports", str(port), "--timeout", "0.5"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Security assessment" not in captured.out


def test_main_assess_offline_reports_no_findings_for_unrecognized_service(capsys):
    # --offline forces cache-only lookups, so this never touches the
    # network even though a raw listening socket has no parseable banner
    # to look up anyway.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]

        exit_code = main(
            ["127.0.0.1", "--ports", str(port), "--timeout", "0.5", "--assess", "--offline"]
        )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Security assessment for 127.0.0.1" in captured.out
    assert "No known vulnerabilities matched" in captured.out


def test_main_assess_with_no_open_ports_reports_nothing_to_assess(capsys):
    closed_port = _free_port()

    exit_code = main(
        ["127.0.0.1", "--ports", str(closed_port), "--timeout", "0.3", "--assess", "--offline"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "No open ports to assess" in captured.out
    assert "Security assessment" not in captured.out


class TestFormatSecurityReport:
    def test_renders_host_risk_and_per_service_findings(self):
        vulnerability = Vulnerability(
            cve_id="CVE-2003-0693",
            description="a buffer overflow",
            cvss_score=10.0,
            cvss_version="2.0",
            fixed_version="3.6.2",
            references=(),
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
        host = Host(target="example.com", services=(service,), risk_level=RiskLevel.CRITICAL)

        report = _format_security_report(host)

        assert "host risk = CRITICAL" in report
        assert "Port 22 (SSH) - OpenSSH_3.4p1 - risk: CRITICAL" in report
        assert "CVE-2003-0693 (CVSS 10.0)" in report
        assert "Recommendation: Upgrade openssh to 3.6.2" in report

    def test_service_with_no_findings_says_so(self):
        service = Service(
            port=80,
            state="OPEN",
            service_name="HTTP",
            banner="nginx/1.18.0",
            findings=(),
            risk_level=RiskLevel.INFO,
        )
        host = Host(target="example.com", services=(service,), risk_level=RiskLevel.INFO)

        report = _format_security_report(host)

        assert "No known vulnerabilities matched" in report


class TestFormatTable:
    def test_renders_header_and_rows(self):
        results = [
            PortResult(port=22, state="OPEN", service="SSH", banner="OpenSSH_9.6"),
            PortResult(port=80, state="OPEN", service="HTTP", banner="nginx/1.18.0"),
        ]

        table = _format_table(results)
        lines = table.splitlines()

        assert lines[0].split() == ["PORT", "STATE", "SERVICE", "BANNER"]
        assert "22" in lines[2] and "SSH" in lines[2] and "OpenSSH_9.6" in lines[2]
        assert "80" in lines[3] and "HTTP" in lines[3] and "nginx/1.18.0" in lines[3]

    def test_columns_are_aligned_to_widest_cell(self):
        results = [
            PortResult(port=22, state="OPEN", service="SSH", banner="OpenSSH_9.6"),
            PortResult(port=3306, state="OPEN", service="MySQL", banner="8.0.34"),
        ]

        lines = _format_table(results).splitlines()
        # Every row (header, separator, and both data rows) must be the
        # same length once padded to the widest cell per column.
        assert len({len(line) for line in lines}) == 1
