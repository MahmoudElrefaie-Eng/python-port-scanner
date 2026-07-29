# CAREER_ROADMAP.md — High-Level Roadmap for This Project

This is the milestone-level view of `01-port-scanner`'s progress within the
`career2026` portfolio. For implementation-level detail see
[`../ROADMAP.md`](../ROADMAP.md); for the decisions behind these milestones
see [`../DECISIONS.md`](../DECISIONS.md).

## Completed milestones

| Milestone | Evidence |
|---|---|
| Project scaffolding, Git, README, licensing | `LICENSE` (MIT), initial commits |
| Core TCP connect-scan engine | `src/port_scanner/scanner.py: scan_port` |
| Concurrency (threaded scanning) | `src/port_scanner/scanner.py: scan_range` (`ThreadPoolExecutor`) |
| CLI interface | `src/port_scanner/cli.py` (`argparse`, Nmap-style `--ports` spec) |
| Packaging | `pyproject.toml`, `port-scanner` console script |
| Automated test suite | `tests/test_scanner.py`, `tests/test_cli.py` |
| CI (tests on every push/PR) | `.github/workflows/ci.yml` |
| v1.0.0 version bump | `pyproject.toml: version = "1.0.0"` |

## Upcoming milestones

| Milestone | Status |
|---|---|
| Service/banner detection | Planned — not started |
| Output formats (JSON, table, file export) | Planned — not started |
| Web interface for interactive scanning | Planned — not started |
| Deployment story | Planned — not started |

## Portfolio-level note

`01-port-scanner` is currently the sole project directory under
`career2026`. No other project or documented plan exists to compare it
against at this time.
