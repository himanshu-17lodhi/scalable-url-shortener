from unittest.mock import MagicMock

import pytest
from alembic.config import Config
from httpx import ASGITransport, AsyncClient

from alembic import command
from app.config import Settings, settings

from app.database import engine
from app.main import app
from app.rate_limiter import get_client_ip


@pytest.mark.asyncio
async def test_database_connection_pool_configuration():
    assert engine.pool.size() == settings.DB_POOL_SIZE
    assert settings.DB_MAX_OVERFLOW == 10
    assert settings.DB_POOL_PRE_PING is True


def test_safe_client_ip_trusted_header_parsed(monkeypatch):
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", True)
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", ["10.0.0.1"])

    mock_request = MagicMock()
    mock_request.client.host = "10.0.0.1"
    mock_request.headers.get.return_value = "203.0.113.195, 10.0.0.1"

    extracted_ip = get_client_ip(mock_request)
    assert extracted_ip == "203.0.113.195"


def test_safe_client_ip_untrusted_proxy_header_rejected(monkeypatch):
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", True)
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", ["10.0.0.1"])

    mock_request = MagicMock()
    mock_request.client.host = "192.168.1.50"
    mock_request.headers.get.return_value = "203.0.113.195"

    extracted_ip = get_client_ip(mock_request)
    assert extracted_ip == "192.168.1.50"


def test_alembic_migration_config_loading():
    alembic_cfg = Config("alembic.ini")
    command.heads(alembic_cfg)


@pytest.mark.asyncio
async def test_global_exception_handler_sanitizes_errors(monkeypatch):
    @app.get("/api/v1/test-error-endpoint")
    async def mock_error_route():
        raise ValueError("Secret database credentials leaked!")

    monkeypatch.setattr(settings, "DEBUG", False)
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as unhandled_client:
        response = await unhandled_client.get("/api/v1/test-error-endpoint")
        assert response.status_code == 500
        assert response.json() == {"detail": "Internal server error"}


def test_production_default_settings():
    default_settings = Settings(_env_file=None)
    assert default_settings.DEBUG is False
    assert "*" not in default_settings.CORS_ORIGINS
