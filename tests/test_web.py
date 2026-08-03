"""Tests for the web interface: skeleton (Milestone 1) and scan flow
(Milestone 2).

Requires the ``web`` and ``dev`` extras: ``pip install -e ".[dev,web]"``.
"""

import re
import socket

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from port_scanner.web.app import create_app
from port_scanner.web.core.config import Settings, get_settings
from port_scanner.web.core.exceptions import AppError, register_exception_handlers
from port_scanner.web.schemas.scan import ScanFormData
from port_scanner.web.services.scan_service import ScanFormError, run_scan


def _free_port() -> int:
    """Ask the OS for an unused local port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def settings() -> Settings:
    return Settings.from_env()


@pytest.fixture
def client(settings) -> TestClient:
    return TestClient(create_app(settings))


class TestHealthEndpoint:
    def test_returns_ok(self, client: TestClient):
        response = client.get("/health")

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["status"] == "ok"
        assert body["app_name"] == "Port Scanner API"
        assert body["version"] == "1.0.0"
        assert body["environment"] == "development"

    def test_is_not_versioned(self, client: TestClient, settings: Settings):
        # /health must stay stable across API version bumps, so it must
        # not live under the /api/v1 prefix.
        versioned = client.get(f"{settings.api_v1_prefix}/health")
        assert versioned.status_code == status.HTTP_404_NOT_FOUND


class TestOpenAPICustomization:
    def test_title_and_version_match_settings(self, client: TestClient, settings: Settings):
        schema = client.get("/openapi.json").json()

        assert schema["info"]["title"] == settings.app_name
        assert schema["info"]["version"] == settings.app_version
        assert schema["info"]["contact"] == {"name": "Mahmoud Elrefaie"}

    def test_health_tag_documented(self, client: TestClient):
        schema = client.get("/openapi.json").json()
        tag_names = {tag["name"] for tag in schema.get("tags", [])}
        assert "health" in tag_names

    def test_docs_and_redoc_are_served(self, client: TestClient):
        assert client.get("/docs").status_code == status.HTTP_200_OK
        assert client.get("/redoc").status_code == status.HTTP_200_OK


class TestGlobalExceptionHandling:
    def _app_with_failing_route(self) -> FastAPI:
        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/boom")
        async def boom():
            raise RuntimeError("something broke internally")

        class NotFoundError(AppError):
            status_code = status.HTTP_404_NOT_FOUND
            detail = "resource not found"

        @app.get("/known-error")
        async def known_error():
            raise NotFoundError()

        return app

    def test_unhandled_exception_returns_generic_500(self):
        client = TestClient(self._app_with_failing_route(), raise_server_exceptions=False)

        response = client.get("/boom")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.json() == {"detail": "Internal server error"}
        # The real exception message must not leak to the client.
        assert "something broke internally" not in response.text

    def test_app_error_maps_to_its_declared_status_and_detail(self):
        client = TestClient(self._app_with_failing_route(), raise_server_exceptions=False)

        response = client.get("/known-error")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {"detail": "resource not found"}


class TestSettings:
    def test_defaults_when_env_unset(self, monkeypatch):
        for name in [
            "PORT_SCANNER_APP_NAME",
            "PORT_SCANNER_ENVIRONMENT",
            "PORT_SCANNER_DEBUG",
            "PORT_SCANNER_LOG_LEVEL",
            "PORT_SCANNER_API_V1_PREFIX",
            "PORT_SCANNER_CORS_ORIGINS",
        ]:
            monkeypatch.delenv(name, raising=False)

        settings = Settings.from_env()

        assert settings.app_name == "Port Scanner API"
        assert settings.environment == "development"
        assert settings.debug is False
        assert settings.api_v1_prefix == "/api/v1"
        assert settings.cors_origins == []

    def test_reads_overrides_from_environment(self, monkeypatch):
        monkeypatch.setenv("PORT_SCANNER_APP_NAME", "Custom Scanner")
        monkeypatch.setenv("PORT_SCANNER_ENVIRONMENT", "production")
        monkeypatch.setenv("PORT_SCANNER_DEBUG", "true")
        monkeypatch.setenv("PORT_SCANNER_CORS_ORIGINS", "https://a.example, https://b.example")

        settings = Settings.from_env()

        assert settings.app_name == "Custom Scanner"
        assert settings.environment == "production"
        assert settings.debug is True
        assert settings.cors_origins == ["https://a.example", "https://b.example"]

    def test_get_settings_is_cached(self):
        get_settings.cache_clear()
        try:
            assert get_settings() is get_settings()
        finally:
            get_settings.cache_clear()


class TestScanPage:
    def test_get_index_renders_form(self, client: TestClient):
        response = client.get("/")

        assert response.status_code == status.HTTP_200_OK
        assert 'name="target"' in response.text
        assert 'name="ports"' in response.text
        # url_for() may render an absolute or relative URL depending on
        # Starlette version; either way the form must post to /scan.
        assert re.search(r'action="[^"]*/scan"', response.text)

    def test_static_stylesheet_is_served(self, client: TestClient):
        response = client.get("/static/css/style.css")

        assert response.status_code == status.HTTP_200_OK
        assert "text/css" in response.headers["content-type"]


class TestScanSubmission:
    def test_reports_open_port(self, client: TestClient):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            port = server.getsockname()[1]

            response = client.post(
                "/scan",
                data={"target": "127.0.0.1", "ports": str(port), "timeout": "0.5", "workers": "10"},
            )

        assert response.status_code == status.HTTP_200_OK
        assert str(port) in response.text
        assert "open" in response.text.lower()
        # The form is redisplayed, prefilled with what was submitted.
        assert f'value="{port}"' in response.text
        # New (Milestone 3) results columns.
        assert "Service" in response.text
        assert "Banner" in response.text
        # A raw listening socket isn't a recognized service.
        assert "Unknown" in response.text

    def test_reports_no_open_ports(self, client: TestClient):
        closed_port = _free_port()

        response = client.post(
            "/scan",
            data={"target": "127.0.0.1", "ports": str(closed_port), "timeout": "0.5", "workers": "10"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert "no open ports" in response.text.lower()

    def test_invalid_port_spec_shows_friendly_error(self, client: TestClient):
        response = client.post(
            "/scan",
            data={"target": "127.0.0.1", "ports": "not-a-port", "timeout": "1.0", "workers": "10"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "invalid port" in response.text.lower()
        assert "Traceback" not in response.text
        assert "ValueError" not in response.text

    def test_missing_target_shows_friendly_error(self, client: TestClient):
        response = client.post(
            "/scan",
            data={"target": "", "ports": "80", "timeout": "1.0", "workers": "10"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "target is required" in response.text.lower()

    def test_non_numeric_timeout_shows_friendly_error(self, client: TestClient):
        response = client.post(
            "/scan",
            data={"target": "127.0.0.1", "ports": "80", "timeout": "not-a-number", "workers": "10"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "timeout" in response.text.lower()

    def test_too_many_ports_is_rejected(self, client: TestClient):
        response = client.post(
            "/scan",
            data={"target": "127.0.0.1", "ports": "1-65535", "timeout": "0.1", "workers": "50"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "too many ports" in response.text.lower()

    def test_workers_out_of_bounds_is_rejected(self, client: TestClient):
        response = client.post(
            "/scan",
            data={"target": "127.0.0.1", "ports": "80", "timeout": "1.0", "workers": "100000"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "workers" in response.text.lower()


class TestScanService:
    """Unit tests for the service layer, independent of HTTP wiring."""

    def test_run_scan_finds_open_port(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            port = server.getsockname()[1]

            result = run_scan(
                ScanFormData(target="127.0.0.1", ports=str(port), timeout="0.5", workers="10")
            )

        assert [r.port for r in result.results] == [port]
        assert result.results[0].state == "OPEN"
        assert result.ports_scanned == 1
        assert result.target == "127.0.0.1"

    def test_run_scan_rejects_blank_target(self):
        with pytest.raises(ScanFormError, match="Target is required"):
            run_scan(ScanFormData(target="  ", ports="80"))

    def test_run_scan_rejects_invalid_port_spec(self):
        with pytest.raises(ScanFormError, match="invalid port"):
            run_scan(ScanFormData(target="127.0.0.1", ports="abc"))

    def test_run_scan_rejects_unresolvable_target(self):
        with pytest.raises(ScanFormError, match="Could not scan"):
            run_scan(
                ScanFormData(
                    target="this-host-should-not-resolve.invalid",
                    ports="80",
                    timeout="0.5",
                )
            )
