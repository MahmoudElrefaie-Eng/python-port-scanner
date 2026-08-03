# PROJECT_CONTEXT.md

## Current status

Stable v1.0.0 CLI release. Core scanning engine, CLI, packaging, tests, and
CI are all complete and green (per the checklist in `README.md` and the
GitHub Actions workflow at `.github/workflows/ci.yml`).

A FastAPI web interface skeleton (`src/port_scanner/web/`) now exists as a
peer to `cli.py` — see [`ARCHITECTURE.md`](ARCHITECTURE.md). It has no scan
logic wired in yet: app factory, env-var configuration, centralized
logging, global exception handling, `/api/v1` versioning scaffold,
`/health`, and customized OpenAPI docs only (`tests/test_web.py`, 10 tests).
Install it with `pip install -e ".[dev,web]"`.

## Version

`1.0.0` — as declared in `pyproject.toml` (`[project] version = "1.0.0"`).
Requires Python `>=3.10`; CI runs the suite on Python 3.14.

## Features implemented

- **TCP connect scanning** (`scan_port` in `src/port_scanner/scanner.py`) —
  uses `socket.connect_ex`, no raw sockets or elevated privileges required.
- **Concurrent scanning** (`scan_range`) — `ThreadPoolExecutor`-based, with
  a configurable `max_workers` (default 50).
- **Nmap-style port specs** (`parse_ports`/`_to_port` in
  `src/port_scanner/parsing.py`) — supports comma lists and dash ranges
  (`22,80,443,8000-8010`), validates and deduplicates. `cli.py` imports
  this rather than defining it, so any future interface can reuse it too
  (see [`ARCHITECTURE.md`](ARCHITECTURE.md)).
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

v1.0.0 stable CLI release is done. In parallel, Phase 3's web interface is
underway: Milestone 1 (FastAPI skeleton) is complete; Milestone 2 (the
actual scan flow behind it) has not started.

## Next objective

Web interface Milestone 2: wire `GET /` and `POST /scan` (server-rendered
HTML form, no JS) to `parse_ports`/`scan_range`, add `templates/` and
`static/css/style.css`. Requires explicit approval before starting per the
working agreement in this repo. Separately, Phase 2 (service/banner
detection, additional output formats) remains unstarted and available to
pick up instead — see [`ROADMAP.md`](ROADMAP.md).
