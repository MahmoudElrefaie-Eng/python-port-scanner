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
