"""Command-line interface for the port scanner."""

import argparse
import sys

from port_scanner.scanner import scan_range

MIN_PORT = 1
MAX_PORT = 65535
DEFAULT_PORTS = "1-1024"


def parse_ports(spec: str) -> list[int]:
    """Parse an nmap-style port spec into a sorted list of unique ports.

    Accepts comma-separated ports and dash ranges, e.g. "22,80,443,8000-8010".
    Raises ValueError on malformed or out-of-range input.
    """
    ports: set[int] = set()

    for token in spec.split(","):
        token = token.strip()
        if not token:
            raise ValueError(f"empty port entry in spec: {spec!r}")

        if "-" in token:
            start_str, _, end_str = token.partition("-")
            start, end = _to_port(start_str, spec), _to_port(end_str, spec)
            if start > end:
                raise ValueError(f"invalid range {token!r}: start > end")
            ports.update(range(start, end + 1))
        else:
            ports.add(_to_port(token, spec))

    return sorted(ports)


def _to_port(value: str, spec: str) -> int:
    value = value.strip()
    if not value.isdigit():
        raise ValueError(f"invalid port {value!r} in spec: {spec!r}")
    port = int(value)
    if not (MIN_PORT <= port <= MAX_PORT):
        raise ValueError(f"port {port} out of range ({MIN_PORT}-{MAX_PORT})")
    return port


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="port-scanner",
        description="Scan a host for open TCP ports.",
    )
    parser.add_argument("target", help="Hostname or IP address to scan")
    parser.add_argument(
        "--ports",
        default=DEFAULT_PORTS,
        help=(
            'Ports to scan, e.g. "22,80,443,8000-8010" '
            f"(default: {DEFAULT_PORTS})"
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=1.0,
        help="Per-port connection timeout in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=50,
        help="Number of concurrent worker threads (default: 50)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        ports = parse_ports(args.ports)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    open_ports = scan_range(
        args.target, ports, timeout=args.timeout, max_workers=args.workers
    )

    if open_ports:
        print(f"Open ports on {args.target}:")
        for port in open_ports:
            print(f"  {port}/tcp open")
    else:
        print(f"No open ports found on {args.target} in the scanned range.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
