"""Lightweight service detection and banner grabbing.

No Nmap, no external APIs, no vulnerability scanning. Two layers, applied
per already-open port:

1. **Port-based guess** (`guess_service`) — a static well-known-port table.
   Always available, zero network cost.
2. **Banner grab** (`identify_service`) — a best-effort read (and, for a
   few protocols, a single minimal write) to see what the service says
   about itself: an SSH/FTP/SMTP/POP3/IMAP greeting, an HTTP `Server`
   header, a MySQL handshake packet, a Redis `INFO` reply. Anything else
   falls back to a passive read (`_grab_generic`) and, failing that, the
   literal string ``"Unknown"``.

`identify_service` never raises. A dead port, a timeout, a service that
sends nothing, or a service that sends garbage we can't decode all
degrade to `UNKNOWN` rather than propagating — banner grabbing is
strictly best-effort and must never be why a scan fails (see
DECISIONS.md).
"""

from __future__ import annotations

import re
import socket
import ssl

SERVICE_PORTS: dict[int, str] = {
    21: "FTP",
    22: "SSH",
    25: "SMTP",
    53: "DNS",
    80: "HTTP",
    110: "POP3",
    123: "NTP",
    143: "IMAP",
    389: "LDAP",
    443: "HTTPS",
    445: "SMB",
    3306: "MySQL",
    3389: "RDP",
    5432: "PostgreSQL",
    6379: "Redis",
    27017: "MongoDB",
}

UNKNOWN = "Unknown"

_SSH_PREFIX_RE = re.compile(r"^SSH-\d+\.\d+-")
_HTTP_SERVER_HEADER_RE = re.compile(rb"^Server:[ \t]*(.+?)\r?$", re.IGNORECASE | re.MULTILINE)
_REDIS_VERSION_RE = re.compile(rb"redis_version:([^\r\n]+)")

_GENERIC_READ_BYTES = 256
_HTTP_RESPONSE_LIMIT = 4096


def guess_service(port: int) -> str:
    """Best-effort service name from the well-known-port table."""
    return SERVICE_PORTS.get(port, UNKNOWN)


def identify_service(host: str, port: int, timeout: float = 1.5) -> tuple[str, str]:
    """Return `(service, banner)` for an already-confirmed-open `(host, port)`.

    Never raises: any socket/SSL/decoding failure while grabbing a banner
    degrades to `(guessed-or-Unknown service, "Unknown" banner)`.
    """
    grab = _BANNER_GRABBERS.get(port, _grab_generic)
    try:
        banner = grab(host, port, timeout)
    except Exception:
        # Deliberately broad: a banner grab is a best-effort bonus on top
        # of a scan that already succeeded. No exception here — a refused
        # connection, a timeout, a malformed response, an SSL handshake
        # failure — should ever surface as a scan failure.
        banner = None

    return guess_service(port), banner or UNKNOWN


def _read_line(sock: socket.socket, limit: int = 512) -> str:
    data = sock.recv(limit)
    return data.decode("utf-8", errors="replace").strip()


def _grab_generic(host: str, port: int, timeout: float) -> str | None:
    """Read-only: see if the service says anything without being asked.

    The fallback for every port with no protocol-specific grabber above
    (DNS, LDAP, SMB, RDP, PostgreSQL, MongoDB, NTP, and anything outside
    `SERVICE_PORTS` entirely) — most of those protocols expect the client
    to speak first, so this typically just waits out `timeout` and returns
    `None`. That's the graceful-degradation path, not an error.
    """
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        try:
            data = sock.recv(_GENERIC_READ_BYTES)
        except OSError:
            return None
    return data.decode("utf-8", errors="replace").strip() or None


def _grab_line_greeting(host: str, port: int, timeout: float) -> str | None:
    """FTP/SMTP/POP3/IMAP-style: the server sends a greeting unprompted."""
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        line = _read_line(sock)
    return line or None


def _grab_ssh(host: str, port: int, timeout: float) -> str | None:
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        line = _read_line(sock)
    if not line:
        return None
    return _SSH_PREFIX_RE.sub("", line) or line


def _http_head_request(host: str) -> bytes:
    return f"HEAD / HTTP/1.0\r\nHost: {host}\r\nConnection: close\r\n\r\n".encode("ascii")


def _recv_response_head(sock: socket.socket, limit: int = _HTTP_RESPONSE_LIMIT) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while total < limit:
        chunk = sock.recv(1024)
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if b"\r\n\r\n" in chunk:
            break
    return b"".join(chunks)


def _parse_http_server_header(data: bytes) -> str | None:
    match = _HTTP_SERVER_HEADER_RE.search(data)
    if not match:
        return None
    return match.group(1).decode("utf-8", errors="replace").strip() or None


def _grab_http(host: str, port: int, timeout: float) -> str | None:
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(_http_head_request(host))
        data = _recv_response_head(sock)
    return _parse_http_server_header(data)


def _grab_https(host: str, port: int, timeout: float) -> str | None:
    # A port scanner has no business validating the target's certificate —
    # we're identifying what's listening, not asserting it's trustworthy.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    with socket.create_connection((host, port), timeout=timeout) as raw_sock:
        with context.wrap_socket(raw_sock, server_hostname=host) as sock:
            sock.settimeout(timeout)
            sock.sendall(_http_head_request(host))
            data = _recv_response_head(sock)
    return _parse_http_server_header(data)


def _grab_mysql(host: str, port: int, timeout: float) -> str | None:
    """MySQL sends its version unprompted in the initial handshake packet:
    a 4-byte header, a 1-byte protocol version, then a NUL-terminated
    ASCII server version string (e.g. b"8.0.34" or b"5.7.30-log")."""
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        data = sock.recv(_GENERIC_READ_BYTES)
    if len(data) < 6:
        return None
    end = data.find(b"\x00", 5)
    if end == -1:
        return None
    version = data[5:end].decode("utf-8", errors="replace").strip()
    return f"MySQL {version}" if version else None


def _grab_redis(host: str, port: int, timeout: float) -> str | None:
    """Redis accepts inline commands pre-authentication. `INFO` (if the
    instance has no password) replies with a bulk string containing
    `redis_version:X.Y.Z` among other fields."""
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(b"INFO\r\n")
        data = sock.recv(4096)

    match = _REDIS_VERSION_RE.search(data)
    if match:
        return f"Redis {match.group(1).decode('ascii', errors='replace').strip()}"
    if data.startswith((b"-NOAUTH", b"-ERR", b"-WRONGPASS")):
        return "Redis (authentication required)"
    if data.startswith(b"+PONG"):
        return "Redis"
    return None


_BANNER_GRABBERS = {
    21: _grab_line_greeting,   # FTP
    22: _grab_ssh,
    25: _grab_line_greeting,   # SMTP
    80: _grab_http,
    110: _grab_line_greeting,  # POP3
    143: _grab_line_greeting,  # IMAP
    443: _grab_https,
    3306: _grab_mysql,
    6379: _grab_redis,
}
