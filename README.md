# Port Scanner

[![CI](https://github.com/MahmoudElrefaie-Eng/python-port-scanner/actions/workflows/ci.yml/badge.svg)](https://github.com/MahmoudElrefaie-Eng/python-port-scanner/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](.github/workflows/ci.yml)

A fast, concurrent TCP port scanner built in Python, developed as part of a
cybersecurity portfolio. It scans a host over Nmap-style port specs using a
thread pool and ships as an installable CLI (`port-scanner`) with a full
automated test suite and CI.

## Table of Contents

- [Project Status](#project-status)
- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Usage](#usage)
- [CLI Examples](#cli-examples)
- [Web Interface](#web-interface)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Continuous Integration](#continuous-integration)
- [Roadmap](#roadmap)
- [Documentation](#documentation)
- [Disclaimer](#disclaimer)
- [License](#license)

## Project Status

- ✅ Stable CLI release
- ✅ Automated testing with GitHub Actions
- ✅ Web interface: FastAPI skeleton (no scan flow yet — see below)
- 🚧 Planned features:
  - Service/banner detection
  - JSON export
  - Web interface: scan flow (`GET /`, `POST /scan`)

## Features

- **TCP connect scanning** — reliable, works without elevated privileges
  (no raw sockets required).
- **Concurrent scanning** — a `ThreadPoolExecutor` scans many ports in
  parallel instead of one at a time, so scanning 1,000 ports takes roughly
  as long as the slowest single connection, not the sum of all of them.
- **Nmap-style port specs** — `22,80,443,8000-8010` style input, with
  validation and clear error messages for malformed specs.
- **Configurable timeout and concurrency** — tune `--timeout` and
  `--workers` per scan for speed vs. reliability trade-offs.
- **Scriptable exit codes** — `0` for a completed scan, `2` for invalid
  input — safe to use in shell pipelines and automation.
- **Fully tested** — unit tests for the scan engine, port-spec parser, and
  CLI, run automatically on every push via GitHub Actions.

## Architecture

```mermaid
flowchart TD
    A[User] -->|"port-scanner target --ports ..."| B["CLI (cli.py)"]
    B --> C["parsing.py: parse_ports()<br/>Nmap-style port spec parsing"]
    C --> D["scan_range()<br/>ThreadPoolExecutor"]
    D --> E1["scan_port() worker"]
    D --> E2["scan_port() worker"]
    D --> E3["scan_port() worker N"]
    E1 --> F[Sorted Scan Results]
    E2 --> F
    E3 --> F
    F --> G[Results printed to stdout]
```

Each `scan_port()` call opens its own socket and shares no state with the
others, so the thread pool needs no locking — this is what keeps the
concurrency model simple.

## Installation

Requires Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

The web interface (see [Web Interface](#web-interface)) is an optional
extra — the base install above stays dependency-free:

```bash
pip install -e ".[dev,web]"
```

## Usage

```bash
port-scanner 127.0.0.1 --ports 22,80,443,8000-8010
port-scanner example.com --ports 1-1024 --timeout 0.5 --workers 100
```

Example output:

```
Open ports on 127.0.0.1:
  8000/tcp open
```

If no ports in the scanned range are open:

```
No open ports found on 127.0.0.1 in the scanned range.
```

## CLI Examples

Scan well-known ports with defaults (ports `1-1024`, 1s timeout, 50 workers):

```bash
port-scanner 127.0.0.1
```

Scan a specific list and range together:

```bash
port-scanner 192.168.1.1 --ports 22,80,443,8000-8010
```

Scan faster with more workers and a shorter timeout (useful on responsive
local networks):

```bash
port-scanner 10.0.0.5 --ports 1-65535 --timeout 0.3 --workers 200
```

Invalid port specs fail fast with exit code `2` instead of scanning:

```bash
$ port-scanner 127.0.0.1 --ports abc
error: invalid port 'abc' in spec: 'abc'
```

A successful scan (open ports found or not) exits with status code `0`.

## Web Interface

A FastAPI web interface lives at `src/port_scanner/web/`, as a peer to the
CLI — it depends only on `scanner.py`/`parsing.py`, never on `cli.py`. As
of this writing it's a skeleton only: application factory, environment-
variable configuration, centralized logging, global exception handling,
`/api/v1` versioning scaffold, `/health`, and customized OpenAPI docs. It
does not yet expose any scanning functionality.

```bash
pip install -e ".[dev,web]"
uvicorn port_scanner.web.app:app --reload
```

- `GET /health` — liveness check
- `GET /docs`, `GET /redoc` — interactive API documentation
- `GET /openapi.json` — OpenAPI schema

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the design and
[`ROADMAP.md`](ROADMAP.md) for what's planned next (the scan flow itself).

## Project Structure

```
python-port-scanner/
├── .github/workflows/  # CI workflow (GitHub Actions)
│   └── ci.yml
├── src/port_scanner/   # installable package source
│   ├── scanner.py      # scan_port / scan_range (TCP connect scan engine)
│   ├── parsing.py      # parse_ports (Nmap-style port-spec parsing)
│   ├── cli.py          # command-line interface
│   └── web/            # FastAPI interface (skeleton only, see above)
│       ├── app.py          # create_app() factory
│       ├── core/            # config, logging, exceptions
│       ├── api/v1/           # versioned API router (empty scaffold)
│       ├── routes/            # unversioned routes (health)
│       └── schemas/            # Pydantic models
├── tests/              # test suite
├── pyproject.toml      # packaging & dependencies
├── README.md
├── .gitignore
└── LICENSE
```

## Testing

Run the test suite locally:

```bash
pytest
```

## Continuous Integration

Every push and pull request runs the full test suite on `ubuntu-latest`
with Python 3.14 via GitHub Actions, installing the project the same way a
developer would locally (`pip install -e ".[dev,web]"`). See
[`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## Roadmap

- [x] Project scaffolding, Git, README, licensing
- [x] Core TCP connect scanning engine
- [x] Concurrency (threaded scanning for speed)
- [x] CLI interface (argument parsing, target/port range input)
- [x] Packaging (`pyproject.toml`, installable console script)
- [x] Test suite
- [x] CI (automated tests on every push)
- [ ] Service/banner detection
- [ ] Output formats (JSON, table, file export)
- [x] Web interface — Milestone 1: FastAPI skeleton
- [ ] Web interface — Milestone 2: scan flow
- [ ] Deployment

## Documentation

Further project documentation lives at the repository root:

- [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) — current status and next objective
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — code structure and design rationale
- [`ROADMAP.md`](ROADMAP.md) — detailed, phased roadmap
- [`DECISIONS.md`](DECISIONS.md) — architectural decisions and rationale

## Disclaimer

This tool is intended for authorized security testing and educational use only (e.g., scanning systems you own or have explicit permission to test). Unauthorized port scanning of systems you do not own or have permission to test may be illegal in your jurisdiction.

## License

MIT — see [LICENSE](LICENSE).
