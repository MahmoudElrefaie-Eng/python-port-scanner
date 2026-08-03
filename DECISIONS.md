# DECISIONS.md

Architectural decisions already reflected in the codebase, with rationale.
This is a record of what was chosen and why — not a proposal document.

## 1. TCP connect scan, not raw sockets / SYN scan

**Decision:** `scan_port` uses a standard `socket.connect_ex` TCP connect
scan (`scanner.py`).

**Rationale:** A connect scan requires no elevated privileges and no raw
socket access, so the tool runs the same way for any user on any platform
the standard library supports. This trades off scan stealth (a connect scan
completes the TCP handshake, unlike a SYN scan) for portability and
simplicity — an acceptable trade-off for an educational/portfolio tool with
no dependency on `libpcap`-style raw packet access.

## 2. Thread pool concurrency, not asyncio or multiprocessing

**Decision:** `scan_range` parallelizes with `concurrent.futures.ThreadPoolExecutor`.

**Rationale:** `scan_port` is I/O-bound (blocked on `connect_ex` /
`socket` timeouts), which is exactly the workload threads handle well in
Python — the GIL is released during blocking socket calls. Threads also
keep the code simple (no `async`/`await` propagation through the call
stack, no event-loop management) compared to `asyncio`, and avoid the
process-startup and IPC overhead multiprocessing would add for a workload
that isn't CPU-bound.

## 3. No shared state across scan workers

**Decision:** Each `scan_port` call opens and closes its own socket; no
locks, queues, or shared mutable objects are used across threads.

**Rationale:** This is what makes the `ThreadPoolExecutor` usage safe with
zero synchronization code. It was a deliberate design constraint on
`scan_port`'s signature (pure function of `host`/`port`/`timeout`, returns a
`bool`) rather than an accident.

## 4. `src/`-layout packaging via `pyproject.toml`

**Decision:** The installable package lives at `src/port_scanner/`, built
with `setuptools` via `pyproject.toml`, exposing a `port-scanner` console
script (`port_scanner.cli:main`).

**Rationale:** `src/`-layout prevents accidentally importing the package
from the working directory instead of the installed version, which is a
common source of "works on my machine" bugs in Python projects. A console
script gives the project a real CLI (`port-scanner ...`) instead of
requiring `python -m ...` invocation.

## 5. Zero third-party runtime dependencies

**Decision:** `pyproject.toml` declares `dependencies = []`; only `pytest`
is added, and only as a `dev` extra.

**Rationale:** Keeps the tool trivially installable and auditable — no
supply-chain surface beyond the Python standard library at runtime. Fits a
security-tooling context where dependency provenance matters.

## 6. Separate business logic (`scanner.py`) from interface (`cli.py`)

**Decision:** `scanner.py` has no knowledge of `argparse`, stdout, or exit
codes; `cli.py` owns all of that and calls into `scanner.py`.

**Rationale:** Enables independent testing of the scan engine (with real
sockets) versus the CLI/parsing layer (exit codes, stdout/stderr content),
and keeps the door open for a future non-CLI interface (e.g. the planned
web interface in `ROADMAP.md`) to reuse `scan_range`/`scan_port` unchanged.
See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full rationale.

## 7. Real-socket tests instead of mocked sockets

**Decision:** `tests/test_scanner.py` and `tests/test_cli.py` bind actual
listening/closed sockets on `127.0.0.1` rather than mocking `socket`.

**Rationale:** A mocked socket test can only assert that `scan_port` calls
`connect_ex` — it can't catch a bug in how the result is interpreted or how
timeouts behave. Testing against real local sockets gives higher confidence
for code whose entire purpose is network I/O correctness.

## 8. Exit code contract: `0` success / `2` invalid input

**Decision:** `main()` returns `0` for any completed scan (open ports found
or not) and `2` when the port spec fails validation, before any network
activity occurs.

**Rationale:** Makes the tool safe to compose in shell scripts and CI
pipelines — a non-zero, distinct exit code specifically for "you gave me
garbage input" versus "the scan ran" is a standard CLI convention.

## 9. Nmap-style port-spec syntax

**Decision:** `--ports` accepts comma-separated ports and dash ranges
(`22,80,443,8000-8010`), parsed by `parse_ports`.

**Rationale:** This syntax is already familiar to the tool's target
audience (security practitioners used to `nmap -p`), minimizing the
learning curve for using the CLI.

## 10. MIT license

**Decision:** The project is licensed under the MIT License (`LICENSE`),
as declared in `pyproject.toml` (`license = { file = "LICENSE" }`).

**Rationale:** MIT is a permissive, widely recognized license that imposes
minimal restrictions on reuse, which fits a portfolio project intended to
be read, run, and learned from by others without licensing friction.

## 11. Port-spec parsing extracted into its own module (`parsing.py`)

**Decision:** `parse_ports` and `_to_port`, originally defined in `cli.py`,
were moved verbatim (no logic or behavior change) into a new
`src/port_scanner/parsing.py` module. `cli.py` now imports `parse_ports`
from there instead of defining it.

**Rationale:** This logic takes a string and returns validated port
numbers — it has no dependency on `argparse`, console output, or process
exit codes, so it was never truly CLI-specific. It was made ahead of adding
a second interface (a planned FastAPI web application, see
[`ROADMAP.md`](ROADMAP.md)) specifically to avoid a bad choice that
otherwise would have been forced: either the new interface imports parsing
logic from another *interface* module (`cli.py`), or it duplicates the
parser. Both are worse than giving parsing logic its own module that every
interface can depend on as a peer. See
[`ARCHITECTURE.md`](ARCHITECTURE.md) for the resulting layering.

## 12. Web interface built as an application factory, not a bare module

**Decision:** `src/port_scanner/web/app.py` exposes `create_app(settings=None)`,
which builds and returns a configured `FastAPI` instance; a module-level
`app = create_app()` is kept only so `uvicorn port_scanner.web.app:app`
keeps working unchanged.

**Rationale:** A bare module-level `FastAPI()` instance can only ever be
configured one way per process. The factory takes an optional `Settings`
override so `tests/test_web.py` can build an app against specific
configuration without mutating environment variables (avoiding test
pollution/ordering issues), and so future deployments (different
environments, or eventually a test/staging app with different feature
flags) don't require a different entry-point module.

## 13. `/health` is unversioned; business routes mount under `/api/v1`

**Decision:** `GET /health` lives at the app root
(`src/port_scanner/web/routes/health.py`), outside the
`api/v1/router.py` aggregator that future business endpoints mount under
`settings.api_v1_prefix`.

**Rationale:** Health checks are consumed by infrastructure (load
balancers, Kubernetes liveness/readiness probes), not API clients — their
path must not move when the business API's version changes. Versioning the
business API from the start (an empty `api_router` mounted in `app.py`)
means adding the first real `/api/v1` endpoint in a later milestone never
requires touching `app.py` again.

## 14. Environment-variable configuration via a plain dataclass, not `pydantic-settings`

**Decision:** `src/port_scanner/web/core/config.py`'s `Settings` is a
frozen `dataclass` with a `from_env()` classmethod reading
`PORT_SCANNER_*`-prefixed environment variables, cached process-wide by
`get_settings()` (`functools.lru_cache`) — not a `pydantic-settings`
`BaseSettings` subclass.

**Rationale:** `fastapi` already brings in `pydantic` as a transitive
dependency (used for request/response schemas), but `pydantic-settings` is
a separate package this project doesn't otherwise need. Consistent with
decision 5 (zero unnecessary dependencies): a handful of scalar/list
environment variables doesn't justify adding it. If configuration grows
materially more complex (nested models, secrets sources), this can be
revisited.

## 15. Global exception handling: `AppError` base class + catch-all, FastAPI defaults untouched

**Decision:** `src/port_scanner/web/core/exceptions.py` registers exactly
two handlers: one for a new `AppError` base class (for future domain
errors to declare their own `status_code`/`detail`), and one catch-all for
`Exception` that logs the full traceback server-side and returns an opaque
`{"detail": "Internal server error"}` with status 500. FastAPI's built-in
handlers for `HTTPException` and `RequestValidationError` are left
registered as-is.

**Rationale:** Starlette's exception middleware dispatches to the most
specific registered handler for an exception's class, so adding these two
handlers doesn't change behavior for `HTTPException`/validation errors
already handled well by FastAPI's defaults — it only adds a safety net for
genuinely unhandled bugs (never leak an internal exception message to a
client) and a clean path for future domain-specific errors (auth failures,
scan-job errors) to map to HTTP responses without each route needing its
own `try`/`except`.

## 16. Scan-form validation errors render as HTML inline, bypassing the JSON exception path

**Decision:** `services/scan_service.run_scan()` raises `ScanFormError` (a
`ValueError` subclass) for bad input — empty target, invalid port spec,
out-of-range timeout/workers, unresolvable host, `OSError` during the scan.
`routes/pages.py`'s `submit_scan()` catches `ScanFormError` itself and
re-renders `index.html` with the message inline and the submitted values
preserved (HTTP 422). It does *not* raise `AppError` or let the error reach
the global `Exception` handler from decision 15, which returns JSON.

**Rationale:** `AppError`/the global handler exist for API consumers that
expect a JSON body back. `POST /scan` is submitted by an HTML `<form>` from
a browser — a JSON error response would render as a blank page or raw text,
exactly the "expose internal exceptions" outcome the milestone's
requirements call out to avoid. Keeping this translation local to
`submit_scan()` (rather than, say, teaching the global handler to detect
"was this an HTML request") keeps the two error paths (JSON API vs. HTML
form) simple and independently understandable, at the cost of one small
`try`/`except` per form-submitting route — an acceptable trade at this
scale, revisit if more form endpoints appear.

## 17. Public scan form has input bounds the CLI doesn't need

**Decision:** `services/scan_service.py` rejects (with a `ScanFormError`,
not a crash) more than `MAX_PORTS_PER_SCAN = 1024` ports per request,
`timeout` outside `[0.1, 10.0]` seconds, and `workers` outside `[1, 200]`.
`parse_ports`/`scan_range` themselves are unchanged and enforce none of
this.

**Rationale:** The CLI's `--timeout`/`--workers`/`--ports` are typed by
whoever is running the tool on their own machine against a target they
chose — there's no one to protect them from. `POST /scan` is reachable by
anyone who can reach the server, so an unbounded `ports=1-65535` (65,535
sockets) or `workers=1000000` (attempting to spin up a thread pool of that
size) is a trivial resource-exhaustion vector against the server itself,
not just the scan target. These bounds are basic input validation, not a
substitute for the auth/rate-limiting this milestone deliberately leaves
out — see [`ROADMAP.md`](ROADMAP.md) for what's still planned.

## 18. `scan.html` is a Jinja2 partial, included by both `index.html` and `results.html`

**Decision:** The `<form>` markup (target/ports/timeout/workers fields,
the error banner) lives in its own template, `scan.html`, which does not
extend `base.html` and is never rendered directly by a route. `index.html`
and `results.html` each `{% include "scan.html" %}` it.

**Rationale:** `GET /` (empty form) and a successful `POST /scan` (sticky
form + a results table below it) show the same form. Duplicating the
field markup across two page templates would mean every future field
change (Milestone 3's likely additions, e.g. a scan-type selector) needs
to happen twice and can drift. An `{% include %}`d partial keeps one
source of truth without introducing template inheritance more complex
than the project needs at this size.

## 19. Scan route handlers are synchronous `def`, not `async def`

**Decision:** `index()` and `submit_scan()` in `routes/pages.py` are
defined with plain `def`, not `async def`.

**Rationale:** `scan_range` (via `scanner.py`) is a blocking call — it
doesn't return until every port in the batch has been probed, sometimes
several seconds. Starlette dispatches a synchronous route handler to a
worker thread automatically (`run_in_threadpool`); FastAPI's event loop
stays free to serve other requests while a scan is in flight. Had
`submit_scan` been `async def` and called the (synchronous) `run_scan`
directly, one in-flight scan would block the single-threaded event loop —
and therefore every other request the server is handling — for the
scan's entire duration.

## 20. Service detection is two new peer modules (`detection.py`, `discovery.py`), not changes to `scanner.py`

**Decision:** Milestone 3 (service detection & banner grabbing) added
`src/port_scanner/detection.py` (service guessing, banner grabbing) and
`src/port_scanner/discovery.py` (`discover()`, orchestrating `scanner.py`
+ `detection.py` into `list[PortResult]`). `scanner.py` and `parsing.py`
are byte-for-byte unchanged — not even a new parameter.

**Rationale:** `scan_port`/`scan_range` had an established contract
(`bool`, `list[int]`) that `tests/test_scanner.py` and `cli.py` already
depended on; changing their return type to structured objects would have
broken both for no benefit, since nothing about "does this port accept a
TCP connection" needs to know about banners. `discovery.py` composes the
existing scan with the new detection step from the outside, the same way
`cli.py` and `web/` already compose `parsing.py` with `scanner.py` — one
more layer in a pattern that was already working, not a new pattern.
`detection.py` depends on nothing else in the shared-logic layer (it only
needs a `(host, port)` to probe, not a scan result), so it's independently
testable and reusable even outside `discover()`.

## 21. No Nmap, no external APIs, no vulnerability scanning — a hard boundary, not a starting point

**Decision:** Every technique in `detection.py` is either a static
well-known-port table or a short, protocol-aware exchange the tool
performs itself over a socket it already opened. Nothing shells out to
`nmap`, calls a third-party lookup service, or performs any
credential/exploit/CVE-style probing.

**Rationale:** This was an explicit constraint on the milestone, not
merely a nice-to-have: this project is a portfolio piece demonstrating
what can be built from first principles with the standard library, not a
wrapper around an existing scanner. It also keeps the tool's legal/ethical
footprint identical to what [`README.md`](README.md)'s disclaimer already
describes (a TCP connect scan and a read of what a service volunteers) —
adding exploit or vulnerability probing would change what "authorized
security testing and educational use" actually means for this tool and
wasn't something to introduce without that conversation happening first.

## 22. Active banner probes for 9 of the 16 required services; port-guess + passive read for the rest

**Decision:** `_BANNER_GRABBERS` has entries for SSH, FTP, SMTP, POP3,
IMAP, HTTP, HTTPS, MySQL, and Redis. DNS, LDAP, SMB, RDP, PostgreSQL,
MongoDB, and NTP are identified by `guess_service`'s port table only;
their banner falls through to `_grab_generic` (a passive read, no write).

**Rationale:** The 9 implemented protocols either send a greeting
unprompted (SSH/FTP/SMTP/POP3/IMAP/MySQL) or respond to one trivial,
universally-supported request (HTTP/HTTPS `HEAD /`; Redis `INFO`, which
works pre-authentication on a default install). The other 7 require
building and parsing a binary or ASN.1-encoded protocol handshake
(SMB negotiate, LDAP BER-encoded bind/search, RDP's X.224 exchange,
PostgreSQL's startup packet, MongoDB's BSON wire protocol) for
meaningfully more implementation and maintenance cost per protocol than
the 9 above, with a materially higher chance of getting a fiddly detail
wrong against real-world server variance. "The implementation should
remain lightweight" (the milestone's own words) was read as license to
cut scope here rather than build seven fragile protocol clients. Every
port in `SERVICE_PORTS` still gets a correct *service name* — only the
*banner* is `"Unknown"` for these seven. This is a documented boundary,
not a bug; expanding `_BANNER_GRABBERS` to cover more of them is a
natural, additive follow-up (each new grabber is one function and one
dict entry, per [Decision 20](DECISIONS.md)'s module layout) if a future
milestone wants it.

## 23. `identify_service` catches `Exception` broadly, on purpose

**Decision:** `identify_service`'s call into whichever grabber it
dispatches to is wrapped in a bare `except Exception`, not a narrower set
of expected error types (`OSError`, `ssl.SSLError`, etc.).

**Rationale:** The milestone's requirement is unconditional: "Never fail
the scan because banner grabbing failed" / "Banner failures should never
stop scanning." A banner grab touches a remote, uncontrolled service —
the failure modes aren't limited to socket errors (a malformed response
could also raise while being decoded or regex-matched, for instance). The
cost of being broad here is low (a banner grab has no side effects to
leave half-finished) and the cost of narrowing it and missing a case is a
whole scan crashing on one uncooperative port. `discover()` and the
callers above it never need their own try/except around a banner grab as
a result — the guarantee lives in exactly one place.

## 24. Two-phase scan-then-identify, not banner-grab-while-scanning

**Decision:** `discover()` runs `scan_range` to completion first, then
runs `identify_service` only over the ports that came back open, in a
second, separate `ThreadPoolExecutor` pass.

**Rationale:** The milestone asks for both correctness ("never fail
the scan") and performance ("do not noticeably slow the scanner" /
"avoid unnecessary socket connections"). A typical scan (e.g. the CLI's
default `1-1024`) has far more closed ports than open ones; giving every
scanned port a second, slower, protocol-aware connection attempt would
multiply the cost of a scan by however many ports are in range, not by
however many are actually open. Restricting the (slower, write-then-read)
detection phase to just the open subset keeps the added cost proportional
to what was actually found, which is the whole point of scanning first.

## 25. The CLI's table formatter is hand-rolled, not a `rich`/`tabulate` dependency

**Decision:** `cli.py`'s `_format_table()` is ~15 lines of stdlib string
formatting (compute column widths, left-justify, join) — no table-rendering
library was added.

**Rationale:** Same reasoning as decision 5: the base `pip install -e .`
install has zero runtime dependencies, and a fixed-width table with four
columns doesn't need a library to render well. `rich`/`tabulate` would
buy color and box-drawing characters at the cost of a new dependency for
a "professional table" requirement that a straightforward `ljust()` loop
satisfies.

## 26. Roadmap pivot: service detection before authentication/accounts/history

**Decision:** After Milestones 1–2 (web skeleton, scan flow), the
originally-planned Milestone 3 — authentication, scan history, user
accounts — was explicitly deferred in favor of service detection & banner
grabbing (this milestone) as the project's direction shifts toward being
a network discovery platform rather than a scan-and-store web app.

**Rationale:** This was a direct instruction, not an inference — recorded
here because it changes what "next" means in [`ROADMAP.md`](ROADMAP.md)
and [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md), and a future session
re-reading old planning docs without this decision would reasonably
expect auth to be next. It has a real architectural upside too:
authentication/history/accounts need a database, and building service
detection first meant that decision didn't have to be made under time
pressure before it was needed — `web/api/v1/router.py` and
`web/services/` already exist and are unaffected by this reordering.
