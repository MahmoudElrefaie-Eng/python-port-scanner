"""Shared Jinja2Templates instance for server-rendered pages.

A single instance so every route module renders through the same template
search path instead of each one constructing its own.
"""

from pathlib import Path

from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
