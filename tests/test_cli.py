import socket

import pytest

from port_scanner.cli import _format_table, main, parse_ports
from port_scanner.discovery import PortResult


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
