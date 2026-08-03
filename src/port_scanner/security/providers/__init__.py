"""Vulnerability data providers.

Each provider implements `VulnerabilityProvider` (`base.py`) — a
three-member Protocol, structurally typed, so a new provider (OSV,
Vulners, a future in-house feed) is a new file implementing that Protocol
and nothing else needs to change. See DECISIONS.md 29-30.
"""
