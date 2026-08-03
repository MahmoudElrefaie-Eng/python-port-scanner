"""Environment-driven configuration for the web interface.

No third-party settings library is used here (e.g. ``pydantic-settings``)
because a handful of scalar/list environment variables doesn't need one —
``dependencies = []`` for the base install is a deliberate project
constraint (see ``../../../DECISIONS.md``), and the ``web`` extra should
only grow to include a dependency when a feature actually needs it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache

ENV_PREFIX = "PORT_SCANNER_"


def _env_str(name: str, default: str) -> str:
    return os.environ.get(f"{ENV_PREFIX}{name}", default)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(f"{ENV_PREFIX}{name}")
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: list[str]) -> list[str]:
    raw = os.environ.get(f"{ENV_PREFIX}{name}")
    if raw is None:
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    """Application configuration, sourced entirely from environment variables.

    Every variable is prefixed with ``PORT_SCANNER_`` (e.g.
    ``PORT_SCANNER_LOG_LEVEL``) to avoid collisions with unrelated
    environment variables in shared deployment environments.
    """

    app_name: str = "Port Scanner API"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_name=_env_str("APP_NAME", cls.app_name),
            app_version=_env_str("APP_VERSION", cls.app_version),
            environment=_env_str("ENVIRONMENT", cls.environment),
            debug=_env_bool("DEBUG", cls.debug),
            log_level=_env_str("LOG_LEVEL", cls.log_level),
            api_v1_prefix=_env_str("API_V1_PREFIX", cls.api_v1_prefix),
            cors_origins=_env_list("CORS_ORIGINS", []),
        )


@lru_cache
def get_settings() -> Settings:
    """Return process-wide settings, read from the environment once and cached.

    Cached rather than re-read per request: configuration is a startup-time
    concern in this deployment model (a changed environment variable takes
    effect on the next process restart, same as the CLI's argv).
    """
    return Settings.from_env()
