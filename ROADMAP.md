# ROADMAP.md

Detailed roadmap for `01-port-scanner`. Checkbox state reflects what is
actually implemented in the codebase as of this writing, not intent.

```mermaid
flowchart LR
    subgraph P1["Phase 1 — Foundation (done)"]
        direction TB
        p1a["Scaffolding, Git, README, MIT license"]
        p1b["Core TCP connect-scan engine"]
        p1c["Concurrency (ThreadPoolExecutor)"]
        p1d["CLI (argparse, Nmap-style port specs)"]
        p1e["Packaging (pyproject.toml, console script)"]
        p1f["Test suite (pytest, real sockets)"]
        p1g["CI (GitHub Actions)"]
    end
    subgraph P2["Phase 2 — Richer output (planned)"]
        direction TB
        p2a["Service / banner detection"]
        p2b["Output formats: JSON / table / file export"]
    end
    subgraph P3["Phase 3 — Interfaces & delivery (in progress)"]
        direction TB
        p3a1["Web interface: FastAPI skeleton (done)"]
        p3a2["Web interface: scan flow (done)"]
        p3a3["Web interface: auth / history / accounts (planned)"]
        p3b["Deployment"]
    end
    P1 --> P2 --> P3
```

## Phase 1 — Foundation (complete)

- [x] Project scaffolding, Git, README, licensing (MIT)
- [x] Core TCP connect-scan engine (`scan_port`)
- [x] Concurrency — threaded scanning via `ThreadPoolExecutor` (`scan_range`)
- [x] CLI interface — target/port-range input, `--timeout`, `--workers`
- [x] Packaging — `pyproject.toml`, installable `port-scanner` console script
- [x] Test suite — `tests/test_scanner.py`, `tests/test_cli.py`
- [x] CI — automated tests on every push/PR (`.github/workflows/ci.yml`)
- [x] v1.0.0 release (`pyproject.toml`)

## Phase 2 — Richer output (not started)

- [ ] Service/banner detection on open ports
- [ ] Output formats: JSON, table, file export

## Phase 3 — Interfaces & delivery (in progress)

- [x] Web interface — Milestone 1: FastAPI skeleton (`src/port_scanner/web/`
      — app factory, env-var configuration, centralized logging, global
      exception handling, `/api/v1` versioning scaffold, `/health`,
      customized OpenAPI docs; `tests/test_web.py`). No scan logic wired in.
- [x] Web interface — Milestone 2: scan flow. `GET /` and `POST /scan`,
      server-rendered (Jinja2, no JS) via `web/routes/pages.py` and
      `web/services/scan_service.py`, which is the sole caller of
      `parse_ports`/`scan_range` from the web side. `templates/`
      (`base.html`, `index.html`, `scan.html`, `results.html`) and
      `static/css/style.css`. Validation errors (bad port spec, empty
      target, out-of-range timeout/workers, unresolvable host) render
      inline in the page, not as raw exceptions. No auth, database,
      service detection, or async job queue — see the next item.
- [ ] Web interface — auth, scan history, user accounts (needs a database;
      deliberately deferred so Milestones 1–2 didn't add schema/migration
      decisions before they were needed — see
      [Decisions 12–19](DECISIONS.md) for why `web/` is already structured
      to take this without a rewrite: a services layer already sits
      between routes and the scan engine, and `/api/v1` is already mounted
      and empty)
- [ ] Deployment

None of the Phase 2 items exist in `src/port_scanner/` today. Phase 3's web
interface now has a working scan flow (skeleton + Milestone 2); auth,
history, accounts, and deployment remain unstarted, matching the "planned"
section of `README.md`.
