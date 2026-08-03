# CLAUDE.md — Instructions for Claude Code Sessions

This file tells a future Claude Code session how to work in this repository
safely and consistently. Read this before making changes.

## 1. What this repository is

`port-scanner` is a small, stdlib-only Python CLI tool that performs
concurrent TCP connect scans against a host. It is project `01-port-scanner`
in the `career2026` portfolio directory. See [`../PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md)
for current status and [`../ARCHITECTURE.md`](../ARCHITECTURE.md) for the
design.

## 2. Repository inspection steps (do this first)

Before proposing or making any change, re-verify the current state rather
than trusting memory or prior docs — this repo evolves independently of any
one conversation:

1. `git log --oneline -20` — see what actually landed recently.
2. `git status` — check for uncommitted work; never discard it silently.
3. Read `src/port_scanner/scanner.py`, `src/port_scanner/parsing.py`,
   `src/port_scanner/detection.py`, `src/port_scanner/discovery.py`,
   `src/port_scanner/cli.py`, and `src/port_scanner/web/` (FastAPI
   interface — skeleton, scan flow, and service detection as of
   Milestone 3; no auth/database/async-queue yet, deliberately deferred,
   see `ROADMAP.md` and `ARCHITECTURE.md`) — this is the entire
   application; all are short enough to read in full.
4. Read `tests/test_scanner.py`, `tests/test_cli.py`,
   `tests/test_detection.py`, `tests/test_discovery.py`, and
   `tests/test_web.py` — the tests define the contract the code must keep.
5. Read `pyproject.toml` — authoritative source for version, dependencies,
   Python support range, and the `port-scanner` console-script entry point.
6. Read `README.md` — user-facing description of features and usage.
7. Only after the above, form an opinion about what to change.

Note: this WSL-mounted path can trigger `git`'s "dubious ownership" safety
check. Do not add a `safe.directory` exception to global git config without
asking the user first; use a one-off `git -c safe.directory='*' <cmd>` for
read-only inspection instead.

## 3. Development workflow

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest                         # run the full test suite
port-scanner 127.0.0.1 --ports 22,80,443   # manual smoke test
```

To also run `tests/test_web.py` and the FastAPI app, install the `web`
extra too: `pip install -e ".[dev,web]"`, then
`uvicorn port_scanner.web.app:app --reload`. The base CLI install
(`pip install -e .` with no extras) stays dependency-free either way.

There is no linter, formatter, or type-checker configured in this repo today
— do not assume `black`/`ruff`/`mypy` are wired in until you check
`pyproject.toml` and `.github/workflows/ci.yml` again.

## 4. Coding standards (as already practiced in this codebase)

- **Stdlib only for the base install and core.** `scanner.py`, `parsing.py`,
  `detection.py`, `discovery.py`, and `cli.py` depend on nothing outside
  the Python standard library (`socket`, `ssl`, `re`, `argparse`,
  `concurrent.futures`, `functools`, `typing`); the base `pip install -e .`
  (no extras) stays dependency-free. Don't add a
  runtime dependency to those three files, or to `[project] dependencies`,
  without discussing it with the user first. `src/port_scanner/web/` is the
  one deliberate exception — it depends on the `web` extra
  (`fastapi`, `uvicorn[standard]`, `jinja2`, `python-multipart`), approved
  specifically for that interface; even there, don't add a new dependency
  beyond what's already approved without asking first (see decision 14 in
  `DECISIONS.md` for an example of choosing *not* to add one).
- **Keep business logic and interface separated.** Scanning logic lives in
  `scanner.py`; argument parsing, spec parsing, and I/O live in `cli.py`.
  Don't let `scanner.py` import `argparse` or call `print`/`sys.exit`.
- **Type hints on public functions**, short docstrings explaining behavior
  and edge cases (see `parse_ports` for the style: what it accepts, what it
  raises).
- **Small, stateless functions.** `scan_port` opens and closes its own
  socket and shares no state with other calls — this is what makes the
  thread pool in `scan_range` safe without locks. Preserve this property if
  you touch scanning code.
- **Exit code contract**: `0` = scan completed (even with zero open ports),
  `2` = invalid input (bad port spec). Preserve this if you touch `cli.py`
  — it's part of the documented, scriptable interface.

## 5. Testing philosophy

Tests use real local sockets (bind to `127.0.0.1` on an OS-assigned port,
optionally listen) rather than mocking `socket`. This is intentional: it
verifies actual connect behavior instead of asserting against a mocked
approximation of it. Follow this pattern for new scanner tests. Run `pytest`
before considering any change to `src/` complete.

## 6. Commit workflow

- Do not commit unless the user explicitly asks you to.
- Existing commit messages are short, imperative, and sometimes prefixed
  with a conventional-commit type (`chore:`, `docs:`, `ci:`) — match this
  style. Look at `git log --oneline` for the most recent examples before
  writing a new message.
- Never `--amend`, force-push, or rewrite history unless explicitly asked.
- Never bypass hooks (`--no-verify`) or commit `.venv/`, `__pycache__/`, or
  `*.egg-info/` — they are already covered by `.gitignore`.
- Stage specific files by name; avoid `git add -A` / `git add .` blindly.

## 7. Documentation set in this repository

| File | Purpose |
|---|---|
| `README.md` | User-facing: install, usage, features. |
| `PROJECT_CONTEXT.md` | Current status, version, next objective. |
| `ARCHITECTURE.md` | How the code is structured and why. |
| `ROADMAP.md` | Detailed phased roadmap. |
| `DECISIONS.md` | Architectural decisions and their rationale. |
| `docs/CLAUDE.md` | This file. |
| `docs/MASTER_CONTEXT.md` | Portfolio-level vision and long-term goals. |
| `docs/ENGINEERING_RULES.md` | Principles, testing, and git conventions. |
| `docs/CAREER_ROADMAP.md` | High-level milestone roadmap for this project. |

If you change behavior described in one of these files, update the file in
the same change — don't let docs drift from code.
