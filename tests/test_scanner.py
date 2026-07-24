import socket
from contextlib import ExitStack

from port_scanner.scanner import scan_port, scan_range


def _free_port() -> int:
    """Ask the OS for an unused local port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _listening_server(stack: ExitStack) -> int:
    """Bind and listen on an OS-assigned port; return the port number.

    Registered on `stack` so it stays open (and gets closed) for the
    duration of the test that owns the stack.
    """
    server = stack.enter_context(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    return server.getsockname()[1]


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


def test_scan_range_finds_all_open_ports_among_many_concurrently():
    with ExitStack() as stack:
        open_ports = [_listening_server(stack) for _ in range(5)]
        closed_ports = [_free_port() for _ in range(5)]

        result = scan_range(
            "127.0.0.1", open_ports + closed_ports, max_workers=4
        )

        assert result == sorted(open_ports)


def test_scan_range_output_is_sorted_regardless_of_input_order():
    with ExitStack() as stack:
        open_ports = [_listening_server(stack) for _ in range(2)]

        result = scan_range("127.0.0.1", sorted(open_ports, reverse=True))

        assert result == sorted(open_ports)
