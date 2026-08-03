"""Centralized logging configuration for the web interface.

Called once at application startup so every logger in the process —
including uvicorn's own access/error loggers — shares one format and
destination, instead of each subsystem configuring its own handlers.
"""

from __future__ import annotations

import logging
import sys

from port_scanner.web.core.config import Settings

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=settings.log_level.upper(),
        format=LOG_FORMAT,
        stream=sys.stdout,
        force=True,
    )
