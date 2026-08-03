"""FastAPI web interface for the port scanner.

A peer of ``port_scanner.cli`` — depends only on ``port_scanner.scanner``
and ``port_scanner.parsing``, never on the CLI module. See
``../../../ARCHITECTURE.md`` for the full layering rationale.
"""
