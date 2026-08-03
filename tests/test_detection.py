"""Tests for port_scanner.detection: service guessing and banner grabbing.

Real local sockets, per this project's testing philosophy (see
docs/CLAUDE.md) — fake single-shot protocol servers on OS-assigned ports,
not mocked sockets. Two things can't be exercised this way and are
covered differently:

- `identify_service`'s port -> grabber dispatch (`_BANNER_GRABBERS`) is
  keyed by literal well-known port numbers (22, 80, 3306, ...), which
  tests can't bind without root. Dispatch itself is tested by
  monkeypatching the table to point our OS-assigned test port at a real
  grabber; the individual `_grab_*` functions are tested directly against
  fake servers on those OS-assigned ports (which works fine — they don't
  care what port number they're called with).
- `_grab_https`'s TLS handshake isn't exercised end-to-end (would need a
  throwaway self-signed cert); its HTTP-parsing logic is shared with
  `_grab_http` and is covered via `_parse_http_server_header` directly.
"""

import socket
import threading

import port_scanner.detection as detection
from port_scanner.detection import (
    UNKNOWN,
    _grab_generic,
    _grab_line_greeting,
    _grab_mysql,
    _grab_redis,
    _grab_ssh,
    _parse_http_server_header,
    guess_service,
    identify_service,
)


def _serve_once(behavior) -> int:
    """Bind an OS-assigned port, run `behavior(conn)` against the first
    connection in a background thread, then close. Returns the port."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    def _accept():
        conn, _ = server.accept()
        try:
            behavior(conn)
        except OSError:
            pass
        finally:
            conn.close()
            server.close()

    threading.Thread(target=_accept, daemon=True).start()
    return port


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class TestGuessService:
    def test_known_ports(self):
        assert guess_service(22) == "SSH"
        assert guess_service(80) == "HTTP"
        assert guess_service(443) == "HTTPS"
        assert guess_service(3306) == "MySQL"
        assert guess_service(5432) == "PostgreSQL"
        assert guess_service(6379) == "Redis"
        assert guess_service(27017) == "MongoDB"

    def test_all_sixteen_required_services_are_mapped(self):
        required = {
            "SSH", "HTTP", "HTTPS", "FTP", "SMTP", "POP3", "IMAP", "DNS",
            "MySQL", "PostgreSQL", "Redis", "MongoDB", "SMB", "LDAP",
            "RDP", "NTP",
        }
        assert required <= set(detection.SERVICE_PORTS.values())

    def test_unknown_port_falls_back(self):
        assert guess_service(59999) == UNKNOWN


class TestParseHttpServerHeader:
    def test_extracts_nginx(self):
        data = b"HTTP/1.1 200 OK\r\nServer: nginx/1.18.0\r\nContent-Length: 0\r\n\r\n"
        assert _parse_http_server_header(data) == "nginx/1.18.0"

    def test_extracts_apache(self):
        data = b"HTTP/1.1 200 OK\r\nServer: Apache/2.4.41 (Ubuntu)\r\n\r\n"
        assert _parse_http_server_header(data) == "Apache/2.4.41 (Ubuntu)"

    def test_extracts_caddy(self):
        data = b"HTTP/1.1 200 OK\r\nServer: Caddy\r\n\r\n"
        assert _parse_http_server_header(data) == "Caddy"

    def test_returns_none_without_server_header(self):
        data = b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n"
        assert _parse_http_server_header(data) is None


class TestBannerGrabbers:
    def test_grab_ssh_strips_protocol_prefix(self):
        port = _serve_once(lambda conn: conn.sendall(b"SSH-2.0-OpenSSH_9.6\r\n"))
        assert _grab_ssh("127.0.0.1", port, timeout=1.0) == "OpenSSH_9.6"

    def test_grab_ssh_keeps_line_without_recognizable_prefix(self):
        port = _serve_once(lambda conn: conn.sendall(b"not-an-ssh-banner\r\n"))
        assert _grab_ssh("127.0.0.1", port, timeout=1.0) == "not-an-ssh-banner"

    def test_grab_line_greeting_reads_ftp_style_banner(self):
        port = _serve_once(lambda conn: conn.sendall(b"220 (vsFTPd 3.0.5)\r\n"))
        assert _grab_line_greeting("127.0.0.1", port, timeout=1.0) == "220 (vsFTPd 3.0.5)"

    def test_grab_mysql_extracts_version_from_handshake(self):
        # 4-byte header + 1-byte protocol version + NUL-terminated version
        # string, exactly what a real MySQL server sends unprompted.
        payload = b"\x00\x00\x00\x00" + b"\x0a" + b"8.0.34" + b"\x00" + b"\x00" * 8
        port = _serve_once(lambda conn: conn.sendall(payload))
        assert _grab_mysql("127.0.0.1", port, timeout=1.0) == "MySQL 8.0.34"

    def test_grab_mysql_returns_none_on_short_garbage(self):
        port = _serve_once(lambda conn: conn.sendall(b"\x01\x02"))
        assert _grab_mysql("127.0.0.1", port, timeout=1.0) is None

    def test_grab_redis_extracts_version_from_info_reply(self):
        def behavior(conn):
            conn.recv(4096)  # the "INFO\r\n" command
            conn.sendall(b"$64\r\n# Server\r\nredis_version:7.2.3\r\nredis_mode:standalone\r\n")

        port = _serve_once(behavior)
        assert _grab_redis("127.0.0.1", port, timeout=1.0) == "Redis 7.2.3"

    def test_grab_redis_reports_auth_required(self):
        def behavior(conn):
            conn.recv(4096)
            conn.sendall(b"-NOAUTH Authentication required.\r\n")

        port = _serve_once(behavior)
        assert _grab_redis("127.0.0.1", port, timeout=1.0) == "Redis (authentication required)"

    def test_grab_generic_reads_unsolicited_bytes(self):
        port = _serve_once(lambda conn: conn.sendall(b"hello there\n"))
        assert _grab_generic("127.0.0.1", port, timeout=1.0) == "hello there"

    def test_grab_generic_returns_none_when_server_stays_silent(self):
        port = _serve_once(lambda conn: None)  # accept, then say nothing
        assert _grab_generic("127.0.0.1", port, timeout=0.3) is None


class TestIdentifyService:
    def test_never_raises_on_connection_refused(self):
        port = _free_port()  # nothing listening
        service, banner = identify_service("127.0.0.1", port, timeout=0.3)
        assert banner == UNKNOWN

    def test_falls_back_to_unknown_for_a_silent_service(self):
        port = _serve_once(lambda conn: None)
        service, banner = identify_service("127.0.0.1", port, timeout=0.3)
        assert service == UNKNOWN  # not one of the 16 well-known ports
        assert banner == UNKNOWN

    def test_dispatches_to_the_right_grabber_for_the_port(self, monkeypatch):
        port = _serve_once(lambda conn: conn.sendall(b"SSH-2.0-OpenSSH_9.6\r\n"))
        monkeypatch.setitem(detection._BANNER_GRABBERS, port, detection._grab_ssh)
        monkeypatch.setitem(detection.SERVICE_PORTS, port, "SSH")

        service, banner = identify_service("127.0.0.1", port, timeout=1.0)

        assert service == "SSH"
        assert banner == "OpenSSH_9.6"

    def test_swallows_a_broken_grabber_without_raising(self, monkeypatch):
        port = _serve_once(lambda conn: None)

        def _broken_grabber(host, port, timeout):
            raise RuntimeError("boom")

        monkeypatch.setitem(detection._BANNER_GRABBERS, port, _broken_grabber)

        service, banner = identify_service("127.0.0.1", port, timeout=0.3)

        assert banner == UNKNOWN
