"""Tests for port_scanner.discovery: the scan + service-detection pipeline.

Real local sockets, per this project's testing philosophy — see
tests/test_detection.py for why the well-known-port dispatch table gets
monkeypatched rather than binding privileged ports directly.
"""

import socket
import threading
from contextlib import ExitStack

import port_scanner.detection as detection
from port_scanner.discovery import STATE_OPEN, PortResult, discover


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _listening_server(stack: ExitStack) -> int:
    server = stack.enter_context(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    return server.getsockname()[1]


def _serve_repeatedly(behavior, max_connections: int = 4) -> int:
    """Bind an OS-assigned port and run `behavior(conn)` against each of
    up to `max_connections` connections in a background thread.

    `discover()` connects to an open port twice — once from `scan_range`
    just to confirm it's open (no read), once from `identify_service` to
    grab the banner — so a single-shot server (accept one connection, then
    close the listening socket) would refuse the second connection.
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(max_connections)
    port = server.getsockname()[1]

    def _accept_loop():
        for _ in range(max_connections):
            try:
                conn, _ = server.accept()
            except OSError:
                break
            try:
                behavior(conn)
            except OSError:
                pass
            finally:
                conn.close()
        server.close()

    threading.Thread(target=_accept_loop, daemon=True).start()
    return port


def test_discover_returns_empty_list_when_nothing_is_open():
    closed_ports = [_free_port() for _ in range(3)]

    assert discover("127.0.0.1", closed_ports) == []


def test_discover_returns_one_result_per_open_port():
    with ExitStack() as stack:
        open_ports = [_listening_server(stack) for _ in range(3)]
        closed_ports = [_free_port() for _ in range(3)]

        results = discover("127.0.0.1", open_ports + closed_ports, timeout=0.5)

    assert sorted(r.port for r in results) == sorted(open_ports)
    assert all(isinstance(r, PortResult) for r in results)
    assert all(r.state == STATE_OPEN for r in results)


def test_discover_only_identifies_open_ports_not_closed_ones(monkeypatch):
    calls = []
    original = detection.identify_service

    def counting_identify(host, port, timeout=1.5):
        calls.append(port)
        return original(host, port, timeout)

    monkeypatch.setattr("port_scanner.discovery.identify_service", counting_identify)

    with ExitStack() as stack:
        open_port = _listening_server(stack)
        closed_ports = [_free_port() for _ in range(4)]

        discover("127.0.0.1", [open_port, *closed_ports], timeout=0.3)

    assert calls == [open_port]


def test_discover_attaches_detected_service_and_banner(monkeypatch):
    port = _serve_repeatedly(lambda conn: conn.sendall(b"SSH-2.0-OpenSSH_9.6\r\n"))
    monkeypatch.setitem(detection._BANNER_GRABBERS, port, detection._grab_ssh)
    monkeypatch.setitem(detection.SERVICE_PORTS, port, "SSH")

    results = discover("127.0.0.1", [port], timeout=1.0)

    assert len(results) == 1
    result = results[0]
    assert result.port == port
    assert result.state == STATE_OPEN
    assert result.service == "SSH"
    assert result.banner == "OpenSSH_9.6"


def test_discover_defaults_unrecognized_service_to_unknown():
    with ExitStack() as stack:
        open_port = _listening_server(stack)

        results = discover("127.0.0.1", [open_port], timeout=0.3)

    assert results[0].service == "Unknown"
    assert results[0].banner == "Unknown"
