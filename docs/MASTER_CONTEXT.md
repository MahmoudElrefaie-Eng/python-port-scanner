# MASTER_CONTEXT.md — Portfolio Vision

## Portfolio

This repository lives at `career2026/01-port-scanner`. The numeric prefix
suggests it may be the first entry in a series of portfolio projects under
`career2026`; at the time of writing, `01-port-scanner` is the only project
present in that directory. No sibling project or documented plan for
additional entries currently exists, so the scope and structure of any
future portfolio projects should not be assumed from this naming pattern
alone.

## Purpose of this repository

`port-scanner` is a demonstration of applied cybersecurity/software
engineering skill: a concurrent TCP connect-scan CLI written in pure Python,
built and shipped the way a professional tool would be — packaged,
tested, documented, and continuously integrated. It exists to show:

- Correct, safe use of networking primitives (`socket`) without requiring
  elevated privileges.
- A concurrency model (`ThreadPoolExecutor`) applied appropriately to an
  I/O-bound workload.
- Clean separation between business logic (`scanner.py`) and interface
  (`cli.py`).
- A real automated test suite (`pytest`, real sockets, no mocking) wired
  into GitHub Actions CI.
- Professional packaging (`pyproject.toml`, installable `port-scanner`
  console script) and documentation (README with badges, usage examples,
  architecture diagram, and a stated roadmap).

## Current milestone

**v1.0.0 — stable CLI release.** Per `pyproject.toml` and the repository's
own roadmap checklist (`README.md`), the following are complete:

- Core TCP connect-scan engine (`scan_port`, `scan_range`)
- Concurrent scanning via `ThreadPoolExecutor`
- CLI with Nmap-style port-spec parsing (`22,80,443,8000-8010`)
- Packaging as an installable console script
- Full automated test suite
- CI running the suite on every push/PR (GitHub Actions, Python 3.14)

## Long-term goals

For this project specifically (see [`../ROADMAP.md`](../ROADMAP.md) for
detail):

- Service/banner detection on open ports.
- Additional output formats (JSON, table, file export).
- A web interface for interactive scanning.
- A deployment story for the tool.

For the portfolio as a whole: no other projects currently exist under
`career2026` to compare against, so this section will need to be revisited
once (or if) further projects are added.
