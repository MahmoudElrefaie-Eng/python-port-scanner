"""Request/response models for the server-rendered scan form."""

from __future__ import annotations

from pydantic import BaseModel

DEFAULT_PORT_SPEC = "1-1024"
DEFAULT_TIMEOUT = "1.0"
DEFAULT_WORKERS = "50"


class ScanFormData(BaseModel):
    """The scan form's raw field values, always strings.

    Kept as strings (not coerced to float/int here) so an invalid value —
    e.g. a non-numeric timeout — can be redisplayed to the user exactly as
    they typed it, with a validation message, instead of failing before we
    even have something to show them.
    """

    target: str = ""
    ports: str = DEFAULT_PORT_SPEC
    timeout: str = DEFAULT_TIMEOUT
    workers: str = DEFAULT_WORKERS


class ScanResultView(BaseModel):
    """A completed scan, shaped for template rendering."""

    target: str
    open_ports: list[int]
    ports_scanned: int
    timeout: float
    workers: int
    elapsed_seconds: float
