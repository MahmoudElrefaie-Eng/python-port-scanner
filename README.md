# Port Scanner

A professional-grade TCP/UDP port scanner built in Python, developed as part of a cybersecurity portfolio.

## Status

🚧 Under active development — core scanning engine, CLI, and packaging complete.

## Roadmap

- [x] Project scaffolding, Git, README, licensing
- [x] Core TCP connect scanning engine
- [x] Concurrency (threaded scanning for speed)
- [x] CLI interface (argument parsing, target/port range input)
- [x] Packaging (`pyproject.toml`, installable console script)
- [x] Test suite
- [ ] Service/banner detection
- [ ] Output formats (JSON, table, file export)
- [ ] CI (automated tests on every push)

## Project Structure

```
01-port-scanner/
├── src/port_scanner/   # installable package source
│   ├── scanner.py      # scan_port / scan_range (TCP connect scan engine)
│   └── cli.py          # command-line interface
├── tests/              # test suite
├── pyproject.toml      # packaging & dependencies
├── README.md
├── .gitignore
└── LICENSE
```

## Installation

Requires Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

```bash
port-scanner 127.0.0.1 --ports 22,80,443,8000-8010
port-scanner example.com --ports 1-1024 --timeout 0.5 --workers 100
```

Run the test suite:

```bash
pytest tests/
```

## Disclaimer

This tool is intended for authorized security testing and educational use only (e.g., scanning systems you own or have explicit permission to test). Unauthorized port scanning of systems you do not own or have permission to test may be illegal in your jurisdiction.

## License

MIT — see [LICENSE](LICENSE).
