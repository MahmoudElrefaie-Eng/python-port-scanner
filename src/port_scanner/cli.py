"""Command-line interface for the port scanner."""

import argparse
import sys

from port_scanner.parsing import parse_ports
from port_scanner.scanner import scan_range

DEFAULT_PORTS = "1-1024"


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
