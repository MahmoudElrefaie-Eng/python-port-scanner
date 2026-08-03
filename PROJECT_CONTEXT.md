# PROJECT_CONTEXT.md

## Current status

Stable v1.0.0 CLI release. Core scanning engine, CLI, packaging, tests, and
CI are all complete and green (per the checklist in `README.md` and the
GitHub Actions workflow at `.github/workflows/ci.yml`).

The project is evolving further still, from a network discovery platform
into a professional **Security Assessment Platform** — discovery plus
vulnerability matching, risk scoring, and (later) reporting, compliance,
threat intelligence, and AI-assisted analysis. See
[Direction in `ROADMAP.md`](ROADMAP.md#direction).

A FastAPI web interface (`src/port_scanner/web/`) exists as a peer to
`cli.py` — see [`ARCHITECTURE.md`](ARCHITECTURE.md). Milestone 1 (app
factory, env-var configuration, centralized logging, global exception
handling, `/api/v1` versioning scaffold, `/health`, customized OpenAPI
docs), Milestone 2 (a server-rendered scan flow: `GET /` and `POST /scan`,
Jinja2 templates, a plain CSS stylesheet, validation errors shown inline
instead of raw exceptions), and Milestone 3 (service detection & banner
grabbing, shared by the CLI and the web UI) are all complete. Milestone 4
(`src/port_scanner/security/` — vulnerability matching, risk scoring, a
multi-provider abstraction with two working providers) is also complete
but **not yet wired into either interface** — see below and
[Decision 30](DECISIONS.md). No auth, database, or async job queue yet —
deliberately deferred, see [Decision 26](DECISIONS.md).

137 tests total (`test_scanner.py` 5, `test_cli.py` 15, `test_detection.py`
20, `test_discovery.py` 5, `test_web.py` 23, `test_security_matching.py`
29, `test_security_risk.py` 13, `test_security_cve_db.py` 6,
`test_security_providers.py` 10, `test_security_engine.py` 11). Install
with `pip install -e ".[dev,web]"` (the `security/` package is stdlib-only
— no new extra needed), run the CLI with `port-scanner ...` or the web
app with `uvicorn port_scanner.web.app:app`.

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
- **Service detection** (`guess_service` in `src/port_scanner/detection.py`)
  — a well-known-port table covering 16 services (SSH, HTTP, HTTPS, FTP,
  SMTP, POP3, IMAP, DNS, MySQL, PostgreSQL, Redis, MongoDB, SMB, LDAP,
  RDP, NTP).
- **Banner grabbing** (`identify_service`, same module) — protocol-aware
  probes for 9 of those 16 (SSH/FTP/SMTP/POP3/IMAP greetings, HTTP/HTTPS
  `Server` header, MySQL handshake version, Redis `INFO`); the rest fall
  back to a passive read, then `"Unknown"`. Never fails a scan — see
  [Decision 23](DECISIONS.md). No Nmap, no external APIs, no
  vulnerability scanning ([Decision 21](DECISIONS.md)).
- **Structured scan results** (`discover`/`PortResult` in
  `src/port_scanner/discovery.py`) — the single shared entrypoint both
  `cli.py` and the web UI call; combines `scanner.py` + `detection.py`
  into `port`/`state`/`service`/`banner` per open port
  ([Decision 20](DECISIONS.md)).
- **Configurable timeout and concurrency** — `--timeout` (default `1.0`s)
  and `--workers` (default `50`) CLI flags.
- **Scriptable exit codes** — `0` on completed scan, `2` on invalid port
  spec.
- **Installable CLI** — `port-scanner` console script
  (`port_scanner.cli:main`), installed via `pip install -e ".[dev]"`.
  Output is a hand-rolled table (`PORT`/`STATE`/`SERVICE`/`BANNER`, no new
  dependency — [Decision 25](DECISIONS.md)).
- **Web interface** (`src/port_scanner/web/`) — FastAPI, server-rendered
  with Jinja2 (no JS); `GET /` and `POST /scan`, results table with
  `Port`/`Status`/`Service`/`Banner` columns.
- **Vulnerability matching & risk scoring** (`security/engine.py`'s
  `assess()`) — takes `discovery.discover()`'s output and returns a
  `Host` -> `Service` -> `Finding` -> `Vulnerability` graph
  ([Decision 28](DECISIONS.md)), asset-management-shaped. Not yet called
  by either interface — see "Current milestone" below.
- **Multi-provider vulnerability lookup** (`security/providers/`) — a
  `VulnerabilityProvider` Protocol; `LocalCVEProvider` (offline, SQLite
  cache, `security/cve_db.py`) checked first, `NVDProvider` (live NVD
  REST API v2.0, verified against the real API) queried on a cache miss
  and written back into the cache. OSV/Vulners are designed for but not
  yet implemented ([Decision 30](DECISIONS.md)).
- **CVSS-based risk levels & recommendations** (`security/risk.py`) —
  worst-case aggregation per service/host, deterministic (non-AI)
  remediation text.
- **Automated test suite** — 137 tests using real local sockets (and, for
  the one genuinely-external dependency, a local fake HTTP server rather
  than mocks — see ARCHITECTURE.md's testing-strategy note) — see
  [`docs/CLAUDE.md`](docs/CLAUDE.md) for the testing philosophy.
- **CI** — GitHub Actions runs the full suite on every push and pull
  request (`ubuntu-latest`, Python 3.14).

## Current milestone

v1.0.0 stable CLI release is done. Phase 3's web interface has completed
three milestones: FastAPI skeleton, server-rendered scan flow, and service
detection & banner grabbing. Phase 4 (Security Assessment Platform) has
completed Milestone 4: the `security/` engine — data models, matching,
risk scoring, and a working two-provider abstraction — built, tested
(including a live check against the real NVD API), and documented, but
**not called by `cli.py` or `web/` yet**. Auth, scan history, and user
accounts remain planned but deliberately deferred — see
[Decision 26](DECISIONS.md) — and need explicit approval before they
begin, per the working agreement in this repo.

## Next objective

Wait for direction on what's next. Candidates, none started: Milestone 5
— wiring `security.engine.assess()` into `cli.py` (a flag) and `web/` (a
checkbox, a new `assessment_service.py`, a `web/api/v1` JSON endpoint);
OSV/Vulners providers; expanding banner grabbing to the 7 services that
currently only get a port-based guess (DNS, LDAP, SMB, RDP, PostgreSQL,
MongoDB, NTP — see [Decision 22](DECISIONS.md)); JSON/file export output
formats; the deferred web auth/history/accounts milestone; deployment.
See [`ROADMAP.md`](ROADMAP.md).
