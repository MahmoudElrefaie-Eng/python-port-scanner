"""Security assessment: vulnerability matching, risk scoring, and (in the
future) reporting, compliance, threat intelligence, and AI-assisted
analysis — see ARCHITECTURE.md and DECISIONS.md 27-33.

A peer to `scanner.py`/`parsing.py`/`detection.py`/`discovery.py` in the
shared-logic layer. Depends on `discovery.PortResult` as input; nothing in
`discovery.py` depends on this package.
"""
