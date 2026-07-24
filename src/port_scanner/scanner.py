"""Core TCP connect-scan engine."""

import socket
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Iterable


def scan_port(host: str, port: int, timeout: float = 1.0) -> bool:
    """Return True if a TCP connection to (host, port) succeeds, else False."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        return result == 0


def scan_range(
    host: str,
    ports: Iterable[int],
    timeout: float = 1.0,
    max_workers: int = 50,
) -> list[int]:
    """Scan `ports` concurrently, returning the open ones in ascending order.

    scan_port opens its own socket per call and shares no state, so it is
    safe to run across threads without locking.
    """
    ports = list(ports)
    check_port = partial(scan_port, host, timeout=timeout)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        is_open = executor.map(check_port, ports)

    return sorted(port for port, open_ in zip(ports, is_open) if open_)
