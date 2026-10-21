from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture(scope="session")
def api_context():
    database_name = f"survey_system_{uuid4().hex}_test"
    settings = Settings(
        _env_file=None,
        mongodb_uri="mongodb://127.0.0.1:27017",
        mongodb_database=database_name,
        mongodb_test_database=database_name,
        mongodb_timeout_ms=3000,
        jwt_secret="integration-test-secret-with-sufficient-length",
    )
    cleanup_client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=3000)
    cleanup_client.admin.command("ping")
    app = create_app(settings=settings)
    try:
        with TestClient(app) as client:
            yield client, app, settings
    finally:
        cleanup_client.drop_database(database_name)
        cleanup_client.close()


@pytest.fixture()
def api(api_context):
    return api_context[0]


def register_and_login(client: TestClient, username: str) -> dict[str, str]:
    payload = {"username": username, "password": "SecurePass123"}
    register = client.post("/api/v1/auth/register", json=payload)
    assert register.status_code == 201, register.text
    login = client.post("/api/v1/auth/login", json=payload)
    assert login.status_code == 200, login.text
    return {
        "Authorization": f"Bearer {login.json()['access_token']}",
        "Content-Type": "application/json",
    }
