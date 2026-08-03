"""Combines the scan engine with service detection into structured results.

The single place both interfaces (`cli.py`, `web/`) call for a "detailed"
scan — neither talks to `scanner.py` or `detection.py` directly for this,
so the two-phase process below (scan, then identify) exists in exactly one
place. See DECISIONS.md for why it's a two-phase process rather than one.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from typing import Iterable

from port_scanner.detection import identify_service
from port_scanner.scanner import scan_range

STATE_OPEN = "OPEN"


@dataclass(frozen=True)
class PortResult:
    """One open port, with what we could determine is running on it."""

    port: int
    state: str
    service: str
    banner: str


def discover(
    host: str,
    ports: Iterable[int],
    timeout: float = 1.0,
    max_workers: int = 50,
) -> list[PortResult]:
    """Scan `host` over `ports`, then identify the service on each open one.

    Two phases, not one:

    1. `scan_range` — the existing, unmodified connect-scan engine — finds
       which ports are open. Fast: one connect attempt per port.
    2. `identify_service` runs only against the ports phase 1 found open
       (typically a small subset of what was scanned), each in its own
       thread. This is what keeps banner grabbing from meaningfully
       slowing down a scan of, say, 1-1024: the vast majority of closed
       ports never get a second connection at all.
    """
    open_ports = scan_range(host, ports, timeout=timeout, max_workers=max_workers)
    if not open_ports:
        return []

    identify = partial(identify_service, host, timeout=timeout)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        identified = list(executor.map(identify, open_ports))

    return [
        PortResult(port=port, state=STATE_OPEN, service=service, banner=banner)
        for port, (service, banner) in zip(open_ports, identified)
    ]
