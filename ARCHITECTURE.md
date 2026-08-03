# ARCHITECTURE.md

## Overview

`port-scanner` is evolving from a TCP port scanner into a lightweight
network discovery platform: not just *which* ports are open, but *what's
running on them*. It remains a layered application with no third-party
runtime dependencies for its core:

- **Interface layer** — `src/port_scanner/cli.py`: argument parsing
  (`argparse`), table output formatting, process exit codes. It calls into
  the shared logic layer below and contains no scanning, parsing, or
  detection logic of its own.
- **Shared logic layer** — four independent modules. None depends on
  another peer in this layer except where noted, and none depends on any
  interface:
  - `src/port_scanner/scanner.py` — the scan engine (`scan_port`,
    `scan_range`). Unmodified since Phase 1.
  - `src/port_scanner/parsing.py` — Nmap-style port-spec parsing
    (`parse_ports`, `_to_port`). Unmodified since Phase 1.
  - `src/port_scanner/detection.py` — service guessing and banner
    grabbing (`guess_service`, `identify_service`). New in Milestone 3.
    Depends on nothing else in this layer.
  - `src/port_scanner/discovery.py` — orchestrates the other three into
    structured results (`discover`, `PortResult`). New in Milestone 3.
    The only module in this layer that depends on peers (`scanner.py` and
    `detection.py`) — see [Decision 20](DECISIONS.md).

Any interface (`cli.py` today; `web/` as of Milestone 2) depends downward
on `discovery.py` (which in turn depends on `scanner.py` and
`detection.py`) and `parsing.py`. Interfaces never depend on each other.
See [`ROADMAP.md`](ROADMAP.md) for where this is headed.

## Diagram

```mermaid
flowchart TD
    A[User / shell / browser] -->|"target, ports, timeout, workers"| B["interface: cli.py or web/"]
    B --> C["parsing.py: parse_ports()<br/>Nmap-style spec parsing & validation"]
    C -->|invalid spec| X["error shown to user<br/>(exit code 2 / inline HTML)"]
    C -->|valid ports| D["discovery.py: discover()"]
    D --> E["scanner.py: scan_range()<br/>ThreadPoolExecutor, one connect per port"]
    E --> F["open ports only"]
    F --> G["detection.py: identify_service()<br/>ThreadPoolExecutor, one per OPEN port"]
    G --> G1["guess_service(): port &rarr; name table"]
    G --> G2["protocol-aware banner grab<br/>(read-only or one small write)"]
    G1 --> H["list[PortResult]<br/>port / state / service / banner"]
    G2 --> H
    H --> I["cli.py: professional table on stdout<br/>web/: Port/Status/Service/Banner table"]
```

## Layers, in detail

### `scanner.py` — scan engine

- `scan_port(host, port, timeout) -> bool`: opens one `socket.AF_INET,
  socket.SOCK_STREAM`, calls `connect_ex`, returns whether it succeeded.
  Fully self-contained — opens and closes its own socket, touches no
  shared state.
- `scan_range(host, ports, timeout, max_workers) -> list[int]`: fans
  `scan_port` out across a `ThreadPoolExecutor`, then returns the open
  ports sorted ascending.

### `parsing.py` — port-spec parsing

- `parse_ports(spec) -> list[int]` / `_to_port`: turns an Nmap-style string
  (`"22,80,443,8000-8010"`) into a validated, deduplicated, sorted list of
  port numbers, raising `ValueError` with a specific message on malformed
  input. Pure string-to-data logic — no knowledge of `argparse`, console
  output, or process exit codes, so any interface can reuse it unchanged.

### `detection.py` — service guessing and banner grabbing

No Nmap, no external APIs, no vulnerability scanning — see
[Decision 21](DECISIONS.md) for why that's a hard boundary, not just a
starting point. Two layers, both pure stdlib (`socket`, `ssl`, `re`):

- `guess_service(port) -> str`: a static well-known-port table
  (`SERVICE_PORTS`) covering the 16 services this milestone requires —
  SSH, HTTP, HTTPS, FTP, SMTP, POP3, IMAP, DNS, MySQL, PostgreSQL, Redis,
  MongoDB, SMB, LDAP, RDP, NTP. Falls back to `"Unknown"`. Zero network
  cost, always available.
- `identify_service(host, port, timeout) -> (service, banner)`: the guess
  above, plus a best-effort banner grab. A per-port dispatch table
  (`_BANNER_GRABBERS`) routes to a protocol-aware grabber for 9 of the 16
  services — SSH, FTP, SMTP, POP3, IMAP (read the greeting the server
  sends unprompted), HTTP/HTTPS (send a minimal `HEAD /` and read the
  `Server` header), MySQL (parse the version string out of its unprompted
  initial handshake packet), Redis (send `INFO`, parse `redis_version`
  from the reply). Everything else — DNS, LDAP, SMB, RDP, PostgreSQL,
  MongoDB, NTP, and any port outside the table entirely — falls through
  to `_grab_generic`, a passive read with no write, which returns
  whatever the service says unprompted (some do) or `None` after
  `timeout` (most, since these protocols expect the client to speak
  first — see [Decision 22](DECISIONS.md) for why they don't get a real
  probe in this milestone). `identify_service` never raises: any
  connection failure, timeout, or decoding error while grabbing a banner
  degrades to `(guessed-or-"Unknown" service, "Unknown" banner)` — see
  [Decision 23](DECISIONS.md).

### `discovery.py` — combines scanning with detection

- `discover(host, ports, timeout, max_workers) -> list[PortResult]`,
  where `PortResult` is a frozen dataclass of `port`, `state` (always
  `"OPEN"` — `scan_range` only ever returns open ports), `service`,
  `banner`.
- Two sequential phases, not one: `scan_range` finds which ports are open
  first; only *those* ports (typically a small fraction of what was
  scanned) get a second connection from `identify_service`, run
  concurrently in their own `ThreadPoolExecutor`. See
  [Decision 20](DECISIONS.md) for why this is a separate module rather
  than folded into `scanner.py`, and [Decision 24](DECISIONS.md) for the
  performance reasoning behind the two-phase split.
- This is the one shared entrypoint both interfaces call for a detailed
  scan — `cli.py` and `web/services/scan_service.py` each call `discover`
  directly and render its `list[PortResult]`, never `scan_range` or
  `identify_service` individually. That's what makes "the CLI and Web UI
  consume exactly the same scanning results" true by construction rather
  than by convention.

### `cli.py` — interface

- Imports `parse_ports` from `parsing.py` and `discover`/`PortResult` from
  `discovery.py`. Does not import `scanner.py` or `detection.py` directly.
- `build_parser()`: defines the `argparse` CLI surface (`target`, `--ports`,
  `--timeout`, `--workers`) — unchanged by Milestone 3; no new flags.
- `_format_table(results) -> str`: a small hand-rolled fixed-width table
  formatter (headers `PORT`/`STATE`/`SERVICE`/`BANNER`, columns sized to
  the widest cell). Pure stdlib — no `tabulate`/`rich` dependency, for the
  same reason `scanner.py`/`parsing.py` are stdlib-only (see Decision 5 in
  [`DECISIONS.md`](DECISIONS.md)); `cli.py`'s base install stays
  dependency-free.
- `main(argv=None) -> int`: wires parsing → `discover` → table output →
  exit code. This is the function exposed as the `port-scanner` console
  script entry point (`pyproject.toml`: `port-scanner = "port_scanner.cli:main"`).
  Exit code contract unchanged: `0` on a completed scan, `2` on invalid
  input.

### `web/` — FastAPI interface

A second interface, peer to `cli.py`, structured as a small package rather
than a single module:

```
src/port_scanner/web/
├── app.py               # create_app() factory; module-level `app` for uvicorn
├── core/
│   ├── config.py         # Settings, sourced from PORT_SCANNER_* env vars
│   ├── logging.py         # configure_logging() — one format/handler process-wide
│   ├── exceptions.py       # AppError + global exception handlers
│   └── templating.py        # shared Jinja2Templates instance
├── api/v1/
│   └── router.py           # api_router, mounted at settings.api_v1_prefix (empty scaffold)
├── routes/
│   ├── health.py            # GET /health — outside /api/v1
│   └── pages.py               # GET / and POST /scan — the server-rendered UI
├── services/
│   └── scan_service.py         # run_scan(): the only place web/ calls discovery.py/parsing.py
├── schemas/
│   ├── health.py                # HealthResponse
│   └── scan.py                    # ScanFormData, PortResultView, ScanResultView
├── templates/
│   ├── base.html                   # shared layout (header/nav/footer, links style.css)
│   ├── scan.html                    # the <form> — a partial included by index.html and results.html
│   ├── index.html                    # GET / — extends base, includes scan.html
│   └── results.html                   # POST /scan success — extends base, includes scan.html + a results table
└── static/css/style.css                # hand-written CSS, no framework, no JS
```

Design points:

- **Application factory, not a bare module-level app.** `create_app()`
  accepts an optional `Settings` override so tests build an app against a
  specific configuration without mutating process environment variables.
  `app.py` still exposes a module-level `app = create_app()` so
  `uvicorn port_scanner.web.app:app` works unchanged.
- **`/health` and the UI pages sit outside `/api/v1`.** Load balancers
  probe `/health` on a fixed path; `GET /`/`POST /scan` are the UI, not a
  JSON API contract — neither should move when the business API version
  bumps. Versioned endpoints mount under `settings.api_v1_prefix` via
  `api/v1/router.py`, which is intentionally still empty — a future JSON
  API for the same scan capability would live there, without touching the
  UI routes.
- **Global exception handling has two tiers**, for the JSON side of the
  app. An `AppError` base class (for future domain errors — auth
  failures, scan-job errors, etc. — to declare their own
  `status_code`/`detail`) and a catch-all `Exception` handler that logs
  the full traceback server-side and returns an opaque 500, so a bug
  never leaks internals to a client. FastAPI's own defaults for
  `HTTPException` and `RequestValidationError` are left untouched. The
  scan form has its *own*, separate error path (below) because its
  errors need to render as HTML, not JSON.
- **Configuration has no third-party dependency.** `core/config.py` is a
  plain `dataclass` reading `PORT_SCANNER_*` environment variables — no
  `pydantic-settings`. This follows the same reasoning as decision 5 in
  [`DECISIONS.md`](DECISIONS.md): don't add a dependency a feature doesn't
  actually need yet.
- **`services/scan_service.py` is the only bridge to the scanning core.**
  `routes/pages.py` never imports `parse_ports`/`discover` directly — it
  calls `run_scan(form)`, which does (and `run_scan` itself calls
  `discovery.discover`, the same function `cli.py` calls — see
  [Decision 20](DECISIONS.md)). This keeps the interface layer thin (HTTP
  concerns only: form parsing, template selection, status codes) and
  keeps the "interfaces never duplicate business logic" rule from
  [Decision 11](DECISIONS.md) enforceable by inspection: if a second web
  route ever needs to run a scan, it calls `run_scan` too, instead of
  re-deriving the call to `discover`.
- **Scan-form errors render as HTML, not JSON.** `run_scan` raises
  `ScanFormError` (a `ValueError` subclass) for anything the user can fix
  — a bad port spec, an out-of-range timeout, an unresolvable target.
  `routes/pages.py` catches it locally and re-renders `index.html` with
  the message inline and the submitted values still filled in (a "sticky"
  form) — it does *not* go through the JSON `AppError`/global-exception
  path above, which exists for a future JSON API, not for a page a human
  is looking at. Genuine bugs (not `ScanFormError`) still fall through to
  the global `Exception` handler.
- **The scan form has bounds the CLI doesn't.** `scan_service.py` caps
  ports-per-scan, timeout, and worker count — see
  [Decision 16](DECISIONS.md). The CLI has no such caps because argv is
  typed by whoever runs it locally; this form is reachable by anyone who
  can reach the server.
- **`scan.html` is a partial, not a page.** It contains only the `<form>`
  and is `{% include %}`d by both `index.html` (empty/sticky form) and
  `results.html` (sticky form + a results table below it), so the field
  markup exists exactly once.
- **`results.html`'s table has four columns: Port, Status, Service,
  Banner** — the same four fields as `PortResult`/`PortResultView`
  (Milestone 3), rendered with the banner in a monospace column (`.banner-cell`
  in `static/css/style.css`) since banners are typically version strings.
  No new CSS system was introduced — this reuses the `.card`/`.state`/
  `.results-table` classes already in place since Milestone 2.
- **Synchronous route handlers, not `async def`.** `scan_range` blocks the
  calling thread until every port in the batch has been probed. Starlette
  runs a plain `def` route in a worker thread automatically
  (`run_in_threadpool`); had `submit_scan` been `async def` and called
  `run_scan` directly, a single in-flight scan would block the entire
  event loop — every other request the server is handling — for the
  scan's duration.

## Why business logic is separated from the interface

1. **Testability.** `scanner.py` and `parsing.py` can each be tested in
   isolation (`tests/test_scanner.py`, `tests/test_cli.py`) without going
   through `argparse` or capturing stdout. `cli.py` is tested separately for
   its own parsing wiring and exit-code behavior.
2. **Reusability.** Nothing in `scanner.py`, `parsing.py`, `detection.py`,
   or `discovery.py` assumes it's being driven from a terminal. `cli.py`
   and `web/services/scan_service.py` both call `discovery.discover`
   directly — see [`ROADMAP.md`](ROADMAP.md).
3. **Safety of the concurrency model.** Because `scan_port` is pure with
   respect to shared state (it owns only its own socket), `scan_range` can
   run it across a thread pool with zero locking. Mixing in CLI/I/O concerns
   at that layer would risk introducing shared state (e.g. a shared output
   buffer) that isn't thread-safe.
4. **Clear failure boundaries.** Input validation (`parse_ports`) happens
   entirely before any network I/O in the scan engine begins — invalid
   input never reaches `scan_range`.
5. **Interfaces are peers, not dependents of each other.** `parse_ports`
   originally lived in `cli.py`. Left there, any future interface would
   have had to either import from another *interface* module or duplicate
   the parsing logic. Extracting it to `parsing.py` means every interface
   depends only on shared logic modules — never on another interface.
