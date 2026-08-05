"""Command-line interface for the port scanner."""

import argparse
import sys

from port_scanner.discovery import PortResult, discover
from port_scanner.parsing import parse_ports
from port_scanner.security.engine import assess
from port_scanner.security.models import Host

DEFAULT_PORTS = "1-1024"
_TABLE_HEADERS = ("PORT", "STATE", "SERVICE", "BANNER")
_COLUMN_GAP = "  "


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
    parser.add_argument(
        "--assess",
        action="store_true",
        help=(
            "Assess detected services for known vulnerabilities "
            "(local cache first, then a live NVD lookup on a cache miss)"
        ),
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="With --assess, use the local CVE cache only; skip live NVD lookups",
    )
    return parser


def _format_table(results: list[PortResult]) -> str:
    """Render `results` as a fixed-width table, columns sized to content."""
    rows = [(str(r.port), r.state, r.service, r.banner) for r in results]
    columns = [_TABLE_HEADERS, *rows]
    widths = [max(len(row[i]) for row in columns) for i in range(len(_TABLE_HEADERS))]

    def format_row(row: tuple[str, ...]) -> str:
        return _COLUMN_GAP.join(cell.ljust(width) for cell, width in zip(row, widths))

    lines = [
        format_row(_TABLE_HEADERS),
        format_row(tuple("-" * width for width in widths)),
        *(format_row(row) for row in rows),
    ]
    return "\n".join(lines)


def _format_security_report(host: Host) -> str:
    """Render `host` (as returned by `security.engine.assess()`) as a
    stdlib-only text report, printed below the port table when --assess
    is given. Mirrors what the web UI shows for the same data — Service,
    Banner, Risk Level, matched vulnerabilities, and recommendations."""
    lines = [f"Security assessment for {host.target}: host risk = {host.risk_level.value}", ""]
    for service in host.services:
        lines.append(
            f"Port {service.port} ({service.service_name}) - {service.banner} "
            f"- risk: {service.risk_level.value}"
        )
        if service.findings:
            for finding in service.findings:
                cve = finding.vulnerability.cve_id
                score = (
                    f" (CVSS {finding.vulnerability.cvss_score})"
                    if finding.vulnerability.cvss_score is not None
                    else ""
                )
                lines.append(f"  - {cve}{score}: {finding.vulnerability.description}")
                lines.append(f"    Recommendation: {finding.recommendation}")
        else:
            lines.append(
                "  No known vulnerabilities matched (approximate matching; "
                "not a confirmed clean bill of health)."
            )
        lines.append("")
    return "\n".join(lines).rstrip("\n")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        ports = parse_ports(args.ports)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    results = discover(
        args.target, ports, timeout=args.timeout, max_workers=args.workers
    )

    if results:
        print(f"Open ports on {args.target}:\n")
        print(_format_table(results))
    else:
        print(f"No open ports found on {args.target} in the scanned range.")

    if args.assess:
        print()
        if results:
            host = assess(args.target, results, providers=() if args.offline else None)
            print(_format_security_report(host))
        else:
            print(f"No open ports to assess on {args.target}.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
