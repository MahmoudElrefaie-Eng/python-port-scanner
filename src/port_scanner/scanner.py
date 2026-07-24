"""Core TCP connect-scan engine."""

import socket
from typing import Iterable


def scan_port(host: str, port: int, timeout: float = 1.0) -> bool:
    """Return True if a TCP connection to (host, port) succeeds, else False."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        return result == 0


def scan_range(host: str, ports: Iterable[int], timeout: float = 1.0) -> list[int]:
    """Scan each port in `ports` sequentially, returning the list of open ports."""
    return [port for port in ports if scan_port(host, port, timeout)]
