"""Runs a scan on behalf of the web form.

This is the *only* place in `web/` that imports `parse_ports`/`discover`
— no route module talks to the scanning/detection core directly. It
exists to add the things a public HTTP form needs that a local CLI
invocation doesn't:

- input bounds (a stranger on the internet can submit anything a `<form>`
  will let them, unlike argv typed by whoever is running the CLI locally)
- translating `ValueError`/`OSError` into `ScanFormError`, whose message is
  safe to render straight into the page (see `routes/pages.py`)

No scanning, parsing, or service-detection logic is duplicated: this
module validates bounds and translates exceptions, nothing more — the CLI
(`cli.py`) and this module both call `port_scanner.discovery.discover`,
the one shared entrypoint, and so always see identical results for the
same inputs.
"""

from __future__ import annotations

import time

from port_scanner.discovery import discover
from port_scanner.parsing import parse_ports
from port_scanner.web.schemas.scan import PortResultView, ScanFormData, ScanResultView

# Bounds beyond what parse_ports/scan_range enforce themselves. The CLI has
# none of these because argv is typed by whoever runs it locally; this form
# is reachable by anyone who can reach the server.
MAX_PORTS_PER_SCAN = 1024  # matches the CLI's own default range, 1-1024
MIN_TIMEOUT = 0.1
MAX_TIMEOUT = 10.0
MIN_WORKERS = 1
MAX_WORKERS = 200


class ScanFormError(ValueError):
    """A validation failure whose message is safe to display to the user."""


def run_scan(form: ScanFormData) -> ScanResultView:
    """Validate `form`, run the scan, and return a template-ready result.

    Raises `ScanFormError` for anything the user can fix by changing their
    input — a bad port spec, an out-of-range timeout, an unresolvable
    target. Anything else (a genuine bug) is left to propagate to the
    global exception handler.
    """
    target = form.target.strip()
    if not target:
        raise ScanFormError("Target is required.")

    timeout = _parse_float(form.timeout, "Timeout")
    if not (MIN_TIMEOUT <= timeout <= MAX_TIMEOUT):
        raise ScanFormError(
            f"Timeout must be between {MIN_TIMEOUT} and {MAX_TIMEOUT} seconds."
        )

    workers = _parse_int(form.workers, "Workers")
    if not (MIN_WORKERS <= workers <= MAX_WORKERS):
        raise ScanFormError(
            f"Workers must be a whole number between {MIN_WORKERS} and {MAX_WORKERS}."
        )

    try:
        ports = parse_ports(form.ports)
    except ValueError as exc:
        raise ScanFormError(str(exc)) from exc

    if len(ports) > MAX_PORTS_PER_SCAN:
        raise ScanFormError(
            f"Too many ports requested ({len(ports)}). Narrow the range to "
            f"at most {MAX_PORTS_PER_SCAN} ports per scan."
        )

    started = time.monotonic()
    try:
        port_results = discover(target, ports, timeout=timeout, max_workers=workers)
    except OSError as exc:
        # Covers socket.gaierror (DNS resolution failure) and friends —
        # all subclasses of OSError.
        raise ScanFormError(f"Could not scan {target!r}: {exc}") from exc
    elapsed = time.monotonic() - started

    return ScanResultView(
        target=target,
        results=[
            PortResultView(port=r.port, state=r.state, service=r.service, banner=r.banner)
            for r in port_results
        ],
        ports_scanned=len(ports),
        timeout=timeout,
        workers=workers,
        elapsed_seconds=elapsed,
    )


def _parse_float(value: str, field: str) -> float:
    try:
        return float(value)
    except ValueError:
        raise ScanFormError(f"{field} must be a number.") from None


def _parse_int(value: str, field: str) -> int:
    try:
        return int(value)
    except ValueError:
        raise ScanFormError(f"{field} must be a whole number.") from None
