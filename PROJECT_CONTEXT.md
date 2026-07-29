# PROJECT_CONTEXT.md

## Current status

Stable v1.0.0 CLI release. Core scanning engine, CLI, packaging, tests, and
CI are all complete and green (per the checklist in `README.md` and the
GitHub Actions workflow at `.github/workflows/ci.yml`).

## Version

`1.0.0` — as declared in `pyproject.toml` (`[project] version = "1.0.0"`).
Requires Python `>=3.10`; CI runs the suite on Python 3.14.

## Features implemented

- **TCP connect scanning** (`scan_port` in `src/port_scanner/scanner.py`) —
  uses `socket.connect_ex`, no raw sockets or elevated privileges required.
- **Concurrent scanning** (`scan_range`) — `ThreadPoolExecutor`-based, with
  a configurable `max_workers` (default 50).
- **Nmap-style port specs** (`parse_ports`/`_to_port` in
  `src/port_scanner/cli.py`) — supports comma lists and dash ranges
  (`22,80,443,8000-8010`), validates and deduplicates.
- **Configurable timeout and concurrency** — `--timeout` (default `1.0`s)
  and `--workers` (default `50`) CLI flags.
- **Scriptable exit codes** — `0` on completed scan, `2` on invalid port
  spec.
- **Installable CLI** — `port-scanner` console script
  (`port_scanner.cli:main`), installed via `pip install -e ".[dev]"`.
- **Automated test suite** — `tests/test_scanner.py` and
  `tests/test_cli.py`, using real local sockets rather than mocks.
- **CI** — GitHub Actions runs the full suite on every push and pull
  request (`ubuntu-latest`, Python 3.14).

## Current milestone

v1.0.0 stable release — all items in the "completed" section of
[`ROADMAP.md`](ROADMAP.md) are done.

## Next objective

Pick the next unstarted roadmap item. Per the existing roadmap ordering,
that is **service/banner detection** on open ports, followed by additional
output formats (JSON/table/file export). Neither has been started in code
as of this writing.
