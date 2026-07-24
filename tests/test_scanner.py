import socket

from port_scanner.scanner import scan_port, scan_range


def _free_port() -> int:
    """Ask the OS for an unused local port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_scan_port_detects_open_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]

        assert scan_port("127.0.0.1", port) is True


def test_scan_port_detects_closed_port():
    port = _free_port()  # bound then released; nothing listening on it now

    assert scan_port("127.0.0.1", port) is False


def test_scan_range_returns_only_open_ports():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        open_port = server.getsockname()[1]
        closed_port = _free_port()

        result = scan_range("127.0.0.1", [open_port, closed_port])

        assert result == [open_port]
