"""Nmap-style port-spec parsing."""

MIN_PORT = 1
MAX_PORT = 65535


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
