import socket

import pytest

from port_scanner.cli import main, parse_ports


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
