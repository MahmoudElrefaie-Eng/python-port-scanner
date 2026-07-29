# ENGINEERING_RULES.md

Principles this repository is held to, extracted from how the codebase is
actually built today. Treat these as the rules to preserve when extending
the project, not aspirational statements.

## Engineering principles

- **Standard library only.** `src/port_scanner/` has zero runtime
  third-party dependencies (`pyproject.toml`'s `dependencies = []`). The
  only extra dependency is `pytest`, and it is scoped to `[project.optional-dependencies].dev`.
  Adding a runtime dependency is a deliberate decision, not a default.
- **Small, single-purpose functions.** `scan_port`, `scan_range`,
  `parse_ports`, `_to_port`, `build_parser`, `main` — each does one thing.
- **No shared mutable state across concurrency boundaries.** `scan_port`
  opens and closes its own socket per call; `scan_range` relies on this to
  parallelize with `ThreadPoolExecutor` without any locking.
- **Fail fast on bad input.** Invalid port specs are rejected by
  `parse_ports`/`_to_port` with a descriptive `ValueError` before any
  network activity happens, and the CLI turns that into exit code `2`.

## Architecture rules

- **Business logic is independent of the interface.** `scanner.py` must
  stay free of `argparse`, `print`, `sys.exit`, or any other CLI/user-facing
  concern. `cli.py` owns all input parsing, output formatting, and process
  exit codes. This lets the scan engine be reused by a future interface
  (e.g. a web UI) without modification. See [`../ARCHITECTURE.md`](../ARCHITECTURE.md).
- **Package layout is `src/`-based** (`src/port_scanner/`), installed via
  `pyproject.toml` with `[tool.setuptools.packages.find] where = ["src"]`
  and exposed as the `port-scanner` console script
  (`port_scanner.cli:main`). New modules belong under `src/port_scanner/`.

## Testing philosophy

- Tests exercise **real local TCP sockets** (bind to `127.0.0.1` on an
  OS-assigned port via `sock.bind(("127.0.0.1", 0))`), not mocks of
  `socket`. This verifies actual connect-scan behavior rather than an
  assumption about how `socket` behaves.
- Test files mirror the source layout: `tests/test_scanner.py` for
  `scanner.py`, `tests/test_cli.py` for `cli.py`.
- Both the parsing layer (`parse_ports`, valid and invalid specs) and the
  end-to-end CLI (`main`, exit codes, stdout/stderr content) are covered,
  in addition to the scan engine itself.
- Every push and pull request runs the full suite in CI
  (`.github/workflows/ci.yml`) on `ubuntu-latest` with Python 3.14, using
  the same install path a developer would use locally
  (`pip install -e ".[dev]"`).
- A change to `src/` is not complete until `pytest` passes locally.

## Documentation standards

- `README.md` is the user-facing entry point: status, features, install,
  usage/CLI examples, structure, testing, CI, roadmap, disclaimer, license.
  It includes a Mermaid architecture diagram.
- Root-level `PROJECT_CONTEXT.md`, `ARCHITECTURE.md`, `ROADMAP.md`, and
  `DECISIONS.md` plus the `docs/` directory hold the project context,
  design rationale, and process documentation that doesn't belong in the
  README.
- Documentation must reflect the current, verified state of the code — not
  planned or aspirational behavior presented as if already built. Planned
  work is explicitly marked as such (e.g. `[ ]` checkboxes, "planned"
  labels).

## Git workflow

- Commit messages are short, imperative, and often use a conventional-commit
  prefix (`chore:`, `docs:`, `ci:`) — consistent with the existing history
  (`git log --oneline`).
- History is linear; no merge commits or rebasing of shared history
  observed. Prefer new commits over amending published ones.
- `.gitignore` excludes build/venv/cache artifacts (`__pycache__/`,
  `*.egg-info/`, `.venv/`, `.pytest_cache/`) — these must never be
  committed.
