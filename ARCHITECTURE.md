# ARCHITECTURE.md

## Overview

`port-scanner` is a two-layer application with no third-party runtime
dependencies:

- **Interface layer** — `src/port_scanner/cli.py`: argument parsing,
  port-spec parsing/validation, output formatting, process exit codes.
- **Business logic layer** — `src/port_scanner/scanner.py`: the scan
  engine itself (`scan_port`, `scan_range`), with no knowledge of the CLI,
  `argparse`, or console output.

## Diagram

```mermaid
flowchart TD
    A[User / shell] -->|"port-scanner target --ports ..."| B["cli.py: main()"]
    B --> C["cli.py: parse_ports()<br/>Nmap-style spec parsing & validation"]
    C -->|invalid spec| X["stderr + exit code 2"]
    C -->|valid ports| D["scanner.py: scan_range()"]
    D --> E["ThreadPoolExecutor"]
    E --> F1["scan_port() worker"]
    E --> F2["scan_port() worker"]
    E --> F3["scan_port() worker N"]
    F1 --> G["sorted open ports"]
    F2 --> G
    F3 --> G
    G --> H["cli.py: print results to stdout<br/>exit code 0"]
```

## Layers, in detail

### `scanner.py` — business logic

- `scan_port(host, port, timeout) -> bool`: opens one `socket.AF_INET,
  socket.SOCK_STREAM`, calls `connect_ex`, returns whether it succeeded.
  Fully self-contained — opens and closes its own socket, touches no
  shared state.
- `scan_range(host, ports, timeout, max_workers) -> list[int]`: fans
  `scan_port` out across a `ThreadPoolExecutor`, then returns the open
  ports sorted ascending.

### `cli.py` — interface

- `parse_ports(spec) -> list[int]` / `_to_port`: turns an Nmap-style string
  (`"22,80,443,8000-8010"`) into a validated, deduplicated, sorted list of
  port numbers, raising `ValueError` with a specific message on malformed
  input.
- `build_parser()`: defines the `argparse` CLI surface (`target`, `--ports`,
  `--timeout`, `--workers`).
- `main(argv=None) -> int`: wires parsing → `scan_range` → stdout output →
  exit code. This is the function exposed as the `port-scanner` console
  script entry point (`pyproject.toml`: `port-scanner = "port_scanner.cli:main"`).

## Why business logic is separated from the interface

1. **Testability.** `scanner.py` can be tested with real sockets in
   isolation (`tests/test_scanner.py`) without going through `argparse` or
   capturing stdout. `cli.py` is tested separately for parsing and exit-code
   behavior (`tests/test_cli.py`).
2. **Reusability.** Nothing in `scanner.py` assumes it's being driven from a
   terminal. The same `scan_range`/`scan_port` functions could back a
   different interface — e.g. the web interface listed as a planned item in
   [`ROADMAP.md`](ROADMAP.md) — without any change to the scan engine.
3. **Safety of the concurrency model.** Because `scan_port` is pure with
   respect to shared state (it owns only its own socket), `scan_range` can
   run it across a thread pool with zero locking. Mixing in CLI/I/O concerns
   at that layer would risk introducing shared state (e.g. a shared output
   buffer) that isn't thread-safe.
4. **Clear failure boundaries.** Input validation (`parse_ports`) happens
   entirely in the interface layer, before any network I/O in the business
   layer begins — invalid input never reaches `scan_range`.
