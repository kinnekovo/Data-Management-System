from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pymongo.errors import ServerSelectionTimeoutError

from app.api.health import live, ready
from app.core.config import Settings
from app.main import create_app


class FakeAdmin:
    def __init__(self, available: bool):
        self.available = available

    def command(self, name: str):
        assert name == "ping"
        if not self.available:
            raise ServerSelectionTimeoutError("simulated unavailable database")
        return {"ok": 1}


def request_with_database(available: bool):
    client = SimpleNamespace(admin=FakeAdmin(available))
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(mongodb_client=client)))


def test_live_returns_success_payload_without_database_dependency():
    assert live() == {"status": "alive", "service": "survey-system-api"}


def test_health_routes_declare_http_200_success_status():
    app = create_app(settings=Settings(_env_file=None))
    health_routes = {
        route.path: route
        for route in app.routes
        if route.path in {"/api/v1/health/live", "/api/v1/health/ready"}
    }
    assert set(health_routes) == {
        "/api/v1/health/live",
        "/api/v1/health/ready",
    }
    assert all(route.status_code == 200 for route in health_routes.values())


def test_ready_returns_success_payload_when_database_is_available():
    assert ready(request_with_database(True)) == {
        "status": "ready",
        "database": "connected",
    }


def test_ready_returns_503_without_leaking_database_error():
    with pytest.raises(HTTPException) as error:
        ready(request_with_database(False))
    assert error.value.status_code == 503
    assert error.value.detail == "MongoDB unavailable"
    assert "simulated" not in error.value.detail
